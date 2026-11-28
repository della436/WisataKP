# -*- coding: utf-8 -*-
"""
WisataKP Telegram Bot - Versi 2.0 (revisi sesuai PRD)

Struktur file:
  1. Konfigurasi & logging
  2. Pembacaan dataset (CSV event & destinasi)
  3. Utilitas teks & tanggal
  4. Logika event (daftar, pencarian, format)
  5. Logika destinasi (kategori, pencarian, detail)
  6. Helper pengiriman pesan Telegram
  7. Handler menu & state percakapan
  8. Penanganan error
  9. Main
"""

import csv
import fnmatch
import io
import logging
import os
import re
import time
import unicodedata
from collections import Counter
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

    PREVIEW_KW = {"link_preview_options": LinkPreviewOptions(is_disabled=True)}
except ImportError:  # python-telegram-bot 20.x
    PREVIEW_KW = {"disable_web_page_preview": True}

try:  # opsional: baca TELEGRAM_BOT_TOKEN dari file .env
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# =========================================================
# 1. KONFIGURASI & LOGGING
# =========================================================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

SCRIPT_DIR = Path(__file__).resolve().parent

# Folder yang dicari (berdasarkan lokasi file bot.py, bukan
# current working directory). Mencakup bot.py di root project
# maupun di dalam subfolder (misal bot/bot.py).
SEARCH_ROOTS = [SCRIPT_DIR, SCRIPT_DIR.parent]
SKIP_DIRS = {
    "venv", ".venv", "env", "node_modules", "__pycache__",
    "site-packages", ".git", ".idea", ".vscode",
}
MAX_SEARCH_DEPTH = 4

# Boleh dioverride lewat environment variable bila perlu:
#   EVENT_CSV_PATH=/path/ke/event_valid.csv
#   DESTINATION_CSV_PATH=/path/ke/destinasi_60_final.csv
EVENT_FILE_PATTERNS = ["event_valid*.csv"]
DESTINATION_FILE_PATTERNS = [
    "destinasi_60_final*.csv",
    "destinasi_clean*.csv",
    "destinasi*.csv",
]

MAX_EVENT_LIST = 5       # Daftar Event: maksimal 5, tanpa pagination
MAX_SEARCH_RESULTS = 5   # Cari Event: maksimal 5 per respons
MAX_RELATED_EVENTS = 3   # Event terkait pada detail destinasi
TELEGRAM_SAFE_LIMIT = 3900

WIB = timezone(timedelta(hours=7))

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
# httpx mencetak URL request (berisi token bot) pada level INFO
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("wisatakp")


def today_wib():
    """Tanggal hari ini menurut WIB (bukan zona waktu server)."""
    return datetime.now(WIB).date()


# ---------------------------------------------------------
# Menu & state
# ---------------------------------------------------------

MENU_DAFTAR = "📅 Daftar Event"
MENU_CARI = "🔍 Cari Event"
MENU_WISATA = "🏞️ Wisata"
MENU_BANTUAN = "❓ Bantuan"

MENU = ReplyKeyboardMarkup(
    [[MENU_DAFTAR, MENU_CARI], [MENU_WISATA, MENU_BANTUAN]],
    resize_keyboard=True,
    input_field_placeholder="Pilih menu WisataKP",
)

MODE_MENU = "menu"                  # menu utama
MODE_EVENT_SEARCH = "event_search"  # pencarian event
MODE_WISATA_MENU = "wisata_menu"    # memilih kategori wisata
MODE_WISATA_SEARCH = "wisata_search"  # pencarian destinasi

KATEGORI_WISATA = [
    "🏖️ Pantai",
    "🌿 Wisata Alam",
    "🏡 Desa Wisata",
    "☕ Kuliner & Tempat Nongkrong",
    "⛰️ Panorama",
]

MSG_PILIH_MENU = "👇 Silakan pilih menu yang tersedia di bawah."
MSG_DATA_EVENT_ERROR = (
    "⚠️ <b>Data event belum bisa dimuat</b>\n"
    "<i>Silakan coba lagi beberapa saat lagi.</i>"
)
MSG_DATA_DESTINASI_ERROR = (
    "⚠️ <b>Data destinasi belum bisa dimuat</b>\n"
    "<i>Silakan coba lagi beberapa saat lagi.</i>"
)


# =========================================================
# 2. PEMBACAAN DATASET
# =========================================================

def _walk_limited(root, max_depth=MAX_SEARCH_DEPTH):
    """os.walk dengan batas kedalaman dan folder yang diabaikan."""
    base_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
        ]
        path = Path(dirpath)
        if len(path.parts) - base_depth >= max_depth:
            dirnames[:] = []
        yield path, filenames


def find_dataset_file(patterns, env_var):
    """Mencari file CSV berdasarkan lokasi project."""

    override = os.getenv(env_var)
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            path = SCRIPT_DIR / path
        if path.is_file():
            return path
        log.error("%s=%s menunjuk ke file yang tidak ada.", env_var, path)
        return None

    found = {}
    for root in SEARCH_ROOTS:
        if not root.is_dir():
            continue
        for folder, filenames in _walk_limited(root):
            depth = len(folder.parts)
            for filename in filenames:
                for index, pattern in enumerate(patterns):
                    if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                        path = (folder / filename).resolve()
                        key = (index, depth)
                        if path not in found or key < found[path]:
                            found[path] = key
                        break

    if not found:
        return None

    return min(found, key=lambda p: (found[p], str(p)))


def read_csv_rows(path):
    """Membaca CSV; nama kolom dinormalisasi (huruf kecil, tanpa spasi)."""

    raw = path.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise ValueError("Encoding file tidak dikenali.")

    first_line = text.splitlines()[0] if text.strip() else ""
    delimiter = max([",", ";", "\t"], key=first_line.count)

    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)

    rows = []
    for raw_row in reader:
        row = {}
        for key, value in raw_row.items():
            if not key or not isinstance(value, str):
                continue
            row[key.strip().lower()] = value.strip()
        if any(row.values()):
            rows.append(row)

    return rows


