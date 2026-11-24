
import os
import requests
import pandas as pd

from datetime import datetime
from scripts.crawler.config import (
    APIFY_API_TOKEN,
    ACTOR_ID,
    SEARCH_LOCATION
)


# =========================================================
# 1. FUNGSI CRAWLING DESTINASI
# =========================================================

def crawl_destinations(search_queries, max_places=10):
    """
    Mengambil data destinasi wisata menggunakan Apify Google Maps Scraper.

    Parameters:
        search_queries (list): Daftar keyword pencarian destinasi.
        max_places (int): Maksimal tempat yang diambil per pencarian.

    Returns:
        pandas.DataFrame: Data hasil crawling.
    """

    if not APIFY_API_TOKEN:
        raise ValueError(
            "APIFY_API_TOKEN belum ditemukan di file .env"
        )

    url = (
        "https://api.apify.com/v2/acts/"
        f"{ACTOR_ID.replace('/', '~')}/run-sync-get-dataset-items"
    )

    payload = {
        "searchStringsArray": search_queries,
        "locationQuery": SEARCH_LOCATION,
        "maxCrawledPlacesPerSearch": max_places,
        "language": "id"
    }

    params = {
        "token": APIFY_API_TOKEN
    }

    headers = {
        "Content-Type": "application/json"
    }

    print("\n" + "=" * 50)
    print("CRAWLING DESTINASI WISATA")
    print("=" * 50)
    print(f"Lokasi       : {SEARCH_LOCATION}")
    print(f"Keyword      : {search_queries}")
    print(f"Maksimum     : {max_places} tempat per keyword")
    print("=" * 50)

    response = requests.post(
        url=url,
        json=payload,
        headers=headers,
        params=params,
        timeout=300
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        print("\nTidak ada data destinasi yang ditemukan.")
        return pd.DataFrame()

    df = pd.DataFrame(data)

    print("\nCrawling berhasil!")
    print(f"Jumlah data ditemukan: {len(df)}")

    return df


# =========================================================
# 2. FUNGSI MENYIMPAN DATA RAW
# =========================================================

def save_raw_data(df):
    """
    Menyimpan hasil crawling ke CSV di folder data/raw.
    """

    if df.empty:
        print("Data kosong. Tidak ada file yang disimpan.")
        return None

    folder_path = os.path.join(
        "crawler_destinasi",
        "data",
        "raw"
    )

    os.makedirs(folder_path, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    file_path = os.path.join(
        folder_path,
        f"destinasi_raw_{timestamp}.csv"
    )

    df.to_csv(
        file_path,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nData berhasil disimpan!")
    print(f"File: {file_path}")

    return file_path


# =========================================================
# 3. MAIN PROGRAM
# =========================================================

if __name__ == "__main__":

    print("=" * 50)
    print("       WISATAKP - CRAWLER DESTINASI")
    print("=" * 50)

    # Keyword pencarian destinasi wisata
    search_queries = [
        "Wisata alam Kulon Progo",
        "Pantai Kulon Progo",
        "Air terjun Kulon Progo",
        "Goa Kulon Progo",
        "Wisata perbukitan Kulon Progo",
        "Wisata waduk Kulon Progo"
    ]

    # Batas jumlah tempat untuk setiap keyword
    max_places = 20

    print("\nKeyword pencarian:")
    for i, query in enumerate(search_queries, start=1):
        print(f"{i}. {query}")

    print(f"\nLokasi pencarian : {SEARCH_LOCATION}")
    print(f"Maksimum hasil  : {max_places} per keyword")
    print(f"Total keyword   : {len(search_queries)}")
    print(f"Potensi data    : {len(search_queries) * max_places} tempat")

    print("\n" + "=" * 50)
    print("KONFIRMASI CRAWLING")
    print("=" * 50)

    confirmation = input(
        "\nApakah crawling akan dijalankan? (y/n): "
    ).strip().lower()

    if confirmation == "y":

        try:
            # Menjalankan crawling
            df = crawl_destinations(
                search_queries=search_queries,
                max_places=max_places
            )

            # Menyimpan hasil crawling
            if not df.empty:
                save_raw_data(df)

                print("\nPreview data hasil crawling:")
                print(df.head())

                print("\nKolom yang berhasil diperoleh:")
                print(df.columns.tolist())

            else:
                print("\nTidak ada data yang dapat disimpan.")

        except requests.exceptions.Timeout:
            print("\nRequest timeout.")
            print("Proses crawling membutuhkan waktu terlalu lama.")

        except requests.exceptions.HTTPError as error:
            print("\nHTTP Error saat crawling:")
            print(error)

        except requests.exceptions.RequestException as error:
            print("\nTerjadi kesalahan koneksi:")
            print(error)

        except Exception as error:
            print("\nTerjadi kesalahan:")
            print(error)

    else:
        print("\nCrawling dibatalkan.")
        print("Tidak ada request crawling yang dijalankan.")
