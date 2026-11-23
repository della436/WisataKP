
import pandas as pd
from pathlib import Path
import re
import unicodedata


# =========================================================
# KONFIGURASI PATH
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

DESTINASI_RAW_FILE = RAW_DIR / "destinasi_raw_20261123_015554.csv"
REVIEW_RAW_FILE = RAW_DIR / "wisata_kp_reviews.csv"

DESTINASI_OUTPUT_DIR = PROCESSED_DIR / "destinasi"
REVIEW_OUTPUT_DIR = PROCESSED_DIR / "reviews"

DESTINASI_OUTPUT_FILE = DESTINASI_OUTPUT_DIR / "destinasi_clean.csv"
REVIEW_OUTPUT_FILE = REVIEW_OUTPUT_DIR / "wisata_kp_reviews_clean.csv"


# =========================================================
# KOLOM DATA DESTINASI
# =========================================================

DESTINASI_COLUMNS = [
    "title",
    "categoryName",
    "address",
    "totalScore",
    "reviewsCount"
]


# =========================================================
# KOLOM DATA REVIEW
# =========================================================

REVIEW_COLUMNS = [
    "id_destinasi",
    "nama_destinasi",
    "review",
    "rating"
]


# =========================================================
# FUNGSI CLEANING TEXT DASAR
# =========================================================

def clean_whitespace(value):
    """
    Membersihkan whitespace tanpa mengubah isi teks.
    """

    if pd.isna(value):
        return value

    if not isinstance(value, str):
        return value

    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


# =========================================================
# CLEANING DATA DESTINASI
# =========================================================

def cleaning_destinasi(df):

    print("\n" + "=" * 60)
    print("DATA CLEANING DESTINASI")
    print("=" * 60)

    initial_rows = len(df)

    print(f"Data awal: {initial_rows}")

    # -----------------------------------------------------
    # 1. Validasi kolom
    # -----------------------------------------------------

    missing_columns = [
        column
        for column in DESTINASI_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom destinasi tidak ditemukan: {missing_columns}"
        )

    # -----------------------------------------------------
    # 2. Seleksi kolom
    # -----------------------------------------------------

    df = df[DESTINASI_COLUMNS].copy()

    # -----------------------------------------------------
    # 3. Cleaning whitespace
    # -----------------------------------------------------

    text_columns = [
        "title",
        "categoryName",
        "address"
    ]

    for column in text_columns:
        df[column] = df[column].apply(clean_whitespace)

    # -----------------------------------------------------
    # 4. Menghapus nama destinasi kosong
    # -----------------------------------------------------

    missing_title = (
        df["title"].isna()
        | (df["title"] == "")
    )

    removed_title = missing_title.sum()

    df = df.loc[~missing_title].copy()

    # -----------------------------------------------------
    # 5. Menghapus alamat kosong
    # -----------------------------------------------------

    missing_address = (
        df["address"].isna()
        | (df["address"] == "")
    )

    removed_address = missing_address.sum()

    df = df.loc[~missing_address].copy()

    # -----------------------------------------------------
    # 6. Pemeriksaan duplikasi nama
    # -----------------------------------------------------

    df["title_normalized"] = (
        df["title"]
        .astype(str)
        .str.strip()
        .str.casefold()
    )

    duplicate_names = df[
        df["title_normalized"].duplicated(keep=False)
    ][DESTINASI_COLUMNS].copy()

    duplicate_name_count = (
        df["title_normalized"]
        .duplicated(keep=False)
        .sum()
    )

    # -----------------------------------------------------
    # 7. Menghapus duplikasi baris identik
    # -----------------------------------------------------

    duplicate_rows = df.duplicated(
        subset=DESTINASI_COLUMNS,
        keep="first"
    )

    removed_duplicate_rows = duplicate_rows.sum()

    df = df.loc[~duplicate_rows].copy()

    # Menghapus kolom bantuan
    df = df.drop(columns=["title_normalized"])

    # -----------------------------------------------------
    # 8. Validasi numerik
    # -----------------------------------------------------

    df["totalScore"] = pd.to_numeric(
        df["totalScore"],
        errors="coerce"
    )

    df["reviewsCount"] = pd.to_numeric(
        df["reviewsCount"],
        errors="coerce"
    )

    # -----------------------------------------------------
    # 9. Ringkasan
    # -----------------------------------------------------

    final_rows = len(df)

    print("\nRingkasan cleaning destinasi")
    print("-" * 40)
    print(f"Data awal                  : {initial_rows}")
    print(f"Nama kosong dihapus        : {removed_title}")
    print(f"Alamat kosong dihapus      : {removed_address}")
    print(f"Duplikasi baris dihapus   : {removed_duplicate_rows}")
    print(f"Kandidat nama duplikat     : {duplicate_name_count}")
    print(f"Data akhir                 : {final_rows}")

    print("\nMissing value:")
    print(df.isnull().sum())

    if not duplicate_names.empty:

        print("\nKandidat destinasi dengan nama sama:")
        print(duplicate_names.to_string(index=False))

        print(
            "\nNama yang sama tidak otomatis dihapus "
            "karena mungkin memiliki lokasi berbeda."
        )

    return df