class CsvDataset:
    """
    Dataset CSV dengan cache berbasis waktu modifikasi file.
    get() mengembalikan:
      - list (bisa kosong bila dataset memang kosong), atau
      - None bila dataset tidak ditemukan / gagal dimuat
        (supaya tidak disamakan dengan "hasil tidak ditemukan").
    """

    SEARCH_COOLDOWN = 30  # detik antar pencarian ulang file yang hilang

    def __init__(self, label, patterns, env_var, row_filter):
        self.label = label
        self.patterns = patterns
        self.env_var = env_var
        self.row_filter = row_filter
        self.path = None
        self._mtime = None
        self._rows = None
        self._last_search = None

    def _resolve_path(self):
        if self.path and self.path.is_file():
            return self.path

        now = time.monotonic()
        if (
            self._last_search is not None
            and now - self._last_search < self.SEARCH_COOLDOWN
        ):
            return None
        self._last_search = now

        self.path = find_dataset_file(self.patterns, self.env_var)

        if self.path is None:
            log.error(
                "Dataset %s tidak ditemukan. Pola file: %s | Folder dicari: %s",
                self.label,
                ", ".join(self.patterns),
                ", ".join(str(r) for r in SEARCH_ROOTS),
            )
        else:
            log.info("Dataset %s: %s", self.label, self.path)

        return self.path

    def get(self):
        path = self._resolve_path()
        if path is None:
            return None

        try:
            mtime = path.stat().st_mtime
        except OSError as error:
            log.error("Tidak dapat mengakses %s: %s", path, error)
            self.path = None
            return self._rows

        if self._rows is not None and mtime == self._mtime:
            return self._rows

        try:
            all_rows = read_csv_rows(path)
            rows = self.row_filter(all_rows, self.label)
        except Exception as error:  # noqa: BLE001
            log.error("Gagal membaca dataset %s (%s): %s", self.label, path, error)
            return self._rows

        self._rows = rows
        self._mtime = mtime
        log.info(
            "Dataset %s dimuat: %d baris dipakai dari %d baris.",
            self.label, len(rows), len(all_rows),
        )
        return rows


def filter_valid_events(rows, label):
    """Hanya event dengan status_validasi 'valid' (bila kolomnya ada)."""

    result = []
    for row in rows:
        status = row.get("status_validasi", "").strip().lower()
        if status and not status.startswith("valid"):
            continue
        # Kolom penanda duplikat dari proses scraping/validasi
        if (
            row.get("duplikat_url", "").strip().lower() == "true"
            or row.get("duplikat_judul", "").strip().lower() == "true"
        ):
            continue
        result.append(row)
    return result


NEGATIVE_DECISIONS = (
    "hapus", "buang", "drop", "remove", "delete",
    "exclude", "tolak", "eliminasi", "tidak",
)


def filter_destinations(rows, label):
    """
    Memuat seluruh destinasi yang punya nama. Hanya baris yang secara
    eksplisit ditandai dihapus pada kolom 'keputusan' yang dilewati.
    Rincian baris yang dilewati dicatat di log agar mudah diperiksa.
    """

    result = []
    seen = set()
    skipped = Counter()

    for row in rows:
        name = get_destination_name(row)
        if name == "-":
            skipped["tanpa nama"] += 1
            continue

        decision = row.get("keputusan", "").strip().lower()
        if decision.startswith(NEGATIVE_DECISIONS):
            skipped[f"keputusan={decision}"] += 1
            log.info("Destinasi dilewati (keputusan=%s): %s", decision, name)
            continue

        key = normalize_text(name)
        if key in seen:
            skipped["duplikat"] += 1
            log.info("Destinasi dilewati (duplikat): %s", name)
            continue
        seen.add(key)

        result.append(row)

    if skipped:
        log.info("Destinasi dilewati: %s", dict(skipped))

    return result


EVENTS = CsvDataset(
    "event", EVENT_FILE_PATTERNS, "EVENT_CSV_PATH", filter_valid_events
)
DESTINATIONS = CsvDataset(
    "destinasi", DESTINATION_FILE_PATTERNS,
    "DESTINATION_CSV_PATH", filter_destinations,
)


# =========================================================
# 3. UTILITAS TEKS & TANGGAL
# =========================================================

EMPTY_VALUES = {"", "nan", "none", "null", "-", "n/a"}


def get_value(row, candidates):
    """Nilai pertama yang terisi dari daftar nama kolom (huruf kecil)."""

    for column in candidates:
        value = row.get(column)
        if value is None:
            continue
        value = str(value).strip()
        if value.lower() in EMPTY_VALUES:
            continue
        return value
    return "-"


def normalize_text(text):
    """Huruf kecil, tanpa aksen/tanda baca, spasi dirapikan."""

    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U0001F1E6-\U0001F1FF"
    "\u2600-\u27BF\u2B00-\u2BFF\u200d\ufe0f]"
)


def strip_emoji(text):
    return EMOJI_RE.sub("", text)


def collapse_spaces(text):
    return re.sub(r"\s+", " ", text).strip()


def clean_text(text):
    """
    Pembersihan dasar untuk tampilan: entitas HTML (&ndash;), penanda
    markdown (**tebal**), emoji, dan spasi berlebih. Data CSV tidak diubah.
    """

    text = unescape(str(text or ""))
    text = re.sub(r"[*_`#]{1,3}", "", text)
    text = strip_emoji(text).replace("\xa0", " ")
    return collapse_spaces(text)


BULAN_INDONESIA = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2,
    "maret": 3, "mar": 3, "april": 4, "apr": 4, "mei": 5,
    "juni": 6, "jun": 6, "juli": 7, "jul": 7,
    "agustus": 8, "agu": 8, "ags": 8, "ag": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "november": 11, "nov": 11,
    "desember": 12, "des": 12,
}
NAMA_BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
    "Agustus", "September", "Oktober", "November", "Desember",
]

_MONTH = "|".join(sorted(BULAN_INDONESIA, key=len, reverse=True))
ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
RANGE_RE = re.compile(
    rf"(\d{{1,2}})(?:\s+({_MONTH})\b)?(?:\s+(\d{{4}}))?"
    rf"\s*(?:-|–|—|s\.?\s*/?\s*d\.?|sd|hingga|sampai|dan)\s*"
    rf"(\d{{1,2}})\s+({_MONTH})\b\s+(\d{{4}})"
)
SINGLE_RE = re.compile(rf"(\d{{1,2}})\s+({_MONTH})\b\s+(\d{{4}})")
NUMERIC_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"]


def parse_event_span(value):
    """
    Mengembalikan (tanggal_mulai, tanggal_selesai) atau (None, None).
    Mendukung tanggal tunggal, rentang ("12-14 Januari 2026"),
    format ISO, dan format angka dd/mm/yyyy.
    """

    if not value or value == "-":
        return None, None

    text = str(value).strip().lower()

    # Format ISO (satu atau lebih tanggal)
    iso_dates = []
    for item in ISO_RE.findall(text):
        try:
            iso_dates.append(datetime.strptime(item, "%Y-%m-%d").date())
        except ValueError:
            pass
    if iso_dates:
        return min(iso_dates), max(iso_dates)

    # Rentang tanggal Indonesia
    match = RANGE_RE.search(text)
    if match:
        d1, m1, y1, d2, m2, y2 = match.groups()
        try:
            end = date(int(y2), BULAN_INDONESIA[m2], int(d2))
            start = date(
                int(y1 or y2),
                BULAN_INDONESIA[m1 or m2],
                int(d1),
            )
            if start <= end:
                return start, end
        except (ValueError, KeyError):
            pass

    # Satu atau beberapa tanggal Indonesia
    singles = []
    for d, m, y in SINGLE_RE.findall(text):
        try:
            singles.append(date(int(y), BULAN_INDONESIA[m], int(d)))
        except (ValueError, KeyError):
            pass
    if singles:
        return min(singles), max(singles)

    # Format angka
    for fmt in NUMERIC_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
            return parsed, parsed
        except ValueError:
            continue

    return None, None


