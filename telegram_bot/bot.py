# -*- coding: utf-8 -*-
"""
WisataKP - Telegram Bot informasi event dan destinasi wisata Kulon Progo.

Menu:
    📅 Daftar Event   : maksimal 5 event (3 akan datang, 2 hari ini)
    🔍 Cari Event     : pencarian kata kunci, bisa diulang tanpa memilih menu
    🏞️ Wisata         : pilih kategori, lalu ketik nama destinasi
    ❓ Bantuan

Notifikasi:
    Scheduler (scheduler.py) berjalan di dalam bot ini: scraping tiap 6 jam
    dan pengingat event H-1 ke semua pengguna yang menekan /start.

Catatan data:
    CSV dibaca lewat cache yang memeriksa waktu modifikasi file, sehingga
    bila CSV diperbarui oleh proses lain (mis. scheduler scraping) bot
    otomatis memakai data terbaru tanpa perlu restart.
"""

import csv
import importlib
import io
import logging
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from html import escape, unescape
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

try:  # python-telegram-bot >= 21
    from telegram import LinkPreviewOptions

    NO_PREVIEW = {"link_preview_options": LinkPreviewOptions(is_disabled=True)}
except ImportError:  # python-telegram-bot 20.x
    NO_PREVIEW = {"disable_web_page_preview": True}

try:  # opsional: membaca TELEGRAM_BOT_TOKEN dari file .env
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# =========================================================
# KONFIGURASI
# =========================================================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

BASE_DIR = Path(__file__).resolve().parent

# Folder tempat CSV dicari (berdasarkan lokasi bot.py, bukan folder kerja).
_SUBFOLDERS = (
    "", "data", "data/events", "data/validated", "data/validation",
    "data/processed", "data/destinations", "validation",
)
SEARCH_DIRS = [
    root / sub
    for root in (BASE_DIR, BASE_DIR.parent, BASE_DIR.parent.parent)
    for sub in _SUBFOLDERS
]

# Jika beberapa file cocok, file yang paling baru diubah yang dipakai.
EVENT_PATTERNS = ["event_valid*.csv"]
DESTINATION_PATTERNS = [
    "destinasi_60_final*.csv",
    "destinasi_clean*.csv",
    "destinasi*.csv",
]

MAX_EVENT_LIST = 5
MAX_UPCOMING = 3  # jumlah event "akan datang" pada Daftar Event
MAX_TODAY = 2     # jumlah event "hari ini" pada Daftar Event
MAX_SEARCH_RESULTS = 5
MAX_RELATED_EVENTS = 3
MESSAGE_LIMIT = 3900  # batas aman (Telegram menolak di atas 4096 karakter)

WIB = timezone(timedelta(hours=7))

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
# httpx mencetak URL request yang berisi token bot
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("wisatakp")


# =========================================================
# MENU, KATEGORI, DAN MODE PERCAKAPAN
# =========================================================

MENU_DAFTAR = "📅 Daftar Event"
MENU_CARI = "🔍 Cari Event"
MENU_WISATA = "🏞️ Wisata"
MENU_BANTUAN = "❓ Bantuan"

MENU = ReplyKeyboardMarkup(
    [[MENU_DAFTAR], [MENU_CARI], [MENU_WISATA], [MENU_BANTUAN]],
    resize_keyboard=True,
    input_field_placeholder="Pilih menu WisataKP",
)

KATEGORI_WISATA = [
    "🏖️ Pantai",
    "🌿 Wisata Alam",
    "🏡 Desa Wisata",
    "💦 Wisata Air",
    "⛰️ Panorama",
]

# Mode percakapan (disimpan di context.user_data["mode"]); None = menu utama.
MODE_SEARCH = "search"            # mengetik kata kunci event
MODE_WISATA_MENU = "wisata_menu"  # memilih kategori wisata
MODE_WISATA = "wisata_search"     # mengetik nama destinasi

BACK_WORDS = {"menu", "menu utama", "kembali"}

MSG_PILIH_MENU = "Silakan pilih menu yang tersedia."
MSG_EVENT_ERROR = (
    "⚠️ Data event sedang tidak dapat dimuat. "
    "Silakan coba lagi beberapa saat lagi."
)
MSG_DESTINASI_ERROR = (
    "⚠️ Data destinasi wisata sedang tidak dapat dimuat. "
    "Silakan coba lagi beberapa saat lagi."
)


# =========================================================
# UTILITAS TEKS
# =========================================================

EMPTY_VALUES = {"", "nan", "none", "null", "-", "n/a"}

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U0001F1E6-\U0001F1FF"
    "\u2600-\u27BF\u2B00-\u2BFF\u200d\ufe0f]"
)


def get_value(row, candidates):
    """Nilai pertama yang terisi dari daftar nama kolom, atau '-'."""

    for column in candidates:
        value = str(row.get(column) or "").strip()
        if value.lower() not in EMPTY_VALUES:
            return value
    return "-"


