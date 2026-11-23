
import os
import time
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

load_dotenv(PROJECT_DIR / ".env")

DATA_DIR = BASE_DIR / "data"

INPUT_FILE = DATA_DIR / "processed" / "destinasi_60_final.csv"
OUTPUT_DIR = DATA_DIR / "raw"
OUTPUT_FILE = OUTPUT_DIR / "wisata_kp_reviews.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")

ACTOR_ID = "compass~crawler-google-places"

MAX_REVIEWS = 100
SAVE_INTERVAL = 1  # Simpan CSV setiap selesai memproses 1 destinasi

# Kolom dataset final
COLUMNS = [
    "id_destinasi",
    "nama_destinasi",
    "review",
    "rating"
]

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def save_csv_safely(data, output_file):
    """
    Simpan CSV menggunakan file temporary terlebih dahulu,
    lalu replace file utama agar mengurangi risiko file rusak.
    """

    temp_file = output_file.with_suffix(".tmp.csv")

    df_output = pd.DataFrame(data, columns=COLUMNS)

    df_output.to_csv(
        temp_file,
        index=False,
        encoding="utf-8-sig"
    )

    temp_file.replace(output_file)


def normalize_text(text):
    """
    Normalisasi sederhana untuk pencocokan nama destinasi.
    Tidak melakukan cleaning review.
    """

    if pd.isna(text):
        return ""

    return str(text).strip().lower()


def extract_reviews(results, destination_mapping):
    """
    Mengubah hasil Apify menjadi format dataset WisataKP.

    Satu review = satu baris.
    Review kosong dilewati.
    Nama reviewer dan tanggal tidak diambil.
    """

    rows = []
    unmatched_destinations = []

    for destination in results:

        destination_name = destination.get("title")

        if not destination_name:
            continue

        normalized_name = normalize_text(destination_name)

        # Mencocokkan destinasi hasil Apify dengan daftar input
        if normalized_name not in destination_mapping:

            unmatched_destinations.append(destination_name)

            print(
                f"[WARNING] Destinasi tidak dikenali: "
                f"{destination_name}"
            )

            continue

        destination_id = destination_mapping[normalized_name]

        reviews = destination.get("reviews", [])

        if not isinstance(reviews, list):
            continue

        for review_data in reviews:

            review_text = review_data.get("text")

            # Lewati review kosong atau null
            if not review_text:
                continue

            review_text = str(review_text).strip()

            if not review_text:
                continue

            rating = review_data.get("stars")

            rows.append({
                "id_destinasi": destination_id,
                "nama_destinasi": destination_name,
                "review": review_text,
                "rating": rating
            })

    return rows, unmatched_destinations


# ==========================================
# MAIN
# ==========================================