def format_date_range(start, end):
    if start is None:
        return None
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


def shorten_sentence_text(text, max_length):
    """Memotong teks di batas kata, memakai '...' bila terpotong."""
    if len(text) <= max_length:
        return text
    cut = text[:max_length].rsplit(" ", 1)[0]
    return cut.rstrip(" .,;:–-") + "..."


# =========================================================
# 4. LOGIKA EVENT
# =========================================================

def get_event_name(row):
    return get_value(row, [
        "nama_event", "judul_event", "judul", "title", "nama",
    ])


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


# ---------------------------------------------------------
# Pembersihan judul, lokasi, deskripsi (hanya untuk tampilan;
# data CSV tidak diubah)
# ---------------------------------------------------------

REGION = r"(?:kab(?:upaten)?\.?\s*)?kulon\s*progo"
LEADING_REGION_RE = re.compile(
    rf"^\s*[\(\[]?\s*{REGION}\s*[\)\]]?\s*[-–—:|,]\s*", re.IGNORECASE
)
DATELINE_RE = re.compile(
    r"^\s*[A-Za-z .]{3,40},\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}\s*[-–—:]\s*"
)
TRAILING_SITE_RE = re.compile(
    rf"\s*[|–—-]\s*(?:{REGION}|pemerintah kabupaten kulon progo|"
    r"pemkab kulon progo|portal\b.*|[\w.-]+\.(?:go\.id|co\.id|com|id))\s*$",
    re.IGNORECASE,
)
PEMKAB_RE = re.compile(r"pemerintah\s+kabupaten\s+kulon\s*progo", re.IGNORECASE)


SMALL_WORDS = {
    "di", "dan", "yang", "ke", "dari", "untuk", "dengan", "pada", "atau",
    "serta", "ing", "dalam", "oleh", "bagi", "hingga", "sampai", "se",
}
TIME_AGO_RE = re.compile(
    r"\s+\d+\s+(?:\d+\s+)?(?:detik|menit|jam|hari|minggu|bulan|tahun)"
    r"\s+yang\s+lalu.*$",
    re.IGNORECASE,
)


def _slug_words(url):
    """Kata-kata dari slug URL artikel (berisi judul lengkap), atau None."""

    if not url or url == "-":
        return None
    slug = unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1])
    slug = re.sub(r"\.(?:html?|php)$", "", slug, flags=re.IGNORECASE)
    words = [w for w in slug.split("-") if w]
    if len(words) < 2 or sum(c.isalpha() for c in slug) < 6:
        return None
    return words


def _casing_map(row):
    """
    Huruf besar khusus (YRKI, KPHM, MyEndura) diambil dari teks asli
    untuk menyusun judul dari slug URL yang berhuruf kecil.
    """

    text = clean_text(" ".join([
        row.get("judul", ""), row.get("ringkasan", ""),
        row.get("deskripsi_event", ""),
    ]))
    words = re.findall(r"[A-Za-z][A-Za-z0-9]*", text)
    seen_plain = {
        w.lower() for w in words if w == w.lower() or w == w.capitalize()
    }

    mapping = {}
    for w in words:
        lw = w.lower()
        if lw in ("kulon", "progo") or lw in seen_plain:
            continue
        if (w.isupper() and 2 <= len(w) <= 6) or re.search(r"[a-z][A-Z]", w):
            mapping.setdefault(lw, w)
    return mapping


def _title_from_slug(row):
    words = _slug_words(get_event_url(row))
    if not words:
        return None

    casing = _casing_map(row)

    # Potongan judul asli dipakai untuk memisahkan kata yang menempel di
    # slug, mis. "sambanggoyear" -> "Sambanggo" + "Year".
    fragment = clean_text(row.get("judul", "")).split("...")[0]
    original = [t for t in re.split(r"[\s,;:/()]+", fragment) if t]
    pairs = {
        (a + b).lower(): (a, b) for a, b in zip(original, original[1:])
    }
    known = {t.lower() for t in original}

    expanded = []
    for w in words:
        if w not in known and w in pairs:
            expanded.extend(pairs[w])
        else:
            expanded.append(w)

    parts = []
    skip_next = False
    for index, w in enumerate(expanded):
        if skip_next:
            skip_next = False
            continue
        lw = w.lower()
        nxt = expanded[index + 1] if index + 1 < len(expanded) else ""

        if re.fullmatch(r"\d{1,2}", w) and re.fullmatch(r"\d{1,2}", nxt):
            parts.append(f"{w}–{nxt}")  # "3 4 mei" -> "3–4 Mei"
            skip_next = True
        elif lw in casing:
            parts.append(casing[lw])
        elif index > 0 and lw in SMALL_WORDS:
            parts.append(lw)
        else:
            parts.append(w[:1].upper() + w[1:].lower())

    # Nama inti kegiatan biasanya berakhir pada tahun penyelenggaraan:
    # "Festival Paralayang 2026 Resmi Ditutup ..." -> "Festival Paralayang 2026"
    for index, token in enumerate(parts):
        if index >= 2 and re.fullmatch(r"20\d{2}", token):
            return " ".join(parts[:index + 1])

    return " ".join(parts)


def _title_from_name(row):
    """Cadangan bila URL tidak memuat slug judul."""

    name = clean_text(get_event_name(row))
    if name == "-" or not name:
        return None

    # nama_event berbentuk "<judul terpotong>... <awal isi artikel> ..."
    if "..." in name:
        name = name.split("...")[0]
    name = TIME_AGO_RE.sub("", name)

    for _ in range(2):
        name = LEADING_REGION_RE.sub("", name)
        name = TRAILING_SITE_RE.sub("", name)
    return name.strip(" -–—|:,")


def get_display_title(row):
    """
    Judul ringkas: nama inti kegiatan, bukan judul artikel berita.
    Sumber utama: slug URL (judul lengkap); cadangan: nama_event.
    """

    name = _title_from_slug(row)
    from_slug = bool(name)
    if not from_slug:
        name = _title_from_name(row)
    if not name:
        return "Event Wisata"

    name = PEMKAB_RE.sub("Pemkab Kulon Progo", name)

    # Judul cadangan berhuruf kapital semua diubah ke Title Case;
    # judul dari slug sudah memiliki kapitalisasi yang benar.
    if not from_slug and name.isupper():
        name = name.title()

    if len(name) > 80:
        words, out = name.split(), []
        for w in words:
            if len(" ".join(out + [w])) > 76:
                break
            out.append(w)
        while out and out[-1].lower() in SMALL_WORDS:
            out.pop()
        name = " ".join(out) + "..."

    return name.strip() or "Event Wisata"


