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

from pathlib import Path


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

# Chat ID Telegram.
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


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
        5. Membaca CSV event.
        6. Mengembalikan event dalam list dictionary.
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

        if application is not None:

            # Mengirim notifikasi Telegram.
            notification_success = await send_notification(
                application,
                new_events
            )

        else:

            # Mode test tanpa Telegram.
            notification_success = True

            logger.info(
                "Mode test tanpa Telegram. "
                "Event baru hanya ditampilkan di terminal."
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
    scrape_callback
):
    """
    Menjalankan scheduler secara berulang.

    Scraping langsung dijalankan saat scheduler dimulai.
    Setelah selesai, scheduler menunggu 6 jam.
    """

    while True:

        # Menjalankan pemeriksaan scraping.
        await run_scraping_check(
            application,
            scrape_callback
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
    scrape_callback=scrape_wisata_kp
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
            scrape_callback
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

    # TEST 3: Konfigurasi interval.
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