
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
from datetime import datetime
import time
import os
import re
import argparse

# =========================================================
# KONFIGURASI
# =========================================================

BASE_URL = "https://dinpar.kulonprogokab.go.id"

START_URL = (
    "https://dinpar.kulonprogokab.go.id/"
    "publikasi/berita"
)

MAX_PAGES_INITIAL = 19
MAX_PAGES_INCREMENTAL = 3

OUTPUT_DIR = "data/scraping"
EVENT_DIR = "data/events"

RAW_FILE = os.path.join(
    OUTPUT_DIR,
    "artikel_raw.csv"
)

EVENT_FILE = os.path.join(
    EVENT_DIR,
    "event_wisata.csv"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 30
DELAY = 0.5

# Kata yang mengindikasikan artikel kemungkinan membahas event.
# Ini hanya filter awal, bukan jaminan artikel benar-benar event.
EVENT_KEYWORDS = [
    "festival",
    "event",
    "acara",
    "gelar",
    "pentas",
    "lomba",
    "kirab",
    "parade",
    "pagelaran",
    "pertunjukan",
    "konser",
    "perayaan",
    "expo",
    "exhibition",
    "pameran",
    "kejuaraan",
    "turnamen",
    "fun run",
    "fun walk",
    "jalan sehat",
    "bazar",
    "agenda",
    "kompetisi",
    "workshop",
]

# =========================================================
# SESSION
# =========================================================

session = requests.Session()
session.headers.update(HEADERS)


# =========================================================
# UTILITAS
# =========================================================

def clean_text(text):
    """
    Membersihkan spasi berlebih dan karakter whitespace.
    """

    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_title(title):
    """
    Membersihkan judul artikel dari teks navigasi/noise.
    """

    title = clean_text(title)

    unwanted = [
        "selengkapnya",
        "baca selengkapnya",
        "read more",
    ]

    for phrase in unwanted:
        title = re.sub(
            phrase,
            "",
            title,
            flags=re.IGNORECASE
        )

    title = clean_text(title)

    return title


def create_directories():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(EVENT_DIR, exist_ok=True)


def get_soup(url):
    """
    Mengambil HTML website.
    """

    try:
        response = session.get(
            url,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        return BeautifulSoup(
            response.text,
            "html.parser"
        )

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Gagal mengakses {url}")
        print(f"[DETAIL] {e}")

        return None


# =========================================================
# 1. SCRAPING DAFTAR ARTIKEL
# =========================================================

def scrape_article_list(page_url):
    """
    Mengambil judul dan URL artikel dari halaman publikasi.
    """

    soup = get_soup(page_url)

    if soup is None:
        return []

    articles = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):

        href = link.get("href", "").strip()

        if "/publikasi/detail/" not in href:
            continue

        article_url = urljoin(
            BASE_URL,
            href
        )

        # Menghindari URL duplikat dalam satu halaman
        if article_url in seen_urls:
            continue

        seen_urls.add(article_url)

        # Mengambil judul
        title = clean_title(
            link.get_text(" ", strip=True)
        )

        # Jika judul link kosong, coba ambil dari elemen sekitar
        if not title:

            parent = link.find_parent()

            if parent:
                title = clean_title(
                    parent.get_text(" ", strip=True)
                )

        if not title:
            continue

        articles.append({
            "judul": title,
            "url": article_url
        })

    return articles


# =========================================================
# 2. SCRAPING DETAIL ARTIKEL
# =========================================================

def scrape_article_detail(url):
    """
    Mengambil informasi detail dari artikel.
    """

    data = {
        "ringkasan": "",
        "tanggal_publikasi": ""
    }

    soup = get_soup(url)

    if soup is None:
        return data

    # -----------------------------------------------------
    # Mengambil teks artikel
    # -----------------------------------------------------

    paragraphs = soup.find_all("p")

    article_paragraphs = []

    for paragraph in paragraphs:

        text = clean_text(
            paragraph.get_text(" ", strip=True)
        )

        if len(text) < 40:
            continue

        # Menghindari teks navigasi
        if text.lower() in [
            "baca selengkapnya",
            "selengkapnya",
        ]:
            continue

        article_paragraphs.append(text)

    if article_paragraphs:

        full_text = " ".join(
            article_paragraphs
        )

        data["ringkasan"] = full_text[:1500]

    # -----------------------------------------------------
    # Mengambil tanggal publikasi
    # -----------------------------------------------------

    time_element = soup.find("time")

    if time_element:

        data["tanggal_publikasi"] = (
            time_element.get("datetime")
            or clean_text(
                time_element.get_text(" ", strip=True)
            )
        )

    # Jika tanggal time tidak ditemukan,
    # gunakan metadata artikel

    if not data["tanggal_publikasi"]:

        date_meta_tags = [
            {
                "property": "article:published_time"
            },
            {
                "name": "publish-date"
            },
            {
                "name": "date"
            }
        ]

        for attrs in date_meta_tags:

            meta = soup.find(
                "meta",
                attrs=attrs
            )

            if meta:

                data["tanggal_publikasi"] = (
                    meta.get("content", "")
                )

                if data["tanggal_publikasi"]:
                    break

    return data


# =========================================================
# 3. MEMBACA DATA CSV YANG SUDAH ADA
# =========================================================

def load_existing_data(file_path):
    """
    Membaca data lama agar tidak melakukan scraping ulang.
    """

    if not os.path.exists(file_path):
        return pd.DataFrame()

    try:

        df = pd.read_csv(
            file_path,
            encoding="utf-8-sig"
        )

        if "url" not in df.columns:
            return pd.DataFrame()

        return df

    except Exception as e:

        print(f"[WARNING] Gagal membaca CSV: {e}")

        return pd.DataFrame()


# =========================================================
# 4. SCRAPING INITIAL
# =========================================================

def scrape_initial():
    """
    Mengambil artikel dari halaman 1 sampai MAX_PAGES_INITIAL.
    """

    print("\n========================================")
    print("INITIAL SCRAPING")
    print("========================================\n")

    all_articles = []
    seen_urls = set()

    for page in range(
        1,
        MAX_PAGES_INITIAL + 1
    ):

        if page == 1:
            page_url = START_URL

        else:
            page_url = (
                f"{START_URL}?page={page}"
            )

        print(f"[PAGE] Scraping halaman {page}")

        articles = scrape_article_list(
            page_url
        )

        if not articles:

            print(
                "[INFO] Tidak ada artikel ditemukan. "
                "Pagination dihentikan."
            )

            break

        new_articles = []

        for article in articles:

            if article["url"] in seen_urls:
                continue

            seen_urls.add(
                article["url"]
            )

            new_articles.append(article)

        print(
            f"[INFO] Artikel ditemukan: "
            f"{len(new_articles)}"
        )

        for article in new_articles:

            print(
                f"[DETAIL] {article['judul']}"
            )

            detail = scrape_article_detail(
                article["url"]
            )

            article.update(detail)

            article["tanggal_scraping"] = (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            all_articles.append(article)

            time.sleep(DELAY)

        time.sleep(1)

    save_raw_articles(
        all_articles,
        replace=True
    )

    print("\n========================================")
    print("INITIAL SCRAPING SELESAI")
    print("========================================")

    print(
        f"Total artikel: {len(all_articles)}"
    )


# =========================================================
# 5. SCRAPING INCREMENTAL
# =========================================================

def scrape_incremental():
    """
    Memeriksa artikel terbaru.
    Artikel lama dilewati.
    Artikel baru diambil detailnya dan ditambahkan ke CSV.
    """

    print("\n========================================")
    print("INCREMENTAL SCRAPING")
    print("========================================\n")

    existing_df = load_existing_data(
        RAW_FILE
    )

    if existing_df.empty:

        print(
            "[INFO] Data artikel belum tersedia."
        )

        print(
            "[INFO] Menjalankan initial scraping."
        )

        scrape_initial()

        return

    existing_urls = set(
        existing_df["url"]
        .dropna()
        .astype(str)
    )

    new_articles = []
    seen_urls = set()

    for page in range(
        1,
        MAX_PAGES_INCREMENTAL + 1
    ):

        if page == 1:
            page_url = START_URL

        else:
            page_url = (
                f"{START_URL}?page={page}"
            )

        print(
            f"[PAGE] Memeriksa halaman {page}"
        )

        articles = scrape_article_list(
            page_url
        )

        if not articles:

            print(
                "[INFO] Tidak ada artikel ditemukan."
            )

            break

        new_found_on_page = 0

        for article in articles:

            url = article["url"]

            # URL sudah pernah ditemukan
            if url in existing_urls:
                continue

            # Menghindari duplikat pada proses berjalan
            if url in seen_urls:
                continue

            seen_urls.add(url)

            new_found_on_page += 1

            print(
                f"[NEW] Artikel baru: "
                f"{article['judul']}"
            )

            detail = scrape_article_detail(
                url
            )

            article.update(detail)

            article["tanggal_scraping"] = (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            new_articles.append(article)

            time.sleep(DELAY)

        print(
            f"[INFO] Artikel baru halaman {page}: "
            f"{new_found_on_page}"
        )

        # Jika tidak ada artikel baru pada halaman,
        # kemungkinan artikel terbaru sudah terdeteksi.
        # Pagination incremental dapat dihentikan.

        if new_found_on_page == 0:

            print(
                "[INFO] Tidak ditemukan artikel baru "
                "pada halaman ini."
            )

            break

        time.sleep(1)

    if new_articles:

        save_raw_articles(
            new_articles,
            replace=False
        )

    else:

        print(
            "\n[INFO] Tidak ada artikel baru."
        )

    print("\n========================================")
    print("INCREMENTAL SCRAPING SELESAI")
    print("========================================")

    print(
        f"Artikel baru ditemukan: "
        f"{len(new_articles)}"
    )

    print(
        f"Artikel sebelumnya: "
        f"{len(existing_df)}"
    )

    print(
        f"Total artikel sekarang: "
        f"{len(existing_df) + len(new_articles)}"
    )


# =========================================================
# 6. MENYIMPAN ARTIKEL RAW
# =========================================================

def save_raw_articles(
    articles,
    replace=False
):
    """
    Menyimpan hasil scraping artikel mentah.

    replace=True:
        Mengganti data CSV dengan hasil initial.

    replace=False:
        Menambahkan artikel baru ke CSV lama.
    """

    if not articles:

        print(
            "[INFO] Tidak ada artikel untuk disimpan."
        )

        return

    create_directories()

    new_df = pd.DataFrame(
        articles
    )

    existing_df = load_existing_data(
        RAW_FILE
    )

    if replace or existing_df.empty:

        final_df = new_df

    else:

        final_df = pd.concat(
            [
                existing_df,
                new_df
            ],
            ignore_index=True
        )

    # Deduplikasi berdasarkan URL
    final_df = final_df.drop_duplicates(
        subset=["url"],
        keep="first"
    )

    final_df.to_csv(
        RAW_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("\n[CSV] Data artikel tersimpan")
    print(f"[CSV] File: {RAW_FILE}")
    print(f"[CSV] Total: {len(final_df)} artikel")


# =========================================================
# 7. FILTER KANDIDAT EVENT
# =========================================================

def is_event_candidate(title, summary):
    """
    Menentukan apakah artikel berpotensi membahas event.

    Filter keyword ini bersifat awal.
    Hasilnya belum otomatis berarti event valid.
    """

    text = (
        str(title) + " " +
        str(summary)
    ).lower()

    for keyword in EVENT_KEYWORDS:

        if keyword in text:
            return True

    return False


# =========================================================
# 8. MEMBENTUK DATA EVENT
# =========================================================

def extract_event_candidates():
    """
    Mengambil artikel raw yang berpotensi menjadi event.
    """

    print("\n========================================")
    print("FILTER KANDIDAT EVENT")
    print("========================================\n")

    raw_df = load_existing_data(
        RAW_FILE
    )

    if raw_df.empty:

        print(
            "[INFO] Dataset artikel masih kosong."
        )

        return

    candidates = []

    for _, row in raw_df.iterrows():

        title = str(
            row.get("judul", "")
        )

        summary = str(
            row.get("ringkasan", "")
        )

        if is_event_candidate(
            title,
            summary
        ):

            candidates.append(
                row.to_dict()
            )

    if not candidates:

        print(
            "[INFO] Tidak ditemukan kandidat event."
        )

        return

    candidate_df = pd.DataFrame(
        candidates
    )

    # Menghindari duplikasi URL
    candidate_df = candidate_df.drop_duplicates(
        subset=["url"],
        keep="first"
    )

    # Kolom tambahan untuk proses validasi
    candidate_df["status_validasi"] = (
        "perlu_verifikasi"
    )

    candidate_df["tanggal_event"] = ""

    candidate_df["lokasi_event"] = ""

    candidate_df["status_event"] = (
        "belum_divalidasi"
    )

    # Simpan hasil kandidat event
    candidate_df.to_csv(
        EVENT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"[INFO] Kandidat event: "
        f"{len(candidate_df)}"
    )

    print(
        f"[CSV] Kandidat event tersimpan: "
        f"{EVENT_FILE}"
    )

    print(
        "\n[WARNING] Kandidat event belum tentu "
        "merupakan event valid."
    )

    print(
        "[INFO] Perlu verifikasi tanggal, lokasi, "
        "dan relevansi event."
    )


# =========================================================
# 9. MAIN
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Scraper publikasi dan kandidat event "
            "wisata Kulon Progo"
        )
    )

    parser.add_argument(
        "--mode",
        choices=[
            "initial",
            "incremental",
            "filter"
        ],
        required=True,
        help="Mode scraping yang ingin dijalankan"
    )

    args = parser.parse_args()

    create_directories()

    if args.mode == "initial":

        scrape_initial()

        extract_event_candidates()

    elif args.mode == "incremental":

        scrape_incremental()

        extract_event_candidates()

    elif args.mode == "filter":

        extract_event_candidates()


if __name__ == "__main__":
    main()