LOCATION_CUT_RE = re.compile(
    r"[\s,;]+(?:berhasil|akan|ini|itu|yang|sudah|telah|dengan|kegiatan|"
    r"untuk|dalam|pada|serta|kemudian|bertujuan|dimeriahkan|terselenggara|"
    r"menjadi|digelar|terdapat|salah\s+satu|dilaksanakan|diselenggarakan|"
    r"melaksanakan|menggelar)\b.*$",
    re.IGNORECASE,
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
    Lokasi yang dirapikan. Kolom lokasi_event_ekstrak hasil ekstraksi
    sering memuat sisa kalimat, tanggal, atau terpotong; bagian tersebut
    dibuang hanya pada tampilan.
    """

    raw = get_event_location(row)
    if raw == "-":
        return "Lokasi belum tersedia"

    original = clean_text(raw)
    text = re.sub(
        r"^(?:bertempat\s+di|lokasi\s*:?|di)\s+", "", original,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\([^)]*\d[^)]*\)", "", text)   # (12/4/2025), (500m)
    text = re.sub(r"\([^)]*$", "", text)           # kurung terpotong

    cut_text = LOCATION_CUT_RE.sub("", text)
    was_cut = cut_text != text
    text = cut_text.strip(" ,;")

    parts, seen = [], set()
    for part in re.split(r"\s*,\s*", text):
        key = normalize_text(part)
        if not key or key in seen or _is_date_part(part):
            continue
        seen.add(key)
        parts.append(part.strip())

    # Data lokasi sering terpotong di akhir; buang bagian terakhir
    # yang kemungkinan tidak utuh.
    if len(parts) > 1 and (
        (len(original) >= 80 and not was_cut) or len(parts[-1]) <= 4
    ):
        parts.pop()

    parts = [p.title() if p.islower() else p[:1].upper() + p[1:] for p in parts]

    location = ", ".join(parts).strip()
    if not location:
        location = original or "Lokasi belum tersedia"

    return shorten_sentence_text(location, 100)


def clean_description(text):
    if not text or text == "-":
        return ""

    text = clean_text(text)
    text = re.sub(r"https?://\S+", "", text)
    text = collapse_spaces(text)

    # boilerplate berita di awal kalimat
    for _ in range(2):
        text = DATELINE_RE.sub("", text)
        text = LEADING_REGION_RE.sub("", text)

    text = re.sub(r"\bbaca juga\b.*$", "", text, flags=re.IGNORECASE)
    text = PEMKAB_RE.sub("Pemkab Kulon Progo", text)
    return text.strip()


def shorten_description(text, max_length=200):
    """Satu atau dua kalimat pertama yang ringkas, tanpa emoji."""

    text = clean_description(text)
    if not text:
        return "Informasi event belum tersedia."

    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()
    ]
    if not sentences:
        return "Informasi event belum tersedia."

    result = sentences[0]
    if len(result) < 70 and len(sentences) > 1:
        candidate = f"{result} {sentences[1]}"
        if len(candidate) <= max_length:
            result = candidate

    return shorten_sentence_text(result, max_length)


# ---------------------------------------------------------
# Status event
# ---------------------------------------------------------

BUCKET_UPCOMING = "upcoming"
BUCKET_TODAY = "today"
BUCKET_YESTERDAY = "yesterday"
BUCKET_PAST = "past"
BUCKET_UNDATED = "undated"

STATUS_LABEL = {
    BUCKET_UPCOMING: "🟢 AKAN DATANG",
    BUCKET_TODAY: "🟡 BERLANGSUNG HARI INI",
    BUCKET_YESTERDAY: "🔴 BARU SAJA BERLALU",
    BUCKET_PAST: "⚪ TELAH BERLALU",
    BUCKET_UNDATED: "⚪ TANGGAL BELUM TERSEDIA",
}

LINE = "━━━━━━━━━━━━━━━━━━"


def classify_event(row, today):
    """Mengembalikan (bucket, tanggal_mulai, tanggal_selesai)."""

    start, end = parse_event_span(get_event_date(row))

    if start is None:
        return BUCKET_UNDATED, None, None
    if start > today:
        return BUCKET_UPCOMING, start, end
    if start <= today <= end:
        return BUCKET_TODAY, start, end
    if end == today - timedelta(days=1):
        return BUCKET_YESTERDAY, start, end
    return BUCKET_PAST, start, end


def dedupe_events(rows):
    """Menghilangkan event ganda (judul dan tanggal sama)."""

    seen, result = set(), []
    for row in rows:
        key = (
            normalize_text(get_display_title(row)),
            normalize_text(get_event_date(row)),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


# ---------------------------------------------------------
# Format tampilan event (dipakai di semua menu)
# ---------------------------------------------------------

def get_event_emoji(row):
    text = (get_display_title(row) + " " + get_event_category(row)).lower()

    groups = [
        ("🏃", ["lari", "marathon", "maraton", "sport", "olahraga"]),
        ("🎭", ["seni", "budaya", "festival", "tari", "musik"]),
        ("🍜", ["kuliner", "makanan", "food"]),
        ("🏖️", ["pantai", "laut"]),
        ("🛍️", ["pasar", "expo", "pameran"]),
    ]
    for emoji, words in groups:
        if any(word in text for word in words):
            return emoji
    return "🎉"


def format_event_card(row, today):
    bucket, start, end = classify_event(row, today)

    title = escape(get_display_title(row))
    location = escape(get_display_location(row))
    description = escape(shorten_description(get_event_description(row)))
    date_text = (
        format_date_range(start, end)
        or (get_event_date(row) if get_event_date(row) != "-" else None)
        or "Tanggal belum tersedia"
    )

    message = (
        f"<b>{STATUS_LABEL[bucket]}</b>\n"
        f"{get_event_emoji(row)} <b>{title}</b>\n\n"
        f"📅  <b>{escape(date_text)}</b>\n"
        f"📍  {location}\n\n"
        f"<blockquote>{description}</blockquote>"
    )

    url = get_event_url(row)
    if url != "-":
        message += f"\n🔗 <a href=\"{escape(url, quote=True)}\">Baca selengkapnya ›</a>"

    return message


EVENT_SEPARATOR = "\n\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"


def build_messages(header, blocks, footer=""):
    """
    Menyusun pesan; dipecah menjadi beberapa pesan bila melebihi batas
    panjang Telegram (4096 karakter).
    """

    messages = []
    current = header

    for index, block in enumerate(blocks):
        piece = block + (EVENT_SEPARATOR if index < len(blocks) - 1 else "")
        if len(current) + len(piece) > TELEGRAM_SAFE_LIMIT and current.strip():
            messages.append(current.rstrip())
            current = ""
        current += piece

    if footer:
        if len(current) + len(footer) > TELEGRAM_SAFE_LIMIT:
            messages.append(current.rstrip())
            current = ""
        current += footer

    if current.strip():
        messages.append(current.rstrip())

    return messages


# ---------------------------------------------------------
# Daftar Event (maks. 5, tanpa pagination)
# ---------------------------------------------------------

def select_events_for_list(events, today):
    """
    Prioritas: 2 mendatang, 2 hari ini, 1 kemarin.
    Slot kosong diisi dari kategori lain yang tersedia.
    """

    buckets = {
        BUCKET_UPCOMING: [], BUCKET_TODAY: [],
        BUCKET_YESTERDAY: [], BUCKET_PAST: [],
    }

    for row in dedupe_events(events):
        bucket, start, end = classify_event(row, today)
        if bucket == BUCKET_UNDATED:
            continue
        buckets[bucket].append((start, end, row))

    buckets[BUCKET_UPCOMING].sort(key=lambda x: x[0])
    buckets[BUCKET_TODAY].sort(key=lambda x: (x[0], get_event_name(x[2]).lower()))
    buckets[BUCKET_YESTERDAY].sort(key=lambda x: get_event_name(x[2]).lower())
    buckets[BUCKET_PAST].sort(key=lambda x: x[1], reverse=True)

    quota = [(BUCKET_UPCOMING, 2), (BUCKET_TODAY, 2), (BUCKET_YESTERDAY, 1)]

    selected, used = [], set()

    for name, limit in quota:
        for item in buckets[name][:limit]:
            selected.append(item[2])
            used.add(id(item[2]))

    # Isi slot kosong dari kategori lain
    for name in (BUCKET_UPCOMING, BUCKET_TODAY, BUCKET_YESTERDAY, BUCKET_PAST):
        for item in buckets[name]:
            if len(selected) >= MAX_EVENT_LIST:
                break
            if id(item[2]) not in used:
                selected.append(item[2])
                used.add(id(item[2]))

    selected = selected[:MAX_EVENT_LIST]

    order = {
        BUCKET_TODAY: 0, BUCKET_UPCOMING: 1,
        BUCKET_YESTERDAY: 2, BUCKET_PAST: 3,
    }
    selected.sort(key=lambda r: order[classify_event(r, today)[0]])
    return selected


# ---------------------------------------------------------
# Pencarian event
# ---------------------------------------------------------

def search_events(events, keyword, today):
    tokens = normalize_text(keyword).split()
    if not tokens:
        return []

    indexed = []
    for row in dedupe_events(events):
        bucket, start, end = classify_event(row, today)
        haystack = normalize_text(" ".join([
            get_display_title(row),
            get_event_date(row),
            format_date_range(start, end) or "",
            get_event_location(row),
            get_event_category(row),
            get_event_description(row),
        ]))
        indexed.append((row, bucket, start, end, haystack))

    hits = [item for item in indexed if all(t in item[4] for t in tokens)]

    # Jika kata kunci majemuk tidak ada yang cocok penuh,
    # tampilkan yang cocok sebagian (urut dari yang paling banyak cocok).
    if not hits and len(tokens) > 1:
        scored = [
            (sum(t in item[4] for t in tokens), item) for item in indexed
        ]
        best = max((s for s, _ in scored), default=0)
        if best > 0:
            hits = [item for s, item in scored if s == best]

    def sort_key(item):
        _, bucket, start, end, _ = item
        if bucket in (BUCKET_TODAY, BUCKET_UPCOMING):
            return (0, start)
        if bucket in (BUCKET_YESTERDAY, BUCKET_PAST):
            return (1, -end.toordinal())
        return (2, 0)

    hits.sort(key=sort_key)
    return [item[0] for item in hits]


# =========================================================
# 5. LOGIKA DESTINASI
# =========================================================

def get_destination_name(row):
    return get_value(row, ["title", "nama", "nama_destinasi", "name"])


def get_destination_address(row):
    return get_value(row, ["address", "alamat", "lokasi"])


def get_destination_category_raw(row):
    return get_value(row, ["categoryname", "kategori", "category"])


def get_destination_description(row):
    return get_value(row, [
        "description", "deskripsi", "ringkasan", "summary", "about",
    ])


CATEGORY_RULES = [
    ("🏖️ Pantai", ["pantai", "beach", "pesisir", "laguna", "muara"]),
    ("🏡 Desa Wisata", ["desa wisata", "kampung wisata", "kampung", "desa"]),
    ("☕ Kuliner & Tempat Nongkrong", [
        "cafe", "café", "kafe", "coffee", "kopi", "resto", "restoran",
        "restaurant", "warung", "kuliner", "makan", "kedai", "angkringan",
        "nongkrong", "bakso", "sate", "soto", "bakery", "dapur",
    ]),
    ("⛰️ Panorama", [
        "puncak", "view", "bukit", "panorama", "menoreh", "sunset",
        "sunrise", "pandang", "kaki langit", "negeri di atas awan",
    ]),
    ("🌿 Wisata Alam", [
        "curug", "air terjun", "waduk", "telaga", "danau", "embung",
        "hutan", "sungai", "kebun", "goa", "gua", "alam", "taman",
    ]),
]
DEFAULT_CATEGORY = "🌿 Wisata Alam"


def _match_category(text):
    text = normalize_text(text)
    if not text:
        return None
    for category, words in CATEGORY_RULES:
        for word in words:
            if re.search(rf"(?<![a-z0-9]){re.escape(normalize_text(word))}", text):
                return category
    return None


def classify_destination(row):
    """
    Kategori ditentukan dari kolom kategori dataset lebih dulu
    (mis. 'Kafe', 'Pantai'); jika tidak cukup informatif, dari nama
    destinasi. Alamat sengaja tidak dipakai karena sering memuat
    kata seperti 'Jl. Pantai ...' yang menyesatkan.
    """

    return (
        _match_category(get_destination_category_raw(row))
        or _match_category(get_destination_name(row))
        or DEFAULT_CATEGORY
    )


# Kata umum tidak boleh menjadi dasar kecocokan fuzzy; kalau tidak,
# "pantai glagah" akan dianggap mirip dengan "Pantai Mlarangan Asri".
GENERIC_TOKENS = {
    "pantai", "wisata", "desa", "kampung", "waduk", "curug", "bukit",
    "puncak", "taman", "kebun", "goa", "gua", "kafe", "cafe", "warung",
    "kopi", "resto", "rumah", "makan", "kedai", "the", "di", "dan",
    "kulon", "progo", "kulonprogo", "obyek", "objek",
}
FUZZY_TOKEN_MIN = 0.8
FUZZY_MAX_SCORE = 0.84  # selalu di bawah STRONG_SCORE


def _fuzzy_score(keyword_norm, title_norm):
    """
    Toleransi typo per kata khas: setiap kata khas pada kata kunci
    harus mirip dengan salah satu kata pada judul.
    """

    k_tokens = [t for t in keyword_norm.split() if t not in GENERIC_TOKENS]
    t_tokens = title_norm.split()
    if not k_tokens or not t_tokens:
        return 0.0

    best_scores = []
    for k in k_tokens:
        if len(k) < 4:  # kata terlalu pendek: tanpa toleransi typo
            return 0.0
        best = max(SequenceMatcher(None, k, t).ratio() for t in t_tokens)
        if best < FUZZY_TOKEN_MIN:
            return 0.0
        best_scores.append(best)

    return min(sum(best_scores) / len(best_scores), FUZZY_MAX_SCORE)


STRONG_SCORE = 0.85


def score_destination(keyword_norm, title_norm):
    """Skor kecocokan 0..1 antara kata kunci dan judul destinasi."""

    if not keyword_norm or not title_norm:
        return 0.0

    k_compact = keyword_norm.replace(" ", "")
    t_compact = title_norm.replace(" ", "")

    if keyword_norm == title_norm or k_compact == t_compact:
        return 1.0
    if title_norm.startswith(keyword_norm):
        return 0.95

    k_tokens = keyword_norm.split()
    t_tokens = title_norm.split()

    if re.search(rf"(?<![a-z0-9]){re.escape(keyword_norm)}(?![a-z0-9])", title_norm):
        return 0.9
    if all(token in t_tokens for token in k_tokens):
        return 0.88
    if len(k_compact) >= 4 and k_compact in t_compact:
        return 0.86
    if all(token in title_norm for token in k_tokens) and len(k_compact) >= 4:
        return 0.8

    return _fuzzy_score(keyword_norm, title_norm)


def find_destinations(keyword, destinations, category=None):
    """
    Mencari di SELURUH destinasi (kategori hanya memberi sedikit
    prioritas, tidak pernah menyaring). Mengembalikan daftar
    (skor, row) terurut dari yang paling cocok.
    """

    keyword_norm = normalize_text(keyword)
    if not keyword_norm:
        return []

    results = []
    for row in destinations:
        title_norm = normalize_text(get_destination_name(row))
        score = score_destination(keyword_norm, title_norm)
        if score <= 0:
            continue

        adjusted = score
        if category and classify_destination(row) == category:
            adjusted += 0.02
        adjusted -= len(title_norm) * 1e-5  # judul lebih pendek = lebih tepat
        results.append((adjusted, row))

    results.sort(key=lambda x: x[0], reverse=True)
    return results


def is_ambiguous(results):
    """True bila beberapa destinasi sama-sama cocok dan tidak ada yang jelas."""

    if len(results) < 2:
        return False
    top, second = results[0][0], results[1][0]
    return top < 0.99 and second >= STRONG_SCORE and (top - second) < 0.04


def get_destinations_by_category(destinations, category):
    return [r for r in destinations if classify_destination(r) == category]


# ---------------------------------------------------------
# Detail destinasi
# ---------------------------------------------------------

THEMES = {
    "pantai": "🏖️",
    "alam": "🌿",
    "desa": "🏡",
    "kuliner": "☕",
    "panorama": "⛰️",
}


def get_theme_emoji(category):
    category = category.lower()
    for key, emoji in THEMES.items():
        if key in category:
            return emoji
    return "🌿"


def _is_google_maps_url(url):
    url = url.lower()
    return url.startswith("http") and any(
        marker in url for marker in (
            "google.com/maps", "maps.google", "maps.app.goo.gl",
            "goo.gl/maps", "g.page",
        )
    )


def get_maps_url(row):
    """
    Urutan: link Google Maps dari dataset -> koordinat dataset ->
    pencarian Google Maps dari nama + alamat (hanya bila keduanya ada).
    Mengembalikan None bila lokasi tidak dapat ditentukan.
    """

    for column in ("google_maps_url", "maps_url", "link_maps", "url", "placeurl", "place_url"):
        value = row.get(column, "")
        if value and _is_google_maps_url(value):
            return value

    lat = get_value(row, ["latitude", "lat"])
    lng = get_value(row, ["longitude", "lng", "lon", "long"])

    if lat == "-" or lng == "-":
        located = row.get("location", "")
        match = re.search(
            r"lat\D{0,6}(-?\d+\.\d+).*?(?:lng|lon)\D{0,6}(-?\d+\.\d+)",
            located, re.IGNORECASE | re.DOTALL,
        )
        if match:
            lat, lng = match.groups()

    try:
        float(lat)
        float(lng)
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
    except ValueError:
        pass

    name = get_destination_name(row)
    address = get_destination_address(row)
    if name != "-" and address != "-":
        query = quote(f"{name}, {address}")
        return f"https://www.google.com/maps/search/?api=1&query={query}"

    return None


def get_related_events(destination, events, today):
    """
    Event hari ini / mendatang yang benar-benar menyebut nama
    destinasi pada lokasi atau judul event (pencocokan kata utuh).
    """

    name = normalize_text(get_destination_name(destination))
    if not name:
        return []

    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])")
    related = []

    for row in dedupe_events(events):
        bucket, start, end = classify_event(row, today)
        if bucket not in (BUCKET_TODAY, BUCKET_UPCOMING):
            continue

        if pattern.search(normalize_text(get_event_location(row))) or \
                pattern.search(normalize_text(get_display_title(row))):
            related.append((start, row))

    related.sort(key=lambda x: x[0])
    return [row for _, row in related]


def format_destination_detail(destination, events, today):
    name = get_destination_name(destination)
    address = get_destination_address(destination)
    category = classify_destination(destination)
    emoji = get_theme_emoji(category)

    category_label = collapse_spaces(strip_emoji(category))

    lines = [
        f"{emoji} <b>{escape(name)}</b>",
        f"<i>{escape(category_label)}</i>",
        LINE,
        "",
        f"📍  {escape(address) if address != '-' else 'Alamat belum tersedia'}",
    ]

    maps_url = get_maps_url(destination)
    if maps_url:
        lines.append(
            f"🗺️  <a href=\"{escape(maps_url, quote=True)}\">Buka di Google Maps ›</a>"
        )

    description = clean_description(get_destination_description(destination))
    if description:
        lines += [
            "",
            f"<blockquote>{escape(shorten_sentence_text(description, 350))}</blockquote>",
        ]

    message = "\n".join(lines)

    related = get_related_events(destination, events or [], today) if events else []
    if related:
        cards = [
            format_event_card(row, today)
            for row in related[:MAX_RELATED_EVENTS]
        ]
        message += (
            f"\n\n{LINE}\n"
            "🎉 <b>EVENT DI DESTINASI INI</b>\n\n"
            + EVENT_SEPARATOR.join(cards)
        )

    return message


# =========================================================
# 6. HELPER PENGIRIMAN PESAN TELEGRAM
# =========================================================

def _strip_tags(text):
    return re.sub(r"<[^>]+>", "", text)


async def reply_html(update, text, reply_markup=MENU, preview=False):
    """reply_text HTML dengan retry sekali untuk timeout dan fallback parse."""

    kwargs = {"parse_mode": ParseMode.HTML, "reply_markup": reply_markup}
    if not preview:
        kwargs.update(PREVIEW_KW)

    for attempt in (1, 2):
        try:
            return await update.effective_message.reply_text(text, **kwargs)
        except BadRequest as error:
            if "parse entities" in str(error).lower():
                log.warning("Gagal parse HTML, kirim sebagai teks biasa.")
                return await update.effective_message.reply_text(
                    _strip_tags(text), reply_markup=reply_markup
                )
            raise
        except (TimedOut, NetworkError):
            if attempt == 2:
                raise
            log.warning("Timeout saat mengirim pesan, mencoba ulang...")


async def safe_edit(query, text, reply_markup=None):
    """edit_message_text yang mengabaikan 'Message is not modified'."""

    try:
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            **PREVIEW_KW,
        )
    except BadRequest as error:
        if "message is not modified" in str(error).lower():
            log.info("Pesan tidak berubah, edit dilewati.")
            return
        raise


def set_mode(context, mode):
    context.user_data["mode"] = mode


def get_mode(context):
    return context.user_data.get("mode", MODE_MENU)


# =========================================================
# 7. HANDLER MENU & STATE PERCAKAPAN
# =========================================================

# ---------------------------------------------------------
# /start dan menu utama
# ---------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_mode(context, MODE_MENU)
    context.user_data.pop("wisata_category", None)

    await reply_html(
        update,
        "🌴 <b>Selamat datang di WisataKP</b> 🌴\n"
        "<i>Teman jalan-jalanmu di Kulon Progo</i>\n\n"
        f"{LINE}\n\n"
        "Mau ke mana hari ini?\n\n"
        "🏖️  Pantai yang memukau\n"
        "🌿  Wisata alam yang menenangkan\n"
        "🏡  Desa wisata yang hangat\n"
        "☕  Kuliner &amp; tempat nongkrong\n"
        "⛰️  Panorama pegunungan\n"
        "🎉  Event seru yang sedang berlangsung\n\n"
        f"{LINE}\n"
        "👇 <b>Pilih menu di bawah untuk mulai</b>",
    )


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_mode(context, MODE_MENU)
    await reply_html(
        update,
        "🌿 <b>MENU UTAMA WISATAKP</b>\n"
        f"{LINE}\n\n"
        "📅  Lihat daftar event terbaru\n"
        "🔍  Cari event favoritmu\n"
        "🏞️  Jelajahi destinasi wisata\n"
        "❓  Panduan penggunaan\n\n"
        "👇 <i>Silakan pilih salah satu menu.</i>",
    )


# ---------------------------------------------------------
# Daftar Event
# ---------------------------------------------------------

async def daftar_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_mode(context, MODE_MENU)

    events = EVENTS.get()
    if events is None:
        await reply_html(update, MSG_DATA_EVENT_ERROR)
        return

    today = today_wib()
    selected = select_events_for_list(events, today)

    if not selected:
        await reply_html(
            update,
            "📭 <b>Belum ada event</b>\n\n"
            "<i>Belum ada event yang dapat ditampilkan saat ini. "
            "Coba lagi nanti ya!</i>",
        )
        return

    blocks = [format_event_card(row, today) for row in selected]
    header = (
        "🎉 <b>EVENT KULON PROGO</b>\n"
        f"<i>{len(blocks)} event pilihan untukmu</i>\n"
        f"{LINE}\n\n"
    )
    messages = build_messages(header, blocks)

    for text in messages:
        await reply_html(update, text)


# ---------------------------------------------------------
# Cari Event
# ---------------------------------------------------------

async def cari_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_mode(context, MODE_EVENT_SEARCH)

    await reply_html(
        update,
        "🔍 <b>CARI EVENT</b>\n"
        f"{LINE}\n\n"
        "Ketik nama event, lokasi, kategori, atau kata kunci "
        "yang ingin kamu cari.\n\n"
        "💡 <b>Contoh:</b>  <code>festival</code>  •  <code>pantai</code>  •  "
        "<code>seni</code>  •  <code>olahraga</code>\n\n"
        "<i>Kamu bisa mencari berkali-kali. "
        "Ketik <b>menu</b> atau pilih menu lain untuk keluar.</i>",
    )


async def proses_pencarian_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Mode TETAP event_search agar pencarian dapat diulang.
    keyword = update.message.text.strip()

    events = EVENTS.get()
    if events is None:
        await reply_html(update, MSG_DATA_EVENT_ERROR)
        return

    today = today_wib()
    hasil = search_events(events, keyword, today)

    if not hasil:
        await reply_html(
            update,
            "🔎 <b>HASIL PENCARIAN</b>\n"
            f"{LINE}\n"
            f"Kata kunci: <b>{escape(keyword)}</b>\n\n"
            "😕 <b>Event tidak ditemukan</b>\n"
            "<i>Coba kata kunci lain, misalnya nama kegiatan atau lokasi.</i>",
        )
        return

    header = (
        "🔎 <b>HASIL PENCARIAN</b>\n"
        f"{LINE}\n"
        f"Kata kunci: <b>{escape(keyword)}</b>\n"
        f"✨ Ditemukan <b>{len(hasil)}</b> event\n\n"
    )

    footer = ""
    if len(hasil) > MAX_SEARCH_RESULTS:
        footer = (
            f"\n\n📌 <i>Menampilkan {MAX_SEARCH_RESULTS} dari {len(hasil)} hasil. "
            "Gunakan kata kunci yang lebih spesifik untuk mempersempit.</i>"
        )
    footer += "\n\n💬 <i>Ketik kata kunci lain untuk mencari lagi.</i>"

    blocks = [format_event_card(row, today) for row in hasil[:MAX_SEARCH_RESULTS]]

    for text in build_messages(header, blocks, footer):
        await reply_html(update, text)


# ---------------------------------------------------------
# Wisata
# ---------------------------------------------------------

def build_category_keyboard(selected=None):
    rows = []
    for index, category in enumerate(KATEGORI_WISATA):
        label = f"✅ {category}" if category == selected else category
        rows.append([
            InlineKeyboardButton(label, callback_data=f"wiscategory_{index}")
        ])
    return InlineKeyboardMarkup(rows)


async def menu_wisata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_mode(context, MODE_WISATA_MENU)
    context.user_data["wisata_category"] = None

    await reply_html(
        update,
        "🏞️ <b>JELAJAHI WISATA KULON PROGO</b>\n"
        f"{LINE}\n\n"
        "1️⃣  Pilih kategori di bawah\n"
        "2️⃣  Ketik nama destinasi yang ingin kamu cari\n\n"
        "👇 <i>Mulai dari kategori favoritmu</i>",
        reply_markup=build_category_keyboard(),
    )


async def wisata_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        index = int(query.data.split("_")[-1])
        category = KATEGORI_WISATA[index]
    except (ValueError, IndexError):
        return

    set_mode(context, MODE_WISATA_SEARCH)
    context.user_data["wisata_category"] = category

    destinations = DESTINATIONS.get()
    if destinations is None:
        await safe_edit(query, MSG_DATA_DESTINASI_ERROR, build_category_keyboard(category))
        return

    in_category = get_destinations_by_category(destinations, category)
    examples = [get_destination_name(r) for r in in_category[:5]]

    examples_text = ""
    if examples:
        examples_text = (
            f"\n\n📍 <b>Contoh destinasi</b> <i>({len(in_category)} tersedia)</i>\n"
            + "\n".join(f"  ▫️ {escape(name)}" for name in examples)
        )

    await safe_edit(
        query,
        f"<b>{escape(category)}</b>\n"
        f"{LINE}\n\n"
        "✍️ Ketik nama destinasi yang ingin kamu cari."
        f"{examples_text}\n\n"
        "<i>Tekan kategori lain untuk berganti, "
        "atau ketik <b>menu</b> untuk kembali.</i>",
        build_category_keyboard(category),
    )


async def wisata_change_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tombol 'Pilih kategori lain' di bawah detail destinasi."""

    query = update.callback_query
    await query.answer()

    set_mode(context, MODE_WISATA_MENU)
    context.user_data["wisata_category"] = None

    await query.message.reply_text(
        "🏞️ <b>PILIH KATEGORI WISATA</b>\n"
        f"{LINE}\n"
        "<i>Mau jelajah yang mana?</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=build_category_keyboard(),
    )


CHANGE_CATEGORY_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("🔄 Pilih kategori lain", callback_data="wischange")
]])


