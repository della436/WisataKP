# =========================================================
# SCHEDULER WISATAKP
# =========================================================
# Fungsi:
# 1. Menjalankan scraping otomatis setiap 6 jam.
# 2. Mengambil kandidat event hasil scraping.
# 3. Membandingkan event terbaru dengan event sebelumnya.
# 4. Mendeteksi event baru.
# 5. Mencegah event terdeteksi berulang.
# 6. Menyimpan event yang sudah pernah ditemukan.
# 7. Menyiapkan notifikasi event baru ke Telegram.
# 8. Menyediakan mode pengujian scheduler.
# 9. Mengirim pengingat event H-1 ke semua pengguna bot.
# =========================================================


# =========================================================
# IMPORT LIBRARY
# =========================================================

import asyncio
import html
import inspect
import json
import logging
import os
import sys

from datetime import datetime, timedelta, timezone
from pathlib import Path

try:  # python-telegram-bot >= 21
    from telegram import LinkPreviewOptions

    NO_PREVIEW = {"link_preview_options": LinkPreviewOptions(is_disabled=True)}
except ImportError:  # python-telegram-bot 20.x / belum terpasang
    NO_PREVIEW = {"disable_web_page_preview": True}


# =========================================================
# KONFIGURASI LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# KONFIGURASI SCHEDULER
# =========================================================

# Interval scraping otomatis dalam jam.
SCRAPING_INTERVAL_HOURS = 6

# Mengubah jam menjadi detik.
SCRAPING_INTERVAL_SECONDS = SCRAPING_INTERVAL_HOURS * 3600

# Chat ID Telegram (opsional: admin/channel yang selalu ikut menerima pengingat).
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Zona waktu WIB dan jam paling awal pengingat H-1 boleh dikirim.
WIB = timezone(timedelta(hours=7))
REMINDER_HOUR_WIB = 8


# =========================================================
# MENENTUKAN DIREKTORI PROJECT
# =========================================================

# Lokasi folder scraping.
BASE_DIR = Path(__file__).resolve().parent

# Root project WisataKP.
PROJECT_DIR = BASE_DIR.parent

# Memasukkan root project ke Python path.
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# Folder penyimpanan event.
EVENT_DIR = PROJECT_DIR / "data" / "events"

# File penyimpanan event yang pernah ditemukan.
SEEN_EVENTS_FILE = EVENT_DIR / "seen_events.json"

# Pengguna bot yang menerima pengingat (diisi bot.py saat /start).
SUBSCRIBERS_FILE = EVENT_DIR / "subscribers.json"

# Event yang pengingat H-1-nya sudah terkirim (mencegah kirim ganda).
REMINDED_EVENTS_FILE = EVENT_DIR / "reminded_events.json"


# =========================================================
# MEMBUAT DIREKTORI
# =========================================================

def create_scheduler_directories():
    """
    Membuat folder penyimpanan scheduler
    jika folder belum tersedia.
    """
    EVENT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# MEMBACA EVENT YANG SUDAH PERNAH DITEMUKAN
# =========================================================