def normalize_text(text):
    """Huruf kecil, tanpa aksen dan tanda baca, spasi dirapikan."""

    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def clean_text(text):
    """Merapikan teks untuk tampilan: entitas HTML, markdown, emoji, spasi."""

    text = unescape(str(text or ""))
    text = re.sub(r"[*_`#]{1,3}", "", text)
    text = EMOJI_RE.sub("", text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def shorten(text, max_length):
    """Memotong di batas kata dan menambahkan '...' bila terpotong."""

    if len(text) <= max_length:
        return text
    cut = text[:max_length].rsplit(" ", 1)[0]
    return cut.rstrip(" .,;:–-") + "..."


# =========================================================
# PEMBACAAN DATASET
# =========================================================

def read_csv_rows(path):
    """Membaca CSV; mengembalikan (kolom, baris) dengan nama kolom huruf kecil."""

    raw = path.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("encoding file tidak dikenali")

    header = text.splitlines()[0] if text.strip() else ""
    delimiter = max([",", ";", "\t"], key=header.count)

    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
    columns = {name.strip().lower() for name in (reader.fieldnames or []) if name}

    rows = []
    for record in reader:
        row = {
            key.strip().lower(): value.strip()
            for key, value in record.items()
            if key and isinstance(value, str)
        }
        if any(row.values()):
            rows.append(row)
    return columns, rows


class Dataset:
    """
    Dataset CSV dengan cache berdasarkan waktu modifikasi file.

    load() mengembalikan list (bisa kosong bila datanya memang kosong),
    atau None bila file tidak ditemukan / gagal dibaca. Perbedaan ini
    mencegah bot menyatakan "tidak ditemukan" padahal datanya gagal dimuat.
    """

    def __init__(self, name, env_var, patterns, required_columns, row_filter):
        self.name = name
        self.env_var = env_var
        self.patterns = patterns
        self.required_columns = required_columns
        self.row_filter = row_filter
        self.path = None
        self.mtime = None
        self.rows = None
        self._missing_logged = False

    def find_file(self):
        override = os.getenv(self.env_var)
        if override:
            path = Path(override).expanduser()
            return path if path.is_file() else None

        for pattern in self.patterns:
            matches = [
                path
                for folder in SEARCH_DIRS if folder.is_dir()
                for path in folder.glob(pattern) if path.is_file()
            ]
            if matches:
                return max(matches, key=lambda p: p.stat().st_mtime)
        return None

    def load(self):
        path = self.find_file()

        if path is None:
            if not self._missing_logged:
                log.error(
                    "CSV %s tidak ditemukan. Pola: %s | Folder dicari: %s",
                    self.name,
                    ", ".join(self.patterns),
                    ", ".join(str(d) for d in SEARCH_DIRS if d.is_dir()),
                )
                self._missing_logged = True
            return self.rows  # data lama bila pernah berhasil dimuat

        self._missing_logged = False
        mtime = path.stat().st_mtime

        if self.rows is not None and path == self.path and mtime == self.mtime:
            return self.rows

        try:
            columns, all_rows = read_csv_rows(path)
            if not columns & self.required_columns:
                raise ValueError("kolom yang dibutuhkan tidak ditemukan (file rusak/tidak lengkap?)")
            rows = self.row_filter(all_rows)
        except Exception as error:  # noqa: BLE001
            # File sedang ditulis proses lain / rusak: tetap pakai data lama.
            log.error("Gagal membaca CSV %s (%s): %s", self.name, path, error)
            return self.rows

        self.rows, self.path, self.mtime = rows, path, mtime
        log.info(
            "CSV %s dimuat: %d dari %d baris | %s",
            self.name, len(rows), len(all_rows), path,
        )
        return self.rows


def filter_valid_events(rows):
    """Hanya event valid; baris yang ditandai duplikat dilewati."""

    events = []
    for row in rows:
        status = row.get("status_validasi", "").lower()
        if status and not status.startswith("valid"):
            continue
        if "true" in (row.get("duplikat_url", "").lower(),
                      row.get("duplikat_judul", "").lower()):
            continue
        events.append(row)
    return events


def filter_destinations(rows):
    """Hanya destinasi yang dipertahankan pada proses validasi."""

    destinations, seen = [], set()
    for row in rows:
        name = get_destination_name(row)
        if name == "-":
            continue

        decision = row.get("keputusan", "").lower()
        if decision and decision not in ("pertahankan", "keep"):
            log.info("Destinasi dilewati (keputusan=%s): %s", decision, name)
            continue

        key = normalize_text(name)
        if key in seen:
            log.info("Destinasi dilewati (duplikat): %s", name)
            continue
        seen.add(key)

        destinations.append(row)
    return destinations


EVENTS = Dataset(
    "event", "EVENT_CSV_PATH", EVENT_PATTERNS,
    {"nama_event", "judul_event", "judul", "title", "nama"},
    filter_valid_events,
)
DESTINATIONS = Dataset(
    "destinasi", "DESTINATION_CSV_PATH", DESTINATION_PATTERNS,
    {"title", "nama", "nama_destinasi", "name"},
    filter_destinations,
)


def load_events():
    return EVENTS.load()


def load_destinations():
    return DESTINATIONS.load()


# =========================================================
# TANGGAL
# =========================================================

BULAN = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2, "maret": 3, "mar": 3,
    "april": 4, "apr": 4, "mei": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7,
    "agustus": 8, "agu": 8, "ags": 8, "ag": 8, "september": 9, "sep": 9,
    "sept": 9, "oktober": 10, "okt": 10, "november": 11, "nov": 11,
    "desember": 12, "des": 12,
}
NAMA_BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
    "Agustus", "September", "Oktober", "November", "Desember",
]

_MONTH = "|".join(sorted(BULAN, key=len, reverse=True))
ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
RANGE_RE = re.compile(
    rf"(\d{{1,2}})(?:\s+({_MONTH})\b)?(?:\s+(\d{{4}}))?"
    rf"\s*(?:-|–|—|s\.?\s*/?\s*d\.?|sd|hingga|sampai|dan)\s*"
    rf"(\d{{1,2}})\s+({_MONTH})\b\s+(\d{{4}})"
)
SINGLE_RE = re.compile(rf"(\d{{1,2}})\s+({_MONTH})\b\s+(\d{{4}})")
NUMERIC_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y")


def today():
    """Tanggal hari ini menurut WIB."""
    return datetime.now(WIB).date()


def parse_date_range(value):
    """
    Mengubah teks tanggal menjadi (mulai, selesai), atau (None, None).
    Mendukung ISO, rentang ("12-14 Januari 2026"), tanggal Indonesia,
    dan angka (dd/mm/yyyy).
    """

    if not value or value == "-":
        return None, None

    text = str(value).strip().lower()

    iso = []
    for item in ISO_RE.findall(text):
        try:
            iso.append(datetime.strptime(item, "%Y-%m-%d").date())
        except ValueError:
            pass
    if iso:
        return min(iso), max(iso)

    match = RANGE_RE.search(text)
    if match:
        d1, m1, y1, d2, m2, y2 = match.groups()
        try:
            end = date(int(y2), BULAN[m2], int(d2))
            start = date(int(y1 or y2), BULAN[m1 or m2], int(d1))
            if start <= end:
                return start, end
        except (ValueError, KeyError):
            pass

    singles = []
    for d, m, y in SINGLE_RE.findall(text):
        try:
            singles.append(date(int(y), BULAN[m], int(d)))
        except ValueError:
            pass
    if singles:
        return min(singles), max(singles)

    for fmt in NUMERIC_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
            return parsed, parsed
        except ValueError:
            continue

    return None, None


def format_date_indonesia(start, end=None):
    """Contoh: '29 November 2026' atau '27–29 November 2026'."""

    if start is None:
        return "Tanggal belum tersedia"
    if end is None or end == start:
        return f"{start.day} {NAMA_BULAN[start.month - 1]} {start.year}"

    if (start.month, start.year) == (end.month, end.year):
        return f"{start.day}–{end.day} {NAMA_BULAN[end.month - 1]} {end.year}"
    if start.year == end.year:
        return (
            f"{start.day} {NAMA_BULAN[start.month - 1]} – "
            f"{end.day} {NAMA_BULAN[end.month - 1]} {end.year}"
        )
    return (
        f"{start.day} {NAMA_BULAN[start.month - 1]} {start.year} – "
        f"{end.day} {NAMA_BULAN[end.month - 1]} {end.year}"
    )


# =========================================================
# HELPER DATA EVENT
# =========================================================

def get_event_name(row):
    return get_value(row, ["nama_event", "judul_event", "judul", "title", "nama"])


def get_event_date(row):
    return get_value(row, [
        "tanggal_event_ekstrak", "tanggal_event", "tanggal", "date",
    ])


def get_event_location(row):
    return get_value(row, [
        "lokasi_event_ekstrak", "lokasi_event", "lokasi", "location",
    ])


def get_event_category(row):
    return get_value(row, [
        "kategori_event_ekstrak", "kategori_event", "kategori", "category",
    ])


def get_event_description(row):
    return get_value(row, [
        "deskripsi_event", "ringkasan", "deskripsi", "summary", "description",
    ])


def get_event_url(row):
    url = get_value(row, ["url", "link", "link_artikel", "source_url"])
    return url if url.lower().startswith(("http://", "https://")) else "-"


# =========================================================
# TAMPILAN EVENT: JUDUL, LOKASI, DESKRIPSI
# (hanya mengubah tampilan, data CSV tidak diubah)
# =========================================================

REGION = r"(?:kab(?:upaten)?\.?\s*)?kulon\s*progo"
LEADING_REGION_RE = re.compile(
    rf"^\s*[\(\[]?\s*{REGION}\s*[\)\]]?\s*[-–—:|,]\s*", re.IGNORECASE
)
TRAILING_SITE_RE = re.compile(
    rf"\s*[|–—-]\s*(?:{REGION}|pemerintah kabupaten kulon progo|"
    r"pemkab kulon progo|portal\b.*|[\w.-]+\.(?:go\.id|co\.id|com|id))\s*$",
    re.IGNORECASE,
)
DATELINE_RE = re.compile(
    r"^\s*[A-Za-z .]{3,40},\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}\s*[-–—:]\s*"
)
PEMKAB_RE = re.compile(r"pemerintah\s+kabupaten\s+kulon\s*progo", re.IGNORECASE)
TIME_AGO_RE = re.compile(
    r"\s+\d+\s+(?:\d+\s+)?(?:detik|menit|jam|hari|minggu|bulan|tahun)"
    r"\s+yang\s+lalu.*$",
    re.IGNORECASE,
)
SMALL_WORDS = {
    "di", "dan", "yang", "ke", "dari", "untuk", "dengan", "pada", "atau",
    "serta", "ing", "dalam", "oleh", "bagi", "hingga", "sampai", "se",
}