async def proses_pencarian_destinasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()
    category = context.user_data.get("wisata_category")

    destinations = DESTINATIONS.get()
    if destinations is None:
        # Dataset gagal dimuat: bukan "destinasi tidak ditemukan".
        await reply_html(update, MSG_DATA_DESTINASI_ERROR)
        return

    results = find_destinations(keyword, destinations, category)

    if not results:
        await reply_html(
            update,
            "🔎 <b>Destinasi belum ditemukan</b> 🥹\n"
            f"{LINE}\n\n"
            "💡 <i>Coba periksa kembali nama destinasi atau gunakan nama "
            "yang lebih singkat. Kamu bisa langsung mengetik nama lain.</i>",
        )
        return

    if is_ambiguous(results):
        names = [get_destination_name(r) for _, r in results[:8]]
        more = len(results) - len(names)
        text = (
            f"🔎 <b>Ada beberapa yang cocok</b>\n"
            f"{LINE}\n"
            f"Kata kunci: <b>{escape(keyword)}</b>\n\n"
            + "\n".join(f"  ▫️ {escape(n)}" for n in names)
        )
        if more > 0:
            text += f"\n  ▫️ <i>...dan {more} lainnya</i>"
        text += "\n\n👆 <i>Ketik nama lengkap salah satunya untuk melihat detailnya.</i>"
        await reply_html(update, text)
        return

    best = results[0][1]
    detail = format_destination_detail(best, EVENTS.get(), today_wib())

    # Event hanya dipakai untuk bagian "event terkait"; bila dataset
    # event gagal dimuat, detail destinasi tetap ditampilkan.
    others = [
        get_destination_name(r) for score, r in results[1:4]
        if score >= STRONG_SCORE
    ]
    if others:
        detail += (
            "\n\n💭 <i>Mungkin juga maksudmu: "
            + escape(", ".join(others)) + "</i>"
        )

    await reply_html(
        update, detail, reply_markup=CHANGE_CATEGORY_KEYBOARD
    )