# =========================================================
# CLEANING DATA REVIEW
# =========================================================

def cleaning_review(df):

    print("\n" + "=" * 60)
    print("DATA CLEANING REVIEW")
    print("=" * 60)

    initial_rows = len(df)

    print(f"Data awal: {initial_rows}")

    # -----------------------------------------------------
    # 1. Validasi kolom
    # -----------------------------------------------------

    missing_columns = [
        column
        for column in REVIEW_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom review tidak ditemukan: {missing_columns}"
        )

    # -----------------------------------------------------
    # 2. Seleksi kolom
    # -----------------------------------------------------

    df = df[REVIEW_COLUMNS].copy()

    # -----------------------------------------------------
    # 3. Cleaning whitespace
    # -----------------------------------------------------

    df["id_destinasi"] = df["id_destinasi"].apply(
        clean_whitespace
    )

    df["nama_destinasi"] = df["nama_destinasi"].apply(
        clean_whitespace
    )

    df["review"] = df["review"].apply(
        clean_whitespace
    )

    # -----------------------------------------------------
    # 4. Menghapus review kosong
    # -----------------------------------------------------

    missing_review = (
        df["review"].isna()
        | (df["review"] == "")
    )

    removed_empty_review = missing_review.sum()

    df = df.loc[~missing_review].copy()

    # -----------------------------------------------------
    # 5. Menghapus data tanpa ID destinasi
    # -----------------------------------------------------

    missing_id = (
        df["id_destinasi"].isna()
        | (df["id_destinasi"] == "")
    )

    removed_missing_id = missing_id.sum()

    df = df.loc[~missing_id].copy()

    # -----------------------------------------------------
    # 6. Menghapus data tanpa nama destinasi
    # -----------------------------------------------------

    missing_name = (
        df["nama_destinasi"].isna()
        | (df["nama_destinasi"] == "")
    )

    removed_missing_name = missing_name.sum()

    df = df.loc[~missing_name].copy()

    # -----------------------------------------------------
    # 7. Validasi rating
    # -----------------------------------------------------

    df["rating"] = pd.to_numeric(
        df["rating"],
        errors="coerce"
    )

    invalid_rating = (
        df["rating"].isna()
        | ~df["rating"].between(1, 5)
    )

    removed_invalid_rating = invalid_rating.sum()

    df = df.loc[~invalid_rating].copy()

    # -----------------------------------------------------
    # 8. Menghapus duplikasi data review identik
    # -----------------------------------------------------

    duplicate_reviews = df.duplicated(
        subset=REVIEW_COLUMNS,
        keep="first"
    )

    removed_duplicate_reviews = duplicate_reviews.sum()

    df = df.loc[~duplicate_reviews].copy()

    # -----------------------------------------------------
    # 9. Reset index
    # -----------------------------------------------------

    df = df.reset_index(drop=True)

    # -----------------------------------------------------
    # 10. Ringkasan cleaning
    # -----------------------------------------------------

    final_rows = len(df)

    print("\nRingkasan cleaning review")
    print("-" * 40)
    print(f"Data awal                     : {initial_rows}")
    print(f"Review kosong dihapus          : {removed_empty_review}")
    print(f"ID destinasi kosong dihapus   : {removed_missing_id}")
    print(f"Nama destinasi kosong dihapus : {removed_missing_name}")
    print(f"Rating tidak valid dihapus    : {removed_invalid_rating}")
    print(f"Duplikasi review dihapus      : {removed_duplicate_reviews}")
    print(f"Data akhir                   : {final_rows}")
    print(f"Total data dihapus            : {initial_rows - final_rows}")

    print("\nMissing value setelah cleaning:")
    print(df.isnull().sum())

    print("\nDistribusi rating:")
    print(df["rating"].value_counts().sort_index())

    print("\nJumlah destinasi:")
    print(df["id_destinasi"].nunique())

    return df