def _slug_words(url):
    """Kata-kata pada slug URL artikel (memuat judul lengkap), atau None."""

    if url == "-":
        return None
    slug = unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1])
    slug = re.sub(r"\.(?:html?|php)$", "", slug, flags=re.IGNORECASE)
    words = [w for w in slug.split("-") if w]
    if len(words) < 2 or sum(c.isalpha() for c in slug) < 6:
        return None
    return words


def _casing_map(row):
    """Singkatan (YRKI, KPHM, CoE) dari teks asli, untuk judul dari slug."""

    text = clean_text(" ".join([
        row.get("judul", ""), row.get("ringkasan", ""),
        row.get("deskripsi_event", ""),
    ]))
    words = re.findall(r"[A-Za-z][A-Za-z0-9]*", text)
    plain = {w.lower() for w in words if w in (w.lower(), w.capitalize())}

    mapping = {}
    for word in words:
        lower = word.lower()
        if lower in ("kulon", "progo") or lower in plain:
            continue
        if (word.isupper() and 2 <= len(word) <= 6) or re.search(r"[a-z][A-Z]", word):
            mapping.setdefault(lower, word)
    return mapping


def _title_from_slug(row):
    words = _slug_words(get_event_url(row))
    if not words:
        return None

    casing = _casing_map(row)

    # Kata yang menempel pada slug dipisah memakai judul asli,
    # mis. "sambanggoyear" -> "Sambanggo" + "Year".
    fragment = clean_text(row.get("judul", "")).split("...")[0]
    original = [t for t in re.split(r"[\s,;:/()]+", fragment) if t]
    pairs = {(a + b).lower(): (a, b) for a, b in zip(original, original[1:])}
    known = {t.lower() for t in original}

    expanded = []
    for word in words:
        if word not in known and word in pairs:
            expanded.extend(pairs[word])
        else:
            expanded.append(word)

    parts, skip = [], False
    for index, word in enumerate(expanded):
        if skip:
            skip = False
            continue
        lower = word.lower()
        following = expanded[index + 1] if index + 1 < len(expanded) else ""

        if re.fullmatch(r"\d{1,2}", word) and re.fullmatch(r"\d{1,2}", following):
            parts.append(f"{word}–{following}")  # "3 4 mei" -> "3–4 Mei"
            skip = True
        elif lower in casing:
            parts.append(casing[lower])
        elif index > 0 and lower in SMALL_WORDS:
            parts.append(lower)
        else:
            parts.append(word[:1].upper() + word[1:].lower())

    # Nama inti kegiatan biasanya berakhir pada tahun penyelenggaraan.
    for index, token in enumerate(parts):
        if index >= 2 and re.fullmatch(r"20\d{2}", token):
            return " ".join(parts[:index + 1])
    return " ".join(parts)


def _title_from_name(row):
    """Cadangan bila URL tidak memuat slug judul."""

    name = clean_text(get_event_name(row))
    if name in ("", "-"):
        return None

    name = name.split("...")[0]  # "<judul terpotong>... <isi artikel>"
    name = TIME_AGO_RE.sub("", name)
    for _ in range(2):
        name = LEADING_REGION_RE.sub("", name)
        name = TRAILING_SITE_RE.sub("", name)
    name = name.strip(" -–—|:,")
    return name.title() if name.isupper() else name


# Judul berita sering berbentuk kalimat: "<pelaku> <kata kerja> <nama event>
# <kata kerja> ...". Hanya nama event yang ditampilkan.
LEAD_VERBS = (
    r"meriahkan|memeriahkan|ramaikan|meramaikan|gelar|menggelar|luncurkan|"
    r"meluncurkan|buka|membuka|tandai|menandai|sambut|menyambut|hadirkan|"
    r"menghadirkan|sukseskan|menyukseskan|resmikan|meresmikan"
)
LEAD_VERB_RE = re.compile(rf"^(?:\S+\s+){{1,5}}?(?:{LEAD_VERBS})\s+(?=\S+\s+\S)", re.IGNORECASE)
TRAIL_VERB_RE = re.compile(
    r"\s+(?:perkuat|memperkuat|tingkatkan|meningkatkan|untuk|guna|demi|"
    r"dalam\s+rangka|sebagai|dengan|yang)\b.*$",
    re.IGNORECASE,
)


def core_title(name):
    """'Ribuan Pelari Meriahkan Kulon Progo Half Marathon 2026' -> 'Kulon Progo Half Marathon 2026'."""

    match = LEAD_VERB_RE.match(name)
    if match:
        name = name[match.end():]

    cut = TRAIL_VERB_RE.sub("", name).strip()
    if len(cut.split()) >= 2:  # jangan sampai judul tinggal satu kata
        name = cut

    words = name.split()
    while words and words[-1].lower() in SMALL_WORDS:
        words.pop()
    return " ".join(words) or name


def get_display_title(row):
    """Judul ringkas berupa nama inti kegiatan, bukan judul berita panjang."""

    name = _title_from_slug(row) or _title_from_name(row)
    if not name:
        return "Event Wisata"

    name = core_title(PEMKAB_RE.sub("Pemkab Kulon Progo", name))

    if len(name) > 60:
        kept = []
        for word in name.split():
            if len(" ".join(kept + [word])) > 56:
                break
            kept.append(word)
        while kept and kept[-1].lower() in SMALL_WORDS:
            kept.pop()
        name = " ".join(kept) + "..."
    return name or "Event Wisata"


LOCATION_CUT_RE = re.compile(
    r"[\s,;]+(?:berhasil|akan|ini|itu|yang|sudah|telah|dengan|kegiatan|"
    r"untuk|dalam|pada|serta|kemudian|bertujuan|dimeriahkan|terselenggara|"
    r"menjadi|digelar|terdapat|salah\s+satu|dilaksanakan|diselenggarakan|"
    r"melaksanakan|menggelar)\b.*$",
    re.IGNORECASE,
)
ADMIN_LABEL_RE = re.compile(
    r"\b(?:kalurahan|kelurahan|kapanewon|kecamatan|padukuhan|dusun)\s+", re.IGNORECASE
)
REGION_ONLY_RE = re.compile(
    r"(?:kab(?:upaten)?\.?\s*)?kulon\s*progo|(?:d\.?i\.?\s*)?yogyakarta|diy", re.IGNORECASE
)
TRAILING_REGION_RE = re.compile(
    r"(?<!Pemkab)\s+(?:kab(?:upaten)?\.?\s+)?kulon\s*progo\s*$", re.IGNORECASE
)
DAY_NAMES = r"(?:senin|selasa|rabu|kamis|jumat|jum'at|sabtu|minggu)"
MONTH_NAMES = r"(?:" + "|".join(m.lower() for m in NAMA_BULAN) + r")"