def load_seen_events():
    """
    Membaca ID event yang sebelumnya telah disimpan.

    Return:
        set : kumpulan ID event yang sudah pernah ditemukan.
    """

    create_scheduler_directories()

    if not SEEN_EVENTS_FILE.exists():
        return set()

    try:
        with open(SEEN_EVENTS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            logger.warning(
                "Format seen_events.json tidak valid. "
                "Data harus berupa list."
            )
            return set()

        # Hanya mengambil data berupa string yang tidak kosong.
        return {
            str(event_id).strip()
            for event_id in data
            if event_id
        }

    except (json.JSONDecodeError, OSError) as error:
        logger.error(
            "Gagal membaca data event: %s",
            error
        )
        return set()


# =========================================================
# MENYIMPAN EVENT YANG SUDAH DITEMUKAN
# =========================================================

def save_seen_events(seen_events):
    """
    Menyimpan ID event yang sudah ditemukan.

    File ini digunakan untuk mencegah event
    yang sama diproses berulang kali.
    """

    create_scheduler_directories()

    try:
        data = sorted(set(seen_events))

        with open(
            SEEN_EVENTS_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False
            )

        logger.info(
            "Data event berhasil disimpan: %s event.",
            len(data)
        )

        return True

    except OSError as error:
        logger.error(
            "Gagal menyimpan data event: %s",
            error
        )

        return False


# =========================================================
# MEMBUAT ID EVENT
# =========================================================

def get_event_id(event):
    """
    Membuat identitas unik event.

    URL digunakan sebagai identitas utama.
    Jika URL tidak tersedia, judul digunakan sebagai alternatif.
    """

    # Mengambil URL event.
    url = str(event.get("url", "")).strip()

    # URL menjadi identitas utama.
    if url:
        return url.lower().rstrip("/")

    # Mengambil judul sebagai alternatif.
    title = str(
        event.get(
            "judul",
            event.get(
                "title",
                event.get("nama_event", "")
            )
        )
    ).strip().lower()

    # Jika judul kosong, event tidak memiliki identitas.
    if not title:
        return ""

    # Menggunakan judul sebagai identitas alternatif.
    return title


# =========================================================
# MENDETEKSI EVENT BARU
# =========================================================

def detect_new_events(events, seen_events):
    """
    Membandingkan event terbaru dengan event sebelumnya.

    Return:
        new_events          : event baru.
        updated_seen_events : ID seluruh event terbaru.
    """

    new_events = []

    # Salinan data event sebelumnya.
    updated_seen_events = set(seen_events)

    # ID yang ditemukan pada pemeriksaan saat ini.
    current_event_ids = set()

    for event in events:

        # Membuat identitas event.
        event_id = get_event_id(event)

        # Melewati event tanpa identitas.
        if not event_id:
            continue

        # Mencegah duplikasi dalam satu hasil scraping.
        if event_id in current_event_ids:
            continue

        current_event_ids.add(event_id)

        # Memeriksa event baru.
        if event_id not in updated_seen_events:

            new_events.append(event)

            # Memasukkan ID agar tidak terdeteksi ulang.
            updated_seen_events.add(event_id)

    return new_events, updated_seen_events


# =========================================================
# FORMAT PESAN NOTIFIKASI EVENT
# =========================================================

def format_event_notification(events):
    """
    Membuat pesan notifikasi event baru untuk Telegram.
    """

    message = (
        "🌴 <b>WisataKP - Event Baru!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )

    for index, event in enumerate(events, start=1):

        # Mengambil informasi event.
        title = event.get(
            "judul",
            event.get("title", "Event baru")
        )

        location = event.get(
            "lokasi_event",
            event.get("location", "Lokasi belum tersedia")
        )

        date = event.get(
            "tanggal_event",
            event.get("date", "Tanggal belum tersedia")
        )

        summary = event.get(
            "ringkasan",
            "Ringkasan belum tersedia"
        )

        url = event.get("url", "")

        # Mengamankan teks dari karakter HTML.
        title = html.escape(str(title))
        location = html.escape(str(location))
        date = html.escape(str(date))
        summary = html.escape(str(summary))

        # Informasi event.
        message += (
            f"<b>{index}. {title}</b>\n"
            f"📍 {location}\n"
            f"📅 {date}\n"
        )

        # Ringkasan.
        if summary and summary != "Ringkasan belum tersedia":
            message += f"📝 {summary}\n"

        # Link sumber.
        if url:
            safe_url = html.escape(
                str(url),
                quote=True
            )

            message += (
                f'🔗 <a href="{safe_url}">Lihat sumber</a>\n'
            )

        message += "\n"

    return message


# =========================================================
# MENGIRIM NOTIFIKASI TELEGRAM
# =========================================================

async def send_notification(application, events):
    """
    Mengirim notifikasi event baru ke Telegram.

    Return:
        True  : pesan berhasil dikirim.
        False : pesan gagal dikirim.
    """

    # Tidak ada event baru.
    if not events:
        return True

    # Memeriksa Chat ID.
    if not TELEGRAM_CHAT_ID:
        logger.warning(
            "TELEGRAM_CHAT_ID belum diatur."
        )
        return False

    # Memeriksa Telegram Application.
    if application is None or not getattr(
        application,
        "bot",
        None
    ):
        logger.warning(
            "Telegram Application belum tersedia."
        )
        return False

    # Membuat pesan.
    message = format_event_notification(events)

    try:

        # Mengirim pesan.
        await application.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        logger.info(
            "Notifikasi berhasil dikirim untuk %s event.",
            len(events)
        )

        return True

    except Exception as error:

        logger.exception(
            "Gagal mengirim notifikasi Telegram: %s",
            error
        )

        return False


# =========================================================
# PENYIMPANAN DAFTAR PENERIMA DAN EVENT YANG SUDAH DIINGATKAN
# =========================================================

def _read_list(path):
    """Membaca file JSON berisi list; list kosong bila belum ada/rusak."""

    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []

    except (json.JSONDecodeError, OSError) as error:
        logger.error("Gagal membaca %s: %s", path.name, error)
        return []


def _write_list(path, items):
    """Menulis list ke JSON (lewat file sementara agar tidak setengah tertulis)."""

    create_scheduler_directories()
    temp_path = path.with_name(path.name + ".tmp")

    try:
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(items, file, indent=4, ensure_ascii=False)

        temp_path.replace(path)
        return True

    except OSError as error:
        logger.error("Gagal menyimpan %s: %s", path.name, error)
        return False


def load_subscribers():
    """Chat ID pengguna yang menerima pengingat."""

    return {
        chat_id
        for chat_id in _read_list(SUBSCRIBERS_FILE)
        if isinstance(chat_id, int)
    }


def add_subscriber(chat_id):
    """Dipanggil bot.py saat pengguna menekan /start."""

    subscribers = load_subscribers()

    if chat_id not in subscribers:
        subscribers.add(chat_id)
        _write_list(SUBSCRIBERS_FILE, sorted(subscribers))
        logger.info("Penerima pengingat bertambah: %s", chat_id)


def remove_subscriber(chat_id):
    """Dipanggil bot.py saat /berhenti, atau saat bot diblokir pengguna."""

    subscribers = load_subscribers()

    if chat_id in subscribers:
        subscribers.discard(chat_id)
        _write_list(SUBSCRIBERS_FILE, sorted(subscribers))
        logger.info("Penerima pengingat dihapus: %s", chat_id)


def get_notification_chat_ids():
    """Seluruh penerima: pengguna bot + TELEGRAM_CHAT_ID (jika diatur)."""

    chat_ids = list(load_subscribers())

    if TELEGRAM_CHAT_ID:
        try:
            extra = int(TELEGRAM_CHAT_ID)
        except ValueError:
            extra = TELEGRAM_CHAT_ID  # mis. @namachannel

        if extra not in chat_ids:
            chat_ids.append(extra)

    return chat_ids


# =========================================================
# PENGINGAT EVENT H-1
# =========================================================

async def broadcast(application, chat_ids, text):
    """
    Mengirim satu pesan ke banyak chat.

    Return:
        int : jumlah chat yang berhasil menerima pesan.
    """

    from telegram.error import Forbidden, RetryAfter

    sent = 0

    for chat_id in chat_ids:

        for attempt in (1, 2):

            try:
                await application.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML",
                    **NO_PREVIEW
                )
                sent += 1
                break

            except Forbidden:
                # Pengguna memblokir bot: hapus dari daftar penerima.
                remove_subscriber(chat_id)
                break

            except RetryAfter as error:
                # Kena batas kirim Telegram: tunggu lalu coba sekali lagi.
                if attempt == 2:
                    break
                await asyncio.sleep(error.retry_after + 1)

            except Exception as error:
                logger.warning(
                    "Gagal mengirim pengingat ke %s: %s",
                    chat_id,
                    error
                )
                break

        # Telegram membatasi sekitar 30 pesan per detik.
        await asyncio.sleep(0.05)

    return sent


async def run_reminder_check(
    application,
    reminder_callback,
    now=None
):
    """
    Mengirim pengingat untuk event yang berlangsung besok (H-1).

    reminder_callback dari bot.py mengembalikan
    [(id_event, pesan_html), ...] untuk event yang dimulai besok.

    Aturan:
        - Dikirim paling cepat jam REMINDER_HOUR_WIB WIB.
        - Setiap event hanya diingatkan sekali (reminded_events.json).
        - Event ditandai terkirim hanya jika minimal satu pesan berhasil.
    """

    if application is None or reminder_callback is None:
        return

    now = now or datetime.now(WIB)

    if now.hour < REMINDER_HOUR_WIB:
        logger.info(
            "Belum jam %02d:00 WIB, pengingat H-1 ditunda.",
            REMINDER_HOUR_WIB
        )
        return

    try:

        reminders = reminder_callback()

        reminded = set(_read_list(REMINDED_EVENTS_FILE))

        pending = [
            (event_id, text)
            for event_id, text in reminders
            if event_id not in reminded
        ]

        if not pending:
            logger.info("Tidak ada pengingat H-1 yang perlu dikirim.")
            return

        chat_ids = get_notification_chat_ids()

        if not chat_ids:
            logger.info(
                "Ada %s pengingat H-1 tetapi belum ada penerima.",
                len(pending)
            )
            return

        for event_id, text in pending:

            sent = await broadcast(application, chat_ids, text)

            if sent:
                reminded.add(event_id)

            logger.info(
                "Pengingat H-1 terkirim ke %s dari %s penerima: %s",
                sent,
                len(chat_ids),
                event_id
            )

        _write_list(REMINDED_EVENTS_FILE, sorted(reminded))

    except Exception as error:

        # Error pengingat tidak boleh menghentikan scheduler.
        logger.exception(
            "Terjadi kesalahan saat mengirim pengingat H-1: %s",
            error
        )


# =========================================================
# FILTERING & VALIDASI EVENT (menghasilkan event_valid.csv)
# =========================================================

# Folder tempat filtering_event.py dan validation_event.py dicari.
PIPELINE_DIRS = [
    BASE_DIR,
    PROJECT_DIR / "scraping",
    PROJECT_DIR / "validation",
    PROJECT_DIR / "filtering",
    PROJECT_DIR,
]


def load_pipeline_module(name):
    """
    Memuat script pipeline berdasarkan nama file (tanpa .py),
    di folder mana pun ia berada pada PIPELINE_DIRS.
    """

    import importlib.util

    for folder in PIPELINE_DIRS:

        path = folder / f"{name}.py"

        if path.is_file():

            spec = importlib.util.spec_from_file_location(
                name,
                path
            )

            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            return module

    raise FileNotFoundError(
        f"{name}.py tidak ditemukan di: "
        + ", ".join(str(folder) for folder in PIPELINE_DIRS)
    )


def run_event_pipeline():
    """
    Menjalankan filtering + ekstraksi, lalu validasi:

        event_wisata.csv -> event_candidates.csv -> event_valid.csv

    event_valid.csv adalah file yang dibaca bot. Tanpa langkah ini,
    event baru hasil scraping tidak punya tanggal dan lokasi sehingga
    tidak tampil di bot dan tidak mendapat pengingat H-1.

    Error di sini tidak menghentikan pemeriksaan scraping.
    """

    # Script pipeline memakai path relatif dari root project.
    os.chdir(PROJECT_DIR)

    for name in ("filtering_event", "validation_event"):

        try:

            logger.info("Menjalankan %s...", name)

            load_pipeline_module(name).main()

        except Exception as error:

            logger.exception(
                "Gagal menjalankan %s: %s. "
                "event_valid.csv tidak diperbarui.",
                name,
                error
            )

            return False

    logger.info("event_valid.csv berhasil diperbarui.")

    return True


# =========================================================
# MENGHUBUNGKAN SCHEDULER DENGAN SCRAPER WISATAKP
# =========================================================

def scrape_wisata_kp():
    """
    Menjalankan scraping WisataKP.

    Tahapan:
        1. Mengatur working directory.
        2. Mengimpor scraper.
        3. Menjalankan scraping incremental.
        4. Mengekstrak kandidat event.
        5. Menjalankan filtering dan validasi (event_valid.csv).
        6. Membaca CSV event.
        7. Mengembalikan event dalam list dictionary.
    """

    # Mengatur direktori aktif ke root project.
    os.chdir(PROJECT_DIR)

    # Mengimpor scraper.
    from scraping import scraper_event

    # Scraping artikel terbaru.
    logger.info(
        "Menjalankan scraping artikel WisataKP..."
    )

    scraper_event.scrape_incremental()

    # Mengekstrak kandidat event.
    logger.info(
        "Mengekstrak kandidat event..."
    )

    scraper_event.extract_event_candidates()

    # Filtering, ekstraksi tanggal/lokasi, dan validasi
    # sehingga event baru masuk ke event_valid.csv untuk bot.
    run_event_pipeline()

    # Mengambil lokasi file event.
    event_file = Path(scraper_event.EVENT_FILE)

    # Memastikan path menjadi absolut.
    if not event_file.is_absolute():
        event_file = PROJECT_DIR / event_file

    # Memeriksa file.
    if not event_file.exists():

        logger.warning(
            "File kandidat event tidak ditemukan: %s",
            event_file
        )

        return []

    # Membaca CSV.
    import pandas as pd

    df = pd.read_csv(event_file)

    # Jika data kosong.
    if df.empty:

        logger.info(
            "Data kandidat event kosong."
        )

        return []

    # Menghapus duplikasi URL.
    if "url" in df.columns:

        df = df.drop_duplicates(
            subset=["url"]
        )

    # Mengubah DataFrame menjadi list dictionary.
    events = df.to_dict(
        orient="records"
    )

    logger.info(
        "Scraping selesai. Total kandidat event: %s",
        len(events)
    )

    return events


# =========================================================
# MENJALANKAN SATU KALI PEMERIKSAAN SCRAPING
# =========================================================

async def run_scraping_check(
    application,
    scrape_callback
):
    """
    Menjalankan satu kali pemeriksaan scraping.

    Proses:
        1. Menjalankan scraper.
        2. Membaca event sebelumnya.
        3. Membuat baseline pada pemeriksaan pertama.
        4. Mendeteksi event baru.
        5. Mengirim notifikasi jika Telegram terhubung.
        6. Menyimpan event yang berhasil diproses.
    """

    logger.info("=" * 50)
    logger.info(
        "MEMULAI PEMERIKSAAN SCRAPING WISATAKP"
    )
    logger.info("=" * 50)

    try:

        # Menjalankan callback scraping.
        if inspect.iscoroutinefunction(scrape_callback):

            events = await scrape_callback()

        else:

            events = await asyncio.to_thread(
                scrape_callback
            )

        # Memastikan hasil scraping berupa list.
        if not isinstance(events, list):

            logger.warning(
                "Hasil scraping tidak berbentuk list."
            )

            return

        logger.info(
            "Jumlah event yang diperiksa: %s",
            len(events)
        )

        # Membaca event sebelumnya.
        seen_events = load_seen_events()

        # =================================================
        # BASELINE / PEMERIKSAAN PERTAMA
        # =================================================

        if not SEEN_EVENTS_FILE.exists():

            # Membuat ID seluruh event awal.
            initial_event_ids = {
                get_event_id(event)
                for event in events
                if get_event_id(event)
            }

            # Menyimpan baseline.
            save_seen_events(initial_event_ids)

            logger.info(
                "Baseline awal berhasil dibuat: %s event.",
                len(initial_event_ids)
            )

            logger.info(
                "Notifikasi tidak dikirim pada pemeriksaan pertama."
            )

            return

        # =================================================
        # DETEKSI EVENT BARU
        # =================================================

        new_events, updated_seen_events = detect_new_events(
            events,
            seen_events
        )

        # =================================================
        # JIKA TIDAK ADA EVENT BARU
        # =================================================

        if not new_events:

            logger.info(
                "Tidak ditemukan event baru."
            )

            save_seen_events(
                updated_seen_events
            )

            return

        # =================================================
        # JIKA TERDAPAT EVENT BARU
        # =================================================

        logger.info(
            "Ditemukan %s event baru!",
            len(new_events)
        )

        # Menampilkan event baru.
        for event in new_events:

            title = event.get(
                "judul",
                "Event tanpa judul"
            )

            logger.info(
                "Event baru: %s",
                title
            )

        # =================================================
        # PENGIRIMAN NOTIFIKASI
        # =================================================

        # Event baru tidak dikirim saat ditemukan. Pengingatnya dikirim
        # H-1 sebelum acara oleh run_reminder_check(), sehingga cukup
        # dicatat di sini agar tidak terdeteksi berulang.
        notification_success = True

        logger.info(
            "Event baru dicatat. "
            "Pengingat akan dikirim H-1 sebelum acara."
        )

        # =================================================
        # MENYIMPAN EVENT YANG SUDAH DIPROSES
        # =================================================

        if notification_success:

            save_seen_events(
                updated_seen_events
            )

            logger.info(
                "Event baru berhasil diproses dan disimpan."
            )

        else:

            logger.warning(
                "Proses notifikasi gagal. "
                "Event baru belum ditandai sebagai berhasil."
            )

    except Exception as error:

        # Menangani error agar scheduler tidak berhenti.
        logger.exception(
            "Terjadi kesalahan saat pemeriksaan scraping: %s",
            error
        )

    finally:

        logger.info(
            "Pemeriksaan scraping selesai."
        )

        logger.info("=" * 50)


# =========================================================
# LOOP SCHEDULER
# =========================================================

async def scheduler_loop(
    application,
    scrape_callback,
    reminder_callback=None
):
    """
    Menjalankan scheduler secara berulang.

    Scraping langsung dijalankan saat scheduler dimulai,
    lalu pengingat H-1 diperiksa.
    Setelah selesai, scheduler menunggu 6 jam.
    """

    while True:

        # Menjalankan pemeriksaan scraping.
        await run_scraping_check(
            application,
            scrape_callback
        )

        # Mengirim pengingat event yang berlangsung besok.
        await run_reminder_check(
            application,
            reminder_callback
        )

        logger.info(
            "Scraping berikutnya akan berjalan dalam %s jam.",
            SCRAPING_INTERVAL_HOURS
        )

        # Menunggu interval berikutnya.
        await asyncio.sleep(
            SCRAPING_INTERVAL_SECONDS
        )


# =========================================================
# MEMULAI SCHEDULER
# =========================================================

async def start_scheduler(
    application,
    scrape_callback=scrape_wisata_kp,
    reminder_callback=None
):
    """
    Memulai scheduler sebagai background task.
    """

    # Mengambil task yang mungkin sudah berjalan.
    existing_task = getattr(
        application,
        "scheduler_task",
        None
    )

    # Mencegah scheduler berjalan dua kali.
    if existing_task and not existing_task.done():

        logger.warning(
            "Scheduler sudah berjalan."
        )

        return

    # Membuat background task.
    application.scheduler_task = asyncio.create_task(
        scheduler_loop(
            application,
            scrape_callback,
            reminder_callback
        )
    )

    logger.info(
        "Scheduler berhasil dimulai. "
        "Interval: setiap %s jam.",
        SCRAPING_INTERVAL_HOURS
    )


# =========================================================
# MENGHENTIKAN SCHEDULER
# =========================================================

async def stop_scheduler(application):
    """
    Menghentikan scheduler secara aman.
    """

    task = getattr(
        application,
        "scheduler_task",
        None
    )

    # Jika task tidak tersedia.
    if task is None:

        logger.info(
            "Scheduler tidak sedang berjalan."
        )

        return

    # Membatalkan task jika masih berjalan.
    if not task.done():

        task.cancel()

        try:

            await task

        except asyncio.CancelledError:

            logger.info(
                "Task scheduler berhasil dibatalkan."
            )

    # Menghapus referensi task.
    application.scheduler_task = None

    logger.info(
        "Scheduler berhasil dihentikan."
    )


# =========================================================
# PENGUJIAN DETEKSI EVENT BARU DAN ANTI-DUPLIKASI
# =========================================================

def test_event_detection():
    """
    Menguji:
    1. Event baru terdeteksi.
    2. Event lama tidak terdeteksi ulang.
    3. Event duplikat dalam satu scraping tidak dihitung berulang.
    """

    logger.info("=" * 50)
    logger.info("TEST DETEKSI EVENT DAN ANTI-DUPLIKASI")
    logger.info("=" * 50)

    # Event yang sudah pernah ditemukan.
    seen_events = {
        "https://contoh.com/event-lama"
    }

    # Simulasi hasil scraping terbaru.
    sample_events = [
        {
            "judul": "Event Lama",
            "url": "https://contoh.com/event-lama"
        },
        {
            "judul": "Event Baru",
            "url": "https://contoh.com/event-baru"
        },
        {
            "judul": "Event Baru",
            "url": "https://contoh.com/event-baru"
        }
    ]

    # Menjalankan deteksi.
    new_events, updated_seen_events = detect_new_events(
        sample_events,
        seen_events
    )

    # Memastikan hanya 1 event baru ditemukan.
    assert len(new_events) == 1, (
        "TEST GAGAL: Jumlah event baru tidak sesuai."
    )

    # Memastikan event baru benar.
    assert new_events[0]["judul"] == "Event Baru", (
        "TEST GAGAL: Event baru yang ditemukan salah."
    )

    # Memastikan ID event baru sudah tersimpan.
    assert (
        "https://contoh.com/event-baru"
        in updated_seen_events
    ), (
        "TEST GAGAL: ID event baru belum tersimpan."
    )

    # Melakukan pengecekan ulang.
    second_check, second_updated_seen = detect_new_events(
        sample_events,
        updated_seen_events
    )

    # Memastikan tidak ada event yang terdeteksi ulang.
    assert len(second_check) == 0, (
        "TEST GAGAL: Event terdeteksi berulang."
    )

    logger.info(
        "TEST DETEKSI EVENT BARU: BERHASIL"
    )

    logger.info(
        "TEST ANTI-DUPLIKASI: BERHASIL"
    )

    logger.info(
        "TEST EVENT LAMA: BERHASIL"
    )

    logger.info(
        "TEST EVENT BARU TIDAK TERDETEKSI ULANG: BERHASIL"
    )

    logger.info("=" * 50)

    return True


# =========================================================
# PENGUJIAN BASELINE DAN SIKLUS PEMERIKSAAN
# =========================================================

async def test_scheduler_cycle():
    """
    Menguji siklus scheduler secara simulasi.

    Pengujian:
    1. Baseline pertama.
    2. Event baru muncul.
    3. Event baru berhasil dicatat.
    4. Event yang sama tidak terdeteksi ulang.

    Pengujian menggunakan file sementara sehingga
    seen_events.json asli tidak diubah.
    """

    import tempfile

    from unittest.mock import patch

    logger.info("=" * 50)
    logger.info("TEST SIKLUS SCHEDULER")
    logger.info("=" * 50)

    # Membuat folder sementara.
    with tempfile.TemporaryDirectory() as temp_dir:

        temp_path = Path(temp_dir)

        temp_event_dir = temp_path / "events"

        temp_seen_file = (
            temp_event_dir / "seen_events.json"
        )

        temp_event_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        # Data baseline awal.
        baseline_events = [
            {
                "judul": "Event Lama",
                "url": "https://contoh.com/event-lama"
            }
        ]

        # Data setelah event baru muncul.
        updated_events = [
            {
                "judul": "Event Lama",
                "url": "https://contoh.com/event-lama"
            },
            {
                "judul": "Event Baru",
                "url": "https://contoh.com/event-baru"
            }
        ]

        # Simulasi data scraping.
        scraping_results = [
            baseline_events,
            updated_events,
            updated_events
        ]

        call_count = 0

        def fake_scraper():

            nonlocal call_count

            result = scraping_results[
                min(
                    call_count,
                    len(scraping_results) - 1
                )
            ]

            call_count += 1

            return result

        # Mengganti file penyimpanan asli
        # dengan file sementara.
        with patch(
            __name__ + ".EVENT_DIR",
            temp_event_dir
        ), patch(
            __name__ + ".SEEN_EVENTS_FILE",
            temp_seen_file
        ):

            # =============================================
            # CHECK 1: BASELINE
            # =============================================

            logger.info(
                "TEST CHECK 1: BASELINE AWAL"
            )

            await run_scraping_check(
                application=None,
                scrape_callback=fake_scraper
            )

            assert temp_seen_file.exists(), (
                "TEST GAGAL: File baseline tidak dibuat."
            )

            baseline_saved = load_seen_events()

            assert (
                "https://contoh.com/event-lama"
                in baseline_saved
            ), (
                "TEST GAGAL: Event baseline tidak tersimpan."
            )

            logger.info(
                "TEST BASELINE: BERHASIL"
            )

            # =============================================
            # CHECK 2: EVENT BARU
            # =============================================

            logger.info(
                "TEST CHECK 2: DETEKSI EVENT BARU"
            )

            await run_scraping_check(
                application=None,
                scrape_callback=fake_scraper
            )

            events_after_new = load_seen_events()

            assert (
                "https://contoh.com/event-baru"
                in events_after_new
            ), (
                "TEST GAGAL: Event baru tidak tersimpan."
            )

            logger.info(
                "TEST DETEKSI DAN PENYIMPANAN EVENT BARU: BERHASIL"
            )

            # =============================================
            # CHECK 3: EVENT DUPLIKAT
            # =============================================

            logger.info(
                "TEST CHECK 3: ANTI-DUPLIKASI"
            )

            await run_scraping_check(
                application=None,
                scrape_callback=fake_scraper
            )

            events_after_duplicate = load_seen_events()

            # Memastikan jumlah ID tidak bertambah.
            assert (
                len(events_after_duplicate)
                == len(events_after_new)
            ), (
                "TEST GAGAL: Jumlah event bertambah karena duplikasi."
            )

            logger.info(
                "TEST ANTI-DUPLIKASI SIKLUS: BERHASIL"
            )

    logger.info(
        "SELURUH TEST SIKLUS SCHEDULER BERHASIL."
    )

    logger.info("=" * 50)

    return True


# =========================================================
# PENGUJIAN PENGINGAT H-1
# =========================================================

async def test_reminder_flow():
    """
    Menguji:
    1. Pengingat tidak dikirim sebelum jam 08:00 WIB.
    2. Pengingat dikirim ke semua penerima.
    3. Event yang sama tidak diingatkan dua kali.
    4. Pengguna yang memblokir bot dihapus dari daftar penerima.

    Pengujian menggunakan file sementara.
    """

    import tempfile

    from types import SimpleNamespace
    from unittest.mock import patch

    logger.info("=" * 50)
    logger.info("TEST PENGINGAT H-1")
    logger.info("=" * 50)

    sent_messages = []

    class FakeBot:

        async def send_message(self, chat_id, text, **kwargs):

            if chat_id == 999:
                from telegram.error import Forbidden
                raise Forbidden("bot diblokir")

            sent_messages.append((chat_id, text))

    fake_app = SimpleNamespace(bot=FakeBot())

    def fake_reminders():
        return [("https://contoh.com/event-besok", "pesan pengingat")]

    with tempfile.TemporaryDirectory() as temp_dir:

        temp_path = Path(temp_dir)

        with patch(
            __name__ + ".EVENT_DIR", temp_path
        ), patch(
            __name__ + ".SUBSCRIBERS_FILE", temp_path / "subscribers.json"
        ), patch(
            __name__ + ".REMINDED_EVENTS_FILE", temp_path / "reminded.json"
        ), patch(
            __name__ + ".TELEGRAM_CHAT_ID", None
        ):

            add_subscriber(111)
            add_subscriber(222)
            add_subscriber(999)

            # CHECK 1: terlalu pagi.
            pagi = datetime(2026, 11, 29, 6, 0, tzinfo=WIB)

            await run_reminder_check(fake_app, fake_reminders, now=pagi)

            assert not sent_messages, (
                "TEST GAGAL: Pengingat terkirim sebelum jam 08:00."
            )

            # CHECK 2: jam kirim.
            siang = datetime(2026, 11, 29, 9, 0, tzinfo=WIB)

            await run_reminder_check(fake_app, fake_reminders, now=siang)

            assert sorted(chat for chat, _ in sent_messages) == [111, 222], (
                "TEST GAGAL: Penerima pengingat tidak sesuai."
            )

            # CHECK 3: pengguna yang memblokir bot dihapus.
            assert 999 not in load_subscribers(), (
                "TEST GAGAL: Pengguna yang memblokir bot masih terdaftar."
            )

            # CHECK 4: tidak dikirim ulang.
            await run_reminder_check(fake_app, fake_reminders, now=siang)

            assert len(sent_messages) == 2, (
                "TEST GAGAL: Pengingat terkirim berulang."
            )

    logger.info("TEST PENGINGAT H-1: BERHASIL")
    logger.info("=" * 50)

    return True


# =========================================================
# TEST FINAL SCHEDULER
# =========================================================

async def run_scheduler_tests():
    """
    Menjalankan seluruh pengujian scheduler.
    """

    logger.info("")
    logger.info("=" * 60)
    logger.info("MEMULAI PENGUJIAN FINAL SCHEDULER WISATAKP")
    logger.info("=" * 60)

    # TEST 1: Deteksi event dan anti-duplikasi.
    test_event_detection()

    # TEST 2: Baseline, event baru, dan siklus.
    await test_scheduler_cycle()

    # TEST 3: Pengingat H-1.
    await test_reminder_flow()

    # TEST 4: Konfigurasi interval.
    assert SCRAPING_INTERVAL_HOURS == 6, (
        "TEST GAGAL: Interval scheduler bukan 6 jam."
    )

    assert SCRAPING_INTERVAL_SECONDS == 21600, (
        "TEST GAGAL: Konversi interval ke detik salah."
    )

    logger.info(
        "TEST INTERVAL 6 JAM: BERHASIL"
    )

    logger.info("")
    logger.info("=" * 60)
    logger.info("SELURUH PENGUJIAN FINAL BERHASIL")
    logger.info("=" * 60)


# =========================================================
# MODE TEST SCHEDULER (STANDALONE)
# =========================================================

if __name__ == "__main__":

    # Menjalankan mode pengujian final.
    if "--test" in sys.argv:

        logger.info(
            "Menjalankan TEST FINAL SCHEDULER WISATAKP..."
        )

        asyncio.run(
            run_scheduler_tests()
        )

    # Mode normal: menjalankan scraping sekali.
    else:

        logger.info(
            "Menjalankan TEST SCHEDULER WISATAKP..."
        )

        asyncio.run(
            run_scraping_check(
                application=None,
                scrape_callback=scrape_wisata_kp
            )
        )

        logger.info(
            "TEST SCHEDULER SELESAI."
        )