# =========================================================
# MAIN PROGRAM
# =========================================================

def main():

    # =====================================================
    # 1. MEMERIKSA FILE RAW
    # =====================================================

    if not DESTINASI_RAW_FILE.exists():
        raise FileNotFoundError(
            f"Dataset destinasi tidak ditemukan:\n"
            f"{DESTINASI_RAW_FILE}"
        )

    if not REVIEW_RAW_FILE.exists():
        raise FileNotFoundError(
            f"Dataset review tidak ditemukan:\n"
            f"{REVIEW_RAW_FILE}"
        )

    # =====================================================
    # 2. MEMBACA DATA RAW
    # =====================================================

    print("Membaca dataset raw...")

    df_destinasi_raw = pd.read_csv(
        DESTINASI_RAW_FILE
    )

    df_review_raw = pd.read_csv(
        REVIEW_RAW_FILE
    )

    # =====================================================
    # 3. CLEANING DESTINASI
    # =====================================================

    df_destinasi_clean = cleaning_destinasi(
        df_destinasi_raw
    )

    # =====================================================
    # 4. CLEANING REVIEW
    # =====================================================

    df_review_clean = cleaning_review(
        df_review_raw
    )

    # =====================================================
    # 5. MEMBUAT FOLDER OUTPUT
    # =====================================================

    DESTINASI_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    REVIEW_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # =====================================================
    # 6. MENYIMPAN HASIL CLEANING
    # =====================================================

    df_destinasi_clean.to_csv(
        DESTINASI_OUTPUT_FILE,
        index=False
    )

    df_review_clean.to_csv(
        REVIEW_OUTPUT_FILE,
        index=False
    )

    # =====================================================
    # 7. PREVIEW DATA
    # =====================================================

    print("\n" + "=" * 60)
    print("PREVIEW DATA DESTINASI CLEAN")
    print("=" * 60)

    print(
        df_destinasi_clean.head(10)
        .to_string(index=False)
    )

    print("\n" + "=" * 60)
    print("PREVIEW DATA REVIEW CLEAN")
    print("=" * 60)

    print(
        df_review_clean.head(10)
        .to_string(index=False)
    )

    # =====================================================
    # 8. SELESAI
    # =====================================================

    print("\n" + "=" * 60)
    print("DATA CLEANING WISATAKP SELESAI")
    print("=" * 60)

    print("\nFile destinasi:")
    print(DESTINASI_OUTPUT_FILE)

    print("\nFile review:")
    print(REVIEW_OUTPUT_FILE)


# =========================================================
# EKSEKUSI
# =========================================================

if __name__ == "__main__":
    main()