def _is_date_part(part):
    part = part.strip().lower()
    return bool(
        re.fullmatch(DAY_NAMES, part)
        or re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", part)
        or re.search(rf"\b\d{{1,2}}\b.*\b{MONTH_NAMES}\b", part)
        or re.fullmatch(rf"{MONTH_NAMES}(?:\s+\d{{4}})?", part)
    )


def get_display_location(row):
    """
    Lokasi yang dirapikan. Hasil ekstraksi sering memuat sisa kalimat,
    tanggal, atau terpotong; bagian tersebut dibuang hanya pada tampilan.
    """

    original = PEMKAB_RE.sub("Pemkab Kulon Progo", clean_text(get_event_location(row)))
    if not original:
        return "Lokasi belum tersedia"

    text = re.sub(
        r"^(?:bertempat\s+di|lokasi\s*:?|di)\s+", "", original, flags=re.IGNORECASE
    )
    text = re.sub(r"\([^)]*\d[^)]*\)", "", text)  # (12/4/2025), (500m)
    text = re.sub(r"\([^)]*$", "", text)          # kurung terpotong

    cut = LOCATION_CUT_RE.sub("", text)
    was_cut = cut != text

    parts, seen = [], set()
    for part in re.split(r"\s*,\s*", cut.strip(" ,;")):
        key = normalize_text(part)
        if key and key not in seen and not _is_date_part(part):
            seen.add(key)
            parts.append(part.strip())

    # Data lokasi sering terpotong di akhir: buang bagian terakhir yang tak utuh.
    if len(parts) > 1 and ((len(original) >= 80 and not was_cut) or len(parts[-1]) <= 4):
        parts.pop()

    # Dipertajam: buang label wilayah (Kalurahan, Kapanewon) dan nama
    # kabupaten yang sudah pasti Kulon Progo; sisakan venue + area saja.
    sharp = []
    for part in parts:
        part = ADMIN_LABEL_RE.sub("", part).strip()
        if REGION_ONLY_RE.fullmatch(part):
            continue
        part = TRAILING_REGION_RE.sub("", part).strip()
        if part:
            sharp.append(part)
    parts = sharp or parts

    parts = [p.title() if p.islower() else p[:1].upper() + p[1:] for p in parts]
    return shorten(", ".join(parts[:3]) or original, 100)


def clean_description(text):
    """Membuang tautan, emoji, markdown, dan boilerplate berita di awal."""

    if not text or text == "-":
        return ""

    text = re.sub(r"https?://\S+", "", clean_text(text))
    text = re.sub(r"\s+", " ", text).strip()

    for _ in range(2):
        text = DATELINE_RE.sub("", text)
        text = LEADING_REGION_RE.sub("", text)

    text = re.sub(r"\bbaca juga\b.*$", "", text, flags=re.IGNORECASE)
    return PEMKAB_RE.sub("Pemkab Kulon Progo", text).strip()


# Tanggal dan lokasi sudah tampil di baris sendiri, jadi tidak diulang
# di deskripsi supaya ruangnya dipakai untuk isi acara.
DAY_DATE_RE = re.compile(
    rf"\s*(?:pada\s+)?(?:hari\s+)?{DAY_NAMES}?\s*\(\s*\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}\s*\)",
    re.IGNORECASE,
)
# "..., bertempat di X" dan "..., yang digelar di X" dibuang seluruhnya.
FULL_DATE_RE = re.compile(
    rf"\s*(?:pada\s+)?(?:hari\s+)?(?:{DAY_NAMES},?\s*)?\d{{1,2}}\s+{MONTH_NAMES}\s+\d{{4}}\s*,?",
    re.IGNORECASE,
)
VENUE_TAIL_RE = re.compile(
    r",?\s*(?:(?:yang\s+)?(?:bertempat|berlokasi)|yang\s+(?:digelar|dilaksanakan|"
    r"diselenggarakan|berlangsung))\s+di\b.*$",
    re.IGNORECASE,
)
# "konferensi pers digelar di X" -> "konferensi pers digelar" (kata kerja dipertahankan).
VENUE_VERB_RE = re.compile(
    r"\b(digelar|dilaksanakan|diselenggarakan|berlangsung)\s+di\b.*$", re.IGNORECASE
)


def first_sentences(text, max_length, enough=70):
    """Kalimat pertama; kalimat berikutnya ditambah bila masih pendek."""

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return ""

    result = sentences[0]
    for sentence in sentences[1:]:
        if len(result) >= enough or len(result) + 1 + len(sentence) > max_length:
            break
        result += " " + sentence
    return result


def shorten_description(text, max_length=160, empty="Informasi event belum tersedia."):
    """Ringkasan satu kalimat berisi apa dan siapa, tanpa tanggal/lokasi."""

    text = clean_description(text)
    text = re.sub(r"\bKabupaten\s+Kulon\s*Progo\b", "Kulon Progo", text)
    text = re.sub(r"\s+([.,;!?])", r"\1", FULL_DATE_RE.sub(" ", DAY_DATE_RE.sub("", text)))

    result = first_sentences(text, max_length)
    if not result:
        return empty

    trimmed = VENUE_TAIL_RE.sub("", result).rstrip(" ,;")
    if trimmed == result:
        trimmed = VENUE_VERB_RE.sub(r"\1", result).rstrip(" ,;")
    if len(trimmed) >= 40:
        result = trimmed

    if len(result) > max_length:
        # Lebih baik berhenti di koma/titik koma daripada di tengah frasa.
        window = result[:max_length]
        cut = max(window.rfind(", "), window.rfind("; "))
        result = window[:cut] if cut >= max_length * 0.5 else shorten(result, max_length)

    result = re.sub(r"\s+", " ", result).strip()
    result = re.sub(r"[,;]+\s*\.", ".", result)  # "Kulon Progo,." -> "Kulon Progo."

    if not result.endswith((".", "!", "?", "…")):
        result += "."
    return result


# =========================================================
# STATUS & EMOJI EVENT
# =========================================================

UPCOMING, TODAY, YESTERDAY, PAST, UNDATED = (
    "upcoming", "today", "yesterday", "past", "undated"
)

STATUS_LABEL = {
    UPCOMING: "🟢 Akan Datang",
    TODAY: "🟡 Hari Ini",
    YESTERDAY: "🔴 Kemarin",
    PAST: "⚪ Lampau",
    UNDATED: "⚪ Informasi tanggal",
}


def get_event_status(row, now):
    """Mengembalikan (status, tanggal_mulai, tanggal_selesai)."""

    start, end = parse_date_range(get_event_date(row))

    if start is None:
        return UNDATED, None, None
    if start > now:
        return UPCOMING, start, end
    if end >= now:
        return TODAY, start, end  # berlangsung hari ini (termasuk multi-hari)
    if end == now - timedelta(days=1):
        return YESTERDAY, start, end
    return PAST, start, end


# Urutan penting: aturan yang lebih spesifik ditaruh di atas.
# Setiap kata dicocokkan dari awal kata (regex), jadi "seni\b" tidak cocok "senin".
EMOJI_RULES = [
    ("🏮", ["lampion"]),
    ("🌅", ["sunset", "senja", "sunrise"]),
    ("🏃", ["lari", "pelari", "marathon", "maraton", "running"]),
    ("🚴", ["sepeda", "gowes", "cycling"]),
    ("🪁", ["layang"]),
    ("🎣", ["mancing", "pancing"]),
    ("🎶", ["musik", "konser", "dangdut", "campursari"]),
    ("🎭", ["tari", "teater", "wayang", "ketoprak", "kesenian", "bendrong",
            "jathilan", "karawitan", r"seni\b", "budaya"]),
    ("🤝", ["rapat", "rakor", "koordinasi", "konferensi", "sosialisasi", "audiensi"]),
    ("📱", ["digital", "aplikasi", "teknologi", r"gora\b", r"pay\b"]),
    ("🎓", ["seminar", "workshop", "pelatihan", "bimtek", "diklat"]),
    ("🏆", ["lomba", "kejuaraan", "turnamen", "kompetisi", "juara"]),
    ("🍜", ["kuliner", "makanan", "food", "bazar"]),
    ("🛍️", ["pasar", "expo", "pameran", "umkm"]),
    ("🌱", ["tanam", "bibit", "tani", "panen", "tuk tumuwuh"]),
    ("🏖️", ["pantai", "laut", "bahari"]),
    ("🏅", ["sport", "olahraga"]),
    ("🎪", ["festival", "karnaval", "pawai"]),
]