# ---------------------------------------------------------
# Bantuan
# ---------------------------------------------------------

async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_mode(context, MODE_MENU)

    await reply_html(
        update,
        "❓ <b>BANTUAN WISATAKP</b>\n"
        f"{LINE}\n\n"
        "📅 <b>Daftar Event</b>\n"
        "<i>Menampilkan hingga 5 event: yang akan datang, hari ini, "
        "dan kemarin.</i>\n\n"
        "🔍 <b>Cari Event</b>\n"
        "<i>Ketik nama, lokasi, kategori, atau kata kunci event. "
        "Bisa mencari berkali-kali tanpa memilih menu lagi.</i>\n\n"
        "🏞️ <b>Wisata</b>\n"
        "<i>Pilih kategori, lalu ketik nama destinasi (boleh sebagian saja, "
        "contoh: </i><code>glagah</code><i>). Detail lengkap dan link "
        "Google Maps akan ditampilkan. Ketik </i><b>kategori</b>"
        "<i> untuk berganti kategori.</i>\n\n"
        "🔁 <b>Berpindah menu</b>\n"
        "<i>Tekan tombol menu kapan saja, atau ketik </i><b>menu</b>"
        "<i>. Perintah </i><b>/start</b><i> mengulang dari awal.</i>",
    )