def main():

    if not APIFY_TOKEN:
        raise ValueError(
            "APIFY_API_TOKEN belum diatur pada file .env"
        )

    print("=" * 60)
    print("WISATA KP - GOOGLE MAPS REVIEW SCRAPING")
    print("=" * 60)

    # ==========================================
    # 1. BACA DAFTAR DESTINASI
    # ==========================================

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"File destinasi tidak ditemukan: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    if "title" not in df.columns:
        raise ValueError(
            "Kolom 'title' tidak ditemukan pada file destinasi."
        )

    destinations_df = (
        df["title"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    destinations_df = destinations_df[
        destinations_df != ""
    ].drop_duplicates()

    destinations = destinations_df.tolist()

    # Pastikan jumlah destinasi sesuai target
    if len(destinations) != 60:
        raise ValueError(
            f"Jumlah destinasi seharusnya 60, "
            f"tetapi ditemukan {len(destinations)}."
        )

    # ==========================================
    # 2. BUAT ID DESTINASI
    # ==========================================

    destination_mapping = {}

    for index, destination in enumerate(destinations, start=1):

        destination_id = f"D{index:03d}"

        destination_mapping[
            normalize_text(destination)
        ] = destination_id

    print(f"Jumlah destinasi: {len(destinations)}")
    print(f"Target review per destinasi: {MAX_REVIEWS}")
    print(f"Output CSV: {OUTPUT_FILE}")

    # ==========================================
    # 3. SIAPKAN CSV
    # ==========================================

    # Membuat CSV kosong terlebih dahulu.
    # Jika proses terhenti, file output tetap tersedia.

    if not OUTPUT_FILE.exists():

        save_csv_safely(
            [],
            OUTPUT_FILE
        )

    # ==========================================
    # 4. INPUT ACTOR APIFY
    # ==========================================

    actor_input = {
        "searchStringsArray": destinations,
        "locationQuery": "Kulon Progo, Yogyakarta, Indonesia",
        "maxCrawledPlacesPerSearch": 1,
        "language": "id",
        "maxReviews": MAX_REVIEWS,
        "reviewsSort": "newest",
        "reviewsOrigin": "google",
        "scrapeReviewsPersonalData": False,
        "skipClosedPlaces": False
    }

    # ==========================================
    # 5. JALANKAN ACTOR
    # ==========================================

    print("\nMenjalankan Apify Actor...")

    run_response = requests.post(
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs",
        params={
            "token": APIFY_TOKEN
        },
        json=actor_input,
        timeout=120
    )

    run_response.raise_for_status()

    run_data = run_response.json()["data"]

    run_id = run_data["id"]
    dataset_id = run_data["defaultDatasetId"]

    print(f"Run ID: {run_id}")
    print("Actor berhasil dimulai.")

    # ==========================================
    # 6. MONITOR PROSES SCRAPING
    # ==========================================

    status_url = (
        f"https://api.apify.com/v2/actor-runs/{run_id}"
    )

    while True:

        response = requests.get(
            status_url,
            params={
                "token": APIFY_TOKEN
            },
            timeout=60
        )

        response.raise_for_status()

        status = response.json()["data"]["status"]

        print(f"Status crawling: {status}")

        if status in [
            "SUCCEEDED",
            "FAILED",
            "ABORTED",
            "TIMED-OUT"
        ]:
            break

        time.sleep(30)

    # ==========================================
    # 7. CEK STATUS
    # ==========================================

    if status != "SUCCEEDED":

        raise RuntimeError(
            f"Crawling gagal. Status akhir: {status}\n"
            f"Run ID: {run_id}"
        )

    print("\nCrawling berhasil!")

    # ==========================================
    # 8. DOWNLOAD DATASET APIFY
    # ==========================================

    print("Mengunduh hasil review dari Apify...")

    dataset_url = (
        f"https://api.apify.com/v2/datasets/"
        f"{dataset_id}/items"
    )

    dataset_response = requests.get(
        dataset_url,
        params={
            "token": APIFY_TOKEN,
            "format": "json"
        },
        timeout=180
    )

    dataset_response.raise_for_status()

    results = dataset_response.json()

    print(f"Jumlah hasil tempat: {len(results)}")

    # ==========================================
    # 9. EKSTRAK REVIEW & SIMPAN CSV
    # ==========================================

    all_rows = []

    print("\nMulai mengekstrak review...")

    for index, destination in enumerate(results, start=1):

        destination_name = destination.get("title", "Unknown")

        print(
            f"\n[{index}/{len(results)}] "
            f"Memproses: {destination_name}"
        )

        # Ekstraksi review dari satu destinasi
        extracted_rows, unmatched = extract_reviews(
            [destination],
            destination_mapping
        )

        all_rows.extend(extracted_rows)

        print(
            f"Review berhasil diekstrak: "
            f"{len(extracted_rows)}"
        )

        # Simpan progres setiap destinasi
        save_csv_safely(
            all_rows,
            OUTPUT_FILE
        )

        print(
            f"Total review tersimpan sementara: "
            f"{len(all_rows)}"
        )

    # ==========================================
    # 10. VALIDASI DATASET
    # ==========================================

    df_final = pd.read_csv(OUTPUT_FILE)

    print("\n" + "=" * 60)
    print("HASIL AKHIR SCRAPING WISATA KP")
    print("=" * 60)

    print(f"Jumlah destinasi input : {len(destinations)}")
    print(f"Jumlah hasil Apify     : {len(results)}")
    print(f"Total review          : {len(df_final)}")
    print(f"Jumlah kolom          : {len(df_final.columns)}")
    print(f"Nama kolom           : {list(df_final.columns)}")
    print(f"File output          : {OUTPUT_FILE}")

    print("\nJumlah review per destinasi:")

    print(
        df_final["nama_destinasi"]
        .value_counts()
    )

    print("\nPreview dataset:")

    print(df_final.head(10).to_string(index=False))

    print("\nCrawling dan penyimpanan CSV selesai!")


# ==========================================
# EXECUTION
# ==========================================

if __name__ == "__main__":
    main()