def get_event_emoji(row):
    # Judul diutamakan; kategori (sering "budaya, seni, hiburan" untuk
    # hampir semua event) hanya dipakai bila judul tidak cocok aturan apa pun.
    for source in (get_display_title(row), get_event_category(row)):
        text = normalize_text(source)
        for emoji, words in EMOJI_RULES:
            if re.search(r"(?<![a-z0-9])(?:" + "|".join(words) + ")", text):
                return emoji
    return "🎉"


def dedupe_events(events):
    """Membuang event ganda (judul ringkas dan tanggal sama)."""

    seen, result = set(), []
    for row in events:
        key = (normalize_text(get_display_title(row)), normalize_text(get_event_date(row)))
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


# =========================================================
# FORMAT PESAN EVENT (dipakai oleh Daftar Event, Cari Event,
# dan event terkait destinasi agar tampilannya konsisten)
# =========================================================

SEPARATOR = "\n\n━━━━━━━━━━━━━━\n\n"


def format_event_card(row, now):
    status, start, end = get_event_status(row, now)

    title = escape(get_display_title(row))
    location = escape(get_display_location(row))
    description = escape(shorten_description(get_event_description(row)))
    tanggal = escape(format_date_indonesia(start, end))

    message = (
        f"<b>{STATUS_LABEL[status]}</b>\n"
        f"{get_event_emoji(row)} <b>{title}</b>\n"
        f"📅 {tanggal}\n"
        f"📍 {location}\n"
        f"{description}\n"
    )

    url = get_event_url(row)
    if url != "-":
        message += f"🔗 <a href=\"{escape(url, quote=True)}\">Baca selengkapnya</a>"

    return message.rstrip()


def build_messages(header, blocks, footer=""):
    """Menyusun pesan; dipecah bila melebihi batas panjang Telegram."""

    messages, current = [], header

    for index, block in enumerate(blocks):
        piece = block + (SEPARATOR if index < len(blocks) - 1 else "")
        if len(current) + len(piece) > MESSAGE_LIMIT and current.strip():
            messages.append(current.rstrip())
            current = ""
        current += piece

    if footer:
        if len(current) + len(footer) > MESSAGE_LIMIT:
            messages.append(current.rstrip())
            current = ""
        current += footer

    if current.strip():
        messages.append(current.rstrip())
    return messages


# =========================================================
# LOGIKA DAFTAR EVENT & PENCARIAN EVENT
# =========================================================

def build_event_list(events, now):
    """
    Maksimal 5 event: 2 hari ini + 3 akan datang (hari ini ditampilkan
    lebih dulu). Slot kosong diisi event akan datang lain, lalu yang sudah
    lewat. Tanpa pagination.
    """

    groups = {UPCOMING: [], TODAY: [], YESTERDAY: [], PAST: []}
    for row in dedupe_events(events):
        status, start, end = get_event_status(row, now)
        if status != UNDATED:
            groups[status].append((start, end, row))

    groups[UPCOMING].sort(key=lambda item: item[0])
    groups[TODAY].sort(key=lambda item: item[0])
    groups[YESTERDAY].sort(key=lambda item: get_display_title(item[2]).lower())
    groups[PAST].sort(key=lambda item: item[1], reverse=True)

    rows = {status: [item[2] for item in items] for status, items in groups.items()}

    selected = rows[TODAY][:MAX_TODAY] + rows[UPCOMING][:MAX_UPCOMING]
    chosen = {id(row) for row in selected}

    leftovers = (
        rows[UPCOMING][MAX_UPCOMING:] + rows[TODAY][MAX_TODAY:]
        + rows[YESTERDAY] + rows[PAST]
    )
    for row in leftovers:
        if len(selected) >= MAX_EVENT_LIST:
            break
        if id(row) not in chosen:
            selected.append(row)
            chosen.add(id(row))

    return selected[:MAX_EVENT_LIST]


def search_events(events, keyword, now):
    """
    Cocok bila semua kata kunci ada pada judul, tanggal, lokasi, kategori,
    atau deskripsi. Jika tidak ada yang cocok penuh, ditampilkan yang
    cocok sebagian terbanyak.
    """

    tokens = normalize_text(keyword).split()
    if not tokens:
        return []

    indexed = []
    for row in dedupe_events(events):
        status, start, end = get_event_status(row, now)
        text = normalize_text(" ".join([
            get_display_title(row),
            get_event_date(row),
            format_date_indonesia(start, end),
            get_event_location(row),
            get_event_category(row),
            get_event_description(row),
        ]))
        indexed.append((row, status, start, end, text))

    hits = [item for item in indexed if all(t in item[4] for t in tokens)]

    if not hits and len(tokens) > 1:
        scores = [(sum(t in item[4] for t in tokens), item) for item in indexed]
        best = max((score for score, _ in scores), default=0)
        if best:
            hits = [item for score, item in scores if score == best]

    def order(item):
        _, status, start, end, _ = item
        if status in (TODAY, UPCOMING):
            return (0, start.toordinal())
        if status in (YESTERDAY, PAST):
            return (1, -end.toordinal())
        return (2, 0)

    return [item[0] for item in sorted(hits, key=order)]


# =========================================================
# LOGIKA DESTINASI: DATA & KATEGORI
# =========================================================

def get_destination_name(row):
    return get_value(row, ["title", "nama", "nama_destinasi", "name"])


def get_destination_address(row):
    return get_value(row, ["address", "alamat", "lokasi"])


def get_destination_description(row):
    return get_value(row, ["description", "deskripsi", "ringkasan", "summary", "about"])


CATEGORY_RULES = [
    ("🏖️ Pantai", ["pantai", "beach", "pesisir", "laguna", "muara"]),
    ("🏡 Desa Wisata", ["desa wisata", "kampung wisata", "kampung", "desa"]),
    ("💦 Wisata Air", [
        "curug", "air terjun", "waterfall", "waduk", "reservoir",
        "bendungan", "telaga", "danau", "lake", "embung", "sungai",
        "river", "kolam", "tubing", "rafting", "arung jeram",
        "water", "tirta", "sendang", "banyu", "mata air",
    ]),
    ("⛰️ Panorama", [
        "puncak", "view", "bukit", "panorama", "menoreh", "sunset",
        "sunrise", "pandang", "kaki langit", "negeri di atas awan",
    ]),
    ("🌿 Wisata Alam", [
        "hutan", "kebun", "goa", "gua", "alam", "taman", "cagar",
    ]),
]
DEFAULT_CATEGORY = "🌿 Wisata Alam"


def _match_category(text):
    text = normalize_text(text)
    for category, words in CATEGORY_RULES:
        for word in words:
            # kata kunci harus berada di awal kata ("view" bukan "review")
            if re.search(rf"(?<![a-z0-9]){re.escape(normalize_text(word))}", text):
                return category
    return None