# ---------------------------------------------------------
# Router pesan teks (berdasarkan state)
# ---------------------------------------------------------

MENU_ACTIONS = {
    MENU_DAFTAR: daftar_event,
    MENU_CARI: cari_event,
    MENU_WISATA: menu_wisata,
    MENU_BANTUAN: bantuan,
}

BACK_WORDS = {"menu", "menu utama", "kembali"}


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    lowered = text.lower()

    # 1. Tombol menu selalu berlaku: berpindah state.
    action = MENU_ACTIONS.get(text)
    if action:
        await action(update, context)
        return

    if lowered in BACK_WORDS:
        await main_menu(update, context)
        return

    # 2. Selain itu, teks diproses sesuai state aktif.
    mode = get_mode(context)

    if mode == MODE_EVENT_SEARCH:
        await proses_pencarian_event(update, context)

    elif mode in (MODE_WISATA_MENU, MODE_WISATA_SEARCH):
        if lowered in {"kategori", "ganti kategori"}:
            await menu_wisata(update, context)
        else:
            await proses_pencarian_destinasi(update, context)

    else:
        await reply_html(update, MSG_PILIH_MENU)


# =========================================================
# 8. PENANGANAN ERROR
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
        log.info("Pengguna memblokir bot atau chat tidak dapat diakses: %s", error)
        return

    try:  # httpx.* yang belum terbungkus oleh PTB
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
# 9. MAIN
# =========================================================

def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN belum diatur.")

    # Muat dataset di awal agar masalah path langsung terlihat di log.
    events = EVENTS.get()
    destinations = DESTINATIONS.get()
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
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", main_menu))
    app.add_handler(CommandHandler(["bantuan", "help"], bantuan))

    app.add_handler(CallbackQueryHandler(wisata_category_callback, pattern=r"^wiscategory_\d+$"))
    app.add_handler(CallbackQueryHandler(wisata_change_callback, pattern=r"^wischange$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.add_error_handler(error_handler)

    log.info("WisataKP Bot sedang berjalan...")
    app.run_polling(bootstrap_retries=-1)


if __name__ == "__main__":
    main()