def classify_destination(row):
    """
    Kategori dari kolom kategori dataset (categoryName) lebih dulu, lalu
    dari nama destinasi. Alamat sengaja tidak dipakai karena sering memuat
    kata seperti "Jl. Pantai ..." yang menyesatkan.
    """

    return (
        _match_category(get_value(row, ["categoryname", "kategori", "category"]))
        or _match_category(get_destination_name(row))
        or DEFAULT_CATEGORY
    )


def get_category_destinations(destinations, category):
    return [row for row in destinations if classify_destination(row) == category]


# =========================================================
# LOGIKA DESTINASI: PENCARIAN
# =========================================================

# Kata umum tidak boleh menjadi dasar kemiripan (typo); kalau tidak,
# "pantai glagah" akan dianggap mirip "Pantai Mlarangan Asri".
GENERIC_WORDS = {
    "pantai", "wisata", "desa", "kampung", "waduk", "curug", "bukit",
    "puncak", "taman", "kebun", "goa", "gua", "kafe", "cafe", "warung",
    "kopi", "resto", "rumah", "makan", "kedai", "the", "di", "dan",
    "kulon", "progo", "kulonprogo", "obyek", "objek",
}
STRONG_SCORE = 0.85


def _fuzzy_score(keyword, title):
    """Toleransi typo per kata khas (bukan kata umum)."""

    key_words = [w for w in keyword.split() if w not in GENERIC_WORDS]
    title_words = title.split()
    if not key_words or not title_words:
        return 0.0

    scores = []
    for word in key_words:
        if len(word) < 4:
            return 0.0
        best = max(SequenceMatcher(None, word, t).ratio() for t in title_words)
        if best < 0.8:
            return 0.0
        scores.append(best)

    return min(sum(scores) / len(scores), 0.84)  # selalu di bawah STRONG_SCORE


def score_destination(keyword, title):
    """Skor kecocokan 0..1 antara kata kunci dan judul destinasi."""

    if not keyword or not title:
        return 0.0

    key_compact = keyword.replace(" ", "")
    title_compact = title.replace(" ", "")
    key_words = keyword.split()

    if keyword == title or key_compact == title_compact:
        return 1.0
    if title.startswith(keyword):
        return 0.95
    if re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", title):
        return 0.9
    if all(word in title.split() for word in key_words):
        return 0.88
    if len(key_compact) >= 4 and key_compact in title_compact:
        return 0.86
    if len(key_compact) >= 4 and all(word in title for word in key_words):
        return 0.8
    return _fuzzy_score(keyword, title)


def find_destinations(keyword, destinations, category=None):
    """
    Mencari di SELURUH destinasi. Kategori hanya memberi sedikit prioritas
    dan tidak pernah menyaring. Hasil: [(skor, row)] dari yang terbaik.
    """

    keyword = normalize_text(keyword)
    results = []

    for row in destinations:
        title = normalize_text(get_destination_name(row))
        score = score_destination(keyword, title)
        if score <= 0:
            continue
        if category and classify_destination(row) == category:
            score += 0.02
        results.append((score - len(title) * 1e-5, row))

    return sorted(results, key=lambda item: item[0], reverse=True)


def is_ambiguous(results):
    """True bila beberapa destinasi sama-sama cocok dan tidak ada yang jelas."""

    if len(results) < 2:
        return False
    top, second = results[0][0], results[1][0]
    return top < 0.99 and second >= STRONG_SCORE and top - second < 0.04


# =========================================================
# LOGIKA DESTINASI: DETAIL
# =========================================================

# (emoji judul, emoji deskripsi, emoji event)
THEMES = {
    "🏖️ Pantai": ("🏖️", "🌴", "🎉"),
    "🌿 Wisata Alam": ("🌿", "🍃", "🎉"),
    "🏡 Desa Wisata": ("🏡", "🌾", "🎊"),
    "💦 Wisata Air": ("💦", "🌊", "🎉"),
    "⛰️ Panorama": ("⛰️", "🌄", "🎉"),
}


def get_maps_url(row):
    """
    Urutan: tautan Google Maps dari dataset, koordinat dataset, lalu
    pencarian dari nama + alamat (hanya bila keduanya tersedia).
    """

    for column in ("google_maps_url", "maps_url", "link_maps", "url", "placeurl", "place_url"):
        value = row.get(column, "").lower()
        if value.startswith("http") and any(
            marker in value for marker in
            ("google.com/maps", "maps.google", "maps.app.goo.gl", "goo.gl/maps", "g.page")
        ):
            return row[column]

    lat = get_value(row, ["latitude", "lat"])
    lng = get_value(row, ["longitude", "lng", "lon", "long"])

    if "-" in (lat, lng):
        match = re.search(
            r"lat\D{0,6}(-?\d+\.\d+).*?(?:lng|lon)\D{0,6}(-?\d+\.\d+)",
            row.get("location", ""), re.IGNORECASE | re.DOTALL,
        )
        if match:
            lat, lng = match.groups()

    try:
        float(lat), float(lng)
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
    except ValueError:
        pass

    name, address = get_destination_name(row), get_destination_address(row)
    if "-" not in (name, address):
        return "https://www.google.com/maps/search/?api=1&query=" + quote(f"{name}, {address}")
    return None


def get_related_events(destination, events, now):
    """
    Event hari ini/mendatang yang menyebut nama destinasi pada lokasi atau
    judul (pencocokan kata utuh), agar event tidak asal dikaitkan.
    """

    name = normalize_text(get_destination_name(destination))
    if not name:
        return []

    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])")
    related = []

    for row in dedupe_events(events):
        status, start, _ = get_event_status(row, now)
        if status not in (TODAY, UPCOMING):
            continue
        if pattern.search(normalize_text(get_event_location(row))) or \
                pattern.search(normalize_text(get_display_title(row))):
            related.append((start, row))

    return [row for _, row in sorted(related, key=lambda item: item[0])]


def format_destination_detail(destination, events, now):
    """Detail destinasi; semua informasi berasal dari dataset."""

    name = get_destination_name(destination)
    address = get_destination_address(destination)
    category = classify_destination(destination)
    title_emoji, description_emoji, event_emoji = THEMES.get(category, THEMES[DEFAULT_CATEGORY])

    message = f"<b>{title_emoji} {escape(name)}</b>\n\n"
    message += f"📍 {escape(address) if address != '-' else 'Alamat belum tersedia'}\n"

    maps_url = get_maps_url(destination)
    if maps_url:
        message += f"<a href=\"{escape(maps_url, quote=True)}\">🗺️ Lihat Google Maps</a>\n"

    description = clean_description(get_destination_description(destination))
    if description:
        short = shorten(first_sentences(description, 220, enough=110), 220)
        message += f"\n{description_emoji} {escape(short)}\n"

    related = get_related_events(destination, events, now) if events else []
    if related:
        cards = [format_event_card(row, now) for row in related[:MAX_RELATED_EVENTS]]
        message += f"\n<b>{event_emoji} Event di Destinasi</b>\n\n" + SEPARATOR.join(cards)

    return message.rstrip()


# =========================================================
# PENGINGAT EVENT H-1 & SCHEDULER
# (scheduler.py yang menjadwalkan dan mengirim; bot.py yang
# menyediakan isi pesannya agar tampilannya sama dengan menu)
# =========================================================

SCHEDULER = None  # modul scheduler.py, diisi oleh main()


def load_scheduler():
    """Memuat scheduler.py; bot tetap jalan bila file tidak ditemukan."""

    for root in (BASE_DIR, BASE_DIR.parent):
        if str(root) not in sys.path:
            sys.path.append(str(root))

    errors = []
    for name in ("scraping.scheduler", "scheduler"):
        try:
            return importlib.import_module(name)
        except Exception as error:  # noqa: BLE001
            errors.append(f"{name}: {error}")

    log.warning("scheduler.py tidak dapat dimuat, notifikasi nonaktif. %s", " | ".join(errors))
    return None


def format_reminder(row, start, end):
    """Pesan pengingat H-1."""

    message = (
        "🔔 <b>PENGINGAT EVENT H-1</b>\n\n"
        "Halo, Sobat WisataKP! 👋\n\n"
        "Jangan sampai ketinggalan event seru besok!\n\n"
        f"📌 <b>Nama Event:</b> {escape(get_display_title(row))}\n"
        f"📅 <b>Tanggal:</b> {escape(format_date_indonesia(start, end))}\n"
        f"📍 <b>Lokasi:</b> {escape(get_display_location(row))}\n\n"
        "ℹ️ <b>Tentang Event:</b>\n"
        f"{escape(shorten_description(get_event_description(row)))}\n\n"
    )

    url = get_event_url(row)
    if url != "-":
        message += (
            "🔗 <b>Informasi selengkapnya:</b> "
            f"<a href=\"{escape(url, quote=True)}\">Baca di sini</a>\n\n"
        )

    return message + "Yuk, catat tanggalnya dan nikmati keseruannya! ✨"


def get_h1_reminders():
    """
    Event yang dimulai besok, sebagai [(id_event, pesan_html)].
    Dipanggil scheduler; id_event dipakai agar satu event hanya diingatkan sekali.
    """

    events = load_events()
    if not events:
        return []

    tomorrow = today() + timedelta(days=1)
    reminders = []

    for row in dedupe_events(events):
        start, end = parse_date_range(get_event_date(row))
        if start != tomorrow:
            continue

        url = get_event_url(row)
        event_id = (
            url.lower().rstrip("/") if url != "-"
            else f"{normalize_text(get_display_title(row))}|{start.isoformat()}"
        )
        reminders.append((event_id, format_reminder(row, start, end)))

    return reminders


def set_subscription(update, active):
    """Daftarkan / hapus chat dari penerima pengingat."""

    if SCHEDULER is None or update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    if active:
        SCHEDULER.add_subscriber(chat_id)
    else:
        SCHEDULER.remove_subscriber(chat_id)


async def post_init(application):
    if SCHEDULER is None or os.getenv("DISABLE_SCHEDULER") == "1":
        log.info("Scheduler tidak dijalankan.")
        return
    await SCHEDULER.start_scheduler(application, reminder_callback=get_h1_reminders)


async def post_shutdown(application):
    if SCHEDULER is not None:
        await SCHEDULER.stop_scheduler(application)


# =========================================================
# PENGIRIMAN PESAN TELEGRAM
# =========================================================

async def reply(update, text, markup=MENU):
    """Kirim pesan HTML; coba ulang sekali saat timeout."""

    for attempt in (1, 2):
        try:
            return await update.effective_message.reply_text(
                text, parse_mode=ParseMode.HTML, reply_markup=markup, **NO_PREVIEW
            )
        except BadRequest as error:
            if "parse entities" not in str(error).lower():
                raise
            log.warning("Gagal parse HTML, dikirim sebagai teks biasa.")
            return await update.effective_message.reply_text(
                re.sub(r"<[^>]+>", "", text), reply_markup=markup
            )
        except (TimedOut, NetworkError):
            if attempt == 2:
                raise
            log.warning("Timeout saat mengirim pesan, mencoba ulang...")


async def safe_edit(query, text, markup=None):
    """Edit pesan; 'Message is not modified' diabaikan."""

    try:
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=markup, **NO_PREVIEW
        )
    except BadRequest as error:
        if "message is not modified" not in str(error).lower():
            raise
        log.info("Pesan tidak berubah, edit dilewati.")


# =========================================================
# HANDLER: START & MENU UTAMA
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = None
    set_subscription(update, True)

    await reply(
        update,
        "👋 <b>Selamat datang di WisataKP!</b>\n\n"
        "Temukan informasi event dan destinasi wisata "
        "di Kulon Progo.\n\n"
        "🌊 Jelajahi pantai\n"
        "🌿 Temukan wisata alam\n"
        "🏡 Kunjungi desa wisata\n"
        "🎉 Cari event menarik\n\n"
        "🔔 Kamu akan mendapat pengingat sehari sebelum event berlangsung. "
        "Ketik /berhenti untuk menghentikannya.\n\n"
        "Silakan pilih menu berikut:",
    )


async def berhenti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_subscription(update, False)
    await reply(
        update,
        "🔕 Pengingat event dihentikan.\n"
        "Ketik /start jika ingin mengaktifkannya lagi.",
    )


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = None

    await reply(
        update,
        "🌿 <b>MENU UTAMA WISATAKP</b>\n\n"
        "Silakan pilih fitur yang ingin digunakan.",
    )


# =========================================================
# HANDLER: DAFTAR EVENT
# =========================================================

async def daftar_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = None

    events = load_events()
    if events is None:
        await reply(update, MSG_EVENT_ERROR)
        return

    now = today()
    selected = build_event_list(events, now)

    if not selected:
        await reply(update, "📅 Belum ada event yang dapat ditampilkan.")
        return

    cards = [format_event_card(row, now) for row in selected]
    for message in build_messages("📅 <b>EVENT KULON PROGO</b>\n\n", cards):
        await reply(update, message)


# =========================================================
# HANDLER: CARI EVENT
# =========================================================

async def cari_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = MODE_SEARCH

    await reply(
        update,
        "🔍 <b>Cari Event</b>\n\n"
        "Ketik nama event, lokasi, kategori, "
        "atau kata kunci yang ingin kamu cari.\n\n"
        "Contoh: festival, pantai, seni, olahraga.\n\n"
        "Kamu bisa mencari berkali-kali. "
        "Ketik <b>menu</b> untuk kembali.",
    )


async def proses_pencarian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Mode tetap MODE_SEARCH agar pengguna bisa langsung mencari lagi.
    keyword = update.message.text.strip()

    events = load_events()
    if events is None:
        await reply(update, MSG_EVENT_ERROR)
        return

    now = today()
    hasil = search_events(events, keyword, now)

    if not hasil:
        await reply(
            update,
            "🔎 <b>HASIL PENCARIAN</b>\n\n"
            f"Kata kunci: <b>{escape(keyword)}</b>\n\n"
            "Event tidak ditemukan.\n"
            "Coba kata kunci lain.",
        )
        return

    header = (
        "🔎 <b>HASIL PENCARIAN</b>\n"
        f"Kata kunci: <b>{escape(keyword)}</b>\n"
        f"Ditemukan {len(hasil)} event\n\n\n"
    )

    footer = ""
    if len(hasil) > MAX_SEARCH_RESULTS:
        footer = (
            f"\n\n<i>Menampilkan {MAX_SEARCH_RESULTS} dari {len(hasil)} hasil. "
            "Gunakan kata kunci yang lebih spesifik.</i>"
        )
    footer += "\n\n<i>Ketik kata kunci lain untuk mencari lagi.</i>"

    cards = [format_event_card(row, now) for row in hasil[:MAX_SEARCH_RESULTS]]
    for message in build_messages(header, cards, footer):
        await reply(update, message)


# =========================================================
# HANDLER: WISATA
# =========================================================

def category_keyboard(selected=None):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"✅ {category}" if category == selected else category,
            callback_data=f"wiscategory_{index}",
        )]
        for index, category in enumerate(KATEGORI_WISATA)
    ])


async def menu_wisata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = MODE_WISATA_MENU
    context.user_data["wisata_category"] = None

    await reply(
        update,
        "🏞️ <b>JELAJAH WISATA KULON PROGO</b>\n\n"
        "Pilih kategori wisata yang ingin kamu jelajahi.",
        markup=category_keyboard(),
    )


async def wisata_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tombol kategori: pengguna memilih kategori, lalu mengetik nama wisata."""

    query = update.callback_query
    await query.answer()

    try:
        category = KATEGORI_WISATA[int(query.data.split("_")[-1])]
    except (ValueError, IndexError):
        return

    context.user_data["wisata_category"] = category
    context.user_data["mode"] = MODE_WISATA

    destinations = load_destinations()
    if destinations is None:
        await safe_edit(query, MSG_DESTINASI_ERROR, category_keyboard(category))
        return

    in_category = get_category_destinations(destinations, category)
    examples = [get_destination_name(row) for row in in_category[:5]]

    examples_text = ""
    if examples:
        examples_text = (
            f"\n\nContoh destinasi ({len(in_category)} tersedia):\n"
            + "\n".join(f"• {escape(name)}" for name in examples)
        )

    await safe_edit(
        query,
        f"<b>{escape(category)}</b>\n\n"
        "Silakan ketik nama destinasi wisata yang ingin kamu cari."
        f"{examples_text}\n\n"
        "Ketik <b>kategori</b> untuk memilih kategori lain "
        "atau <b>menu</b> untuk kembali ke menu utama.",
        category_keyboard(category),
    )


async def proses_pencarian_destinasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()
    category = context.user_data.get("wisata_category")

    destinations = load_destinations()
    if destinations is None:
        # Dataset gagal dimuat: bukan "destinasi tidak ditemukan".
        await reply(update, MSG_DESTINASI_ERROR)
        return

    matches = find_destinations(keyword, destinations, category)

    if not matches:
        await reply(
            update,
            "🔎 <b>Destinasi belum ditemukan 🥹</b>\n\n"
            "Coba periksa kembali nama destinasi "
            "atau gunakan nama yang lebih singkat.",
        )
        return

    if is_ambiguous(matches):
        names = [get_destination_name(row) for _, row in matches[:8]]
        text = (
            f"🔎 Ada beberapa destinasi yang cocok dengan <b>{escape(keyword)}</b>:\n\n"
            + "\n".join(f"• {escape(name)}" for name in names)
        )
        if len(matches) > len(names):
            text += f"\n• ...dan {len(matches) - len(names)} lainnya"
        await reply(update, text + "\n\nKetik nama lengkap salah satunya untuk melihat detailnya.")
        return

    detail = format_destination_detail(matches[0][1], load_events(), today())

    similar = [
        get_destination_name(row)
        for score, row in matches[1:4] if score >= STRONG_SCORE
    ]
    if similar:
        detail += f"\n\n<i>Mungkin juga maksudmu: {escape(', '.join(similar))}</i>"

    await reply(update, detail)


# =========================================================
# HANDLER: BANTUAN
# =========================================================

async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = None

    await reply(
        update,
        "❓ <b>BANTUAN WISATAKP</b>\n\n"
        "📅 <b>Daftar Event</b>\n"
        "Menampilkan hingga 5 event: 3 yang akan datang "
        "dan 2 yang berlangsung hari ini.\n\n"
        "🔍 <b>Cari Event</b>\n"
        "Mencari event berdasarkan nama, lokasi, "
        "kategori, atau kata kunci. Kamu bisa mencari "
        "berkali-kali tanpa memilih menu lagi.\n\n"
        "🏞️ <b>Wisata</b>\n"
        "Pilih kategori wisata lalu ketik nama "
        "destinasi (boleh sebagian saja) untuk melihat informasi wisata, "
        "lokasi, Google Maps, dan event terkait. "
        "Ketik <b>kategori</b> untuk memilih kategori lain.\n\n"
        "🔔 <b>Pengingat</b>\n"
        "Bot mengirim pengingat sehari sebelum event berlangsung. "
        "Ketik /berhenti untuk menghentikan, /start untuk mengaktifkan lagi.\n\n"
        "🔁 <b>Berpindah menu</b>\n"
        "Tekan tombol menu kapan saja, atau ketik <b>menu</b>. "
        "Perintah /start mengulang dari awal.\n\n"
        "Pilih menu di bawah untuk mulai menggunakan bot.",
    )


# =========================================================
# HANDLER: ROUTER PESAN TEKS
# =========================================================

MENU_ACTIONS = {
    MENU_DAFTAR: daftar_event,
    MENU_CARI: cari_event,
    MENU_WISATA: menu_wisata,
    MENU_BANTUAN: bantuan,
}


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    1. Tombol menu selalu berlaku dan berpindah mode.
    2. Selain itu, teks diproses sesuai mode yang sedang aktif.
    """

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    command = text.lower()

    action = MENU_ACTIONS.get(text)
    if action:
        await action(update, context)
        return

    if command in BACK_WORDS:
        await main_menu(update, context)
        return

    mode = context.user_data.get("mode")

    if mode == MODE_SEARCH:
        await proses_pencarian(update, context)

    elif mode in (MODE_WISATA_MENU, MODE_WISATA):
        if command == "kategori":
            await menu_wisata(update, context)
        else:
            await proses_pencarian_destinasi(update, context)

    else:
        await reply(update, MSG_PILIH_MENU)


# =========================================================
# PENANGANAN ERROR
# =========================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error

    if isinstance(error, BadRequest) and "message is not modified" in str(error).lower():
        log.info("Pesan tidak berubah (diabaikan).")
        return

    if isinstance(error, TimedOut):
        log.warning("Request Telegram timeout: %s", error)
        return

    if isinstance(error, NetworkError):
        log.warning("Gangguan jaringan Telegram: %s", error)
        return

    if isinstance(error, Forbidden):
        log.info("Chat tidak dapat diakses (bot diblokir?): %s", error)
        return

    try:  # error httpx yang belum dibungkus oleh python-telegram-bot
        import httpx

        if isinstance(error, (httpx.TimeoutException, httpx.TransportError)):
            log.warning("Gangguan koneksi (%s): %s", type(error).__name__, error)
            return
    except ImportError:
        pass

    log.error("Error tidak terduga.", exc_info=error)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Maaf, terjadi kendala. Silakan coba lagi.", reply_markup=MENU
            )
        except Exception:  # noqa: BLE001
            pass


# =========================================================
# MAIN
# =========================================================

def main():
    global SCHEDULER

    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN belum diatur.")

    SCHEDULER = load_scheduler()

    # Muat dataset di awal agar masalah path langsung terlihat di log.
    events, destinations = load_events(), load_destinations()
    log.info(
        "Event: %s | Destinasi: %s",
        f"{len(events)} baris" if events is not None else "GAGAL DIMUAT",
        f"{len(destinations)} baris" if destinations is not None else "GAGAL DIMUAT",
    )

    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(20)
        .read_timeout(20)
        .write_timeout(20)
        .pool_timeout(20)
        .get_updates_connect_timeout(20)
        .get_updates_read_timeout(30)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("berhenti", berhenti))
    app.add_handler(CallbackQueryHandler(wisata_callback, pattern=r"^wiscategory_\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    app.add_error_handler(error_handler)

    log.info("WisataKP Bot sedang berjalan...")
    app.run_polling(bootstrap_retries=-1)


if __name__ == "__main__":
    main()