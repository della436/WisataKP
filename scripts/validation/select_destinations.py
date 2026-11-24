
import pandas as pd
import re
import ast
import unicodedata
from pathlib import Path

# ==========================================
# KONFIGURASI PATH
# ==========================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data" / "processed"
RAW_DIR = BASE_DIR / "data" / "raw"

TARGET = 60
RANDOM_STATE = 42


# ==========================================
# HELPER
# ==========================================

def normalize_text(text):
    if pd.isna(text):
        return ""

    text = str(text).lower()
    text = unicodedata.normalize("NFKD", text)

    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ==========================================
# MENCARI FILE VALIDASI TERBARU
# ==========================================

def find_latest_validation_file():

    files = list(
        DATA_DIR.glob("destinasi_validation_*.csv")
    )

    if not files:
        raise FileNotFoundError(
            f"File destinasi_validation tidak ditemukan "
            f"di folder:\n{DATA_DIR}"
        )

    return max(
        files,
        key=lambda file: file.stat().st_mtime
    )


# ==========================================
# MENCARI DATASET RAW TERBARU
# ==========================================

def find_latest_raw_file():

    files = list(
        RAW_DIR.glob("destinasi_raw_*.csv")
    )

    if not files:
        raise FileNotFoundError(
            f"Dataset raw destinasi tidak ditemukan "
            f"di folder:\n{RAW_DIR}"
        )

    return max(
        files,
        key=lambda file: file.stat().st_mtime
    )


# ==========================================
# MENCARI KOLOM KEPUTUSAN
# ==========================================

def find_decision_column(df):

    for column in df.columns:

        values = (
            df[column]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        if values.eq("pertahankan").any():
            return column

    raise ValueError(
        "Kolom keputusan 'Pertahankan' tidak ditemukan."
    )


# ==========================================
# KATEGORISASI DESTINASI
# ==========================================

def categorize_destination(row):

    text = normalize_text(
        str(row.get("title", "")) + " " +
        str(row.get("categoryName", ""))
    )

    categories = {

        "Pantai": [
            "pantai", "beach"
        ],

        "Air Terjun": [
            "air terjun", "waterfall", "curug"
        ],

        "Perbukitan / Panorama": [
            "bukit", "hill", "puncak", "panorama",
            "view", "pemandangan", "gunung"
        ],

        "Goa": [
            "goa", "gua", "cave"
        ],

        "Hutan / Alam": [
            "hutan", "forest", "alam", "nature",
            "taman", "park"
        ],

        "Desa Wisata": [
            "desa wisata", "kampung wisata",
            "village tourism"
        ],

        "Waduk": [
            "waduk", "embung", "bendungan"
        ],

        "Kuliner": [
            "kuliner", "cafe", "kafe", "restoran",
            "restaurant", "kedai"
        ],

        "Wisata Lainnya": [
            "wisata", "tourism", "rekreasi"
        ]
    }

    for category, keywords in categories.items():

        if any(keyword in text for keyword in keywords):
            return category

    return "Lainnya"


# ==========================================
# PARSING KOORDINAT DARI LOCATION
# ==========================================

def parse_location(location):

    """
    Mengambil latitude dan longitude dari kolom location.

    Contoh format:
    {'lat': -7.9080407, 'lng': 110.0560952}
    """

    if pd.isna(location):
        return None, None

    try:

        # Mengubah string dictionary menjadi dictionary Python
        location_dict = ast.literal_eval(str(location))

        if isinstance(location_dict, dict):

            latitude = location_dict.get("lat")
            longitude = location_dict.get("lng")

            if latitude is not None and longitude is not None:

                return float(latitude), float(longitude)

    except (ValueError, SyntaxError, TypeError):
        pass

    return None, None


# ==========================================
# EKSTRAKSI KOORDINAT DARI DATA RAW
# ==========================================

def add_coordinates_from_raw(final_df, raw_file):

    print("\n" + "=" * 50)
    print("EKSTRAKSI KOORDINAT")
    print("=" * 50)

    print(f"File raw: {raw_file.name}")

    raw_df = pd.read_csv(raw_file)

    print(f"Jumlah data raw: {len(raw_df)}")

    # ------------------------------------------
    # 1. PASTIKAN KOLOM RAW TERSEDIA
    # ------------------------------------------

    required_columns = ["title", "location"]

    for column in required_columns:

        if column not in raw_df.columns:

            raise ValueError(
                f"Kolom '{column}' tidak ditemukan "
                f"pada dataset raw."
            )

    # ------------------------------------------
    # 2. PARSING KOORDINAT LOCATION
    # ------------------------------------------

    coordinates = raw_df["location"].apply(
        parse_location
    )

    raw_df["latitude"] = coordinates.apply(
        lambda value: value[0]
    )

    raw_df["longitude"] = coordinates.apply(
        lambda value: value[1]
    )

    # ------------------------------------------
    # 3. NORMALISASI NAMA DESTINASI RAW
    # ------------------------------------------

    raw_df["nama_normalisasi"] = (
        raw_df["title"]
        .apply(normalize_text)
    )

    # ------------------------------------------
    # 4. HANYA AMBIL DATA KOORDINAT VALID
    # ------------------------------------------

    raw_coordinates = raw_df[
        [
            "nama_normalisasi",
            "latitude",
            "longitude"
        ]
    ].copy()

    raw_coordinates = raw_coordinates.dropna(
        subset=[
            "nama_normalisasi",
            "latitude",
            "longitude"
        ]
    )

    raw_coordinates = raw_coordinates[
        raw_coordinates["nama_normalisasi"] != ""
    ]

    # ------------------------------------------
    # 5. HAPUS DUPLIKAT NAMA RAW
    # ------------------------------------------

    raw_coordinates = raw_coordinates.drop_duplicates(
        subset="nama_normalisasi",
        keep="first"
    )

    print(
        f"Data raw dengan koordinat valid: "
        f"{len(raw_coordinates)}"
    )

    # ------------------------------------------
    # 6. NORMALISASI NAMA DESTINASI FINAL
    # ------------------------------------------

    final_df = final_df.copy()

    final_df["nama_normalisasi"] = (
        final_df["title"]
        .apply(normalize_text)
    )

    # ------------------------------------------
    # 7. MATCHING DESTINASI
    # ------------------------------------------

    final_df = final_df.merge(
        raw_coordinates,
        on="nama_normalisasi",
        how="left"
    )

    # ------------------------------------------
    # 8. CEK HASIL MATCHING
    # ------------------------------------------

    matched = final_df[
        final_df["latitude"].notna()
        & final_df["longitude"].notna()
    ]

    unmatched = final_df[
        final_df["latitude"].isna()
        | final_df["longitude"].isna()
    ]

    print("\nHasil pencocokan koordinat:")
    print(f"Berhasil ditemukan: {len(matched)}")
    print(f"Tidak ditemukan: {len(unmatched)}")

    # ------------------------------------------
    # 9. TAMPILKAN DESTINASI TANPA KOORDINAT
    # ------------------------------------------

    if len(unmatched) > 0:

        print(
            "\nDestinasi yang belum memiliki koordinat:"
        )

        for title in unmatched["title"].tolist():
            print(f"- {title}")

    # ------------------------------------------
    # 10. HAPUS KOLOM BANTU
    # ------------------------------------------

    final_df = final_df.drop(
        columns=["nama_normalisasi"],
        errors="ignore"
    )

    return final_df


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():

    print("=" * 50)
    print("SELEKSI 60 DESTINASI WISATA")
    print("=" * 50)

    print(f"\nRoot project: {BASE_DIR}")
    print(f"Data processed: {DATA_DIR}")
    print(f"Data raw: {RAW_DIR}")

    # ------------------------------------------
    # 1. AMBIL FILE VALIDASI TERBARU
    # ------------------------------------------

    input_file = find_latest_validation_file()

    print(
        f"\nFile input validasi: "
        f"{input_file.name}"
    )

    df = pd.read_csv(input_file)

    # ------------------------------------------
    # 2. CARI KOLOM KEPUTUSAN
    # ------------------------------------------

    decision_column = find_decision_column(df)

    print(f"Kolom keputusan: {decision_column}")

    # ------------------------------------------
    # 3. AMBIL DESTINASI PERTAHANKAN
    # ------------------------------------------

    df_selected = df[
        df[decision_column]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("pertahankan")
    ].copy()

    print(
        f"Destinasi Pertahankan: "
        f"{len(df_selected)}"
    )

    # ------------------------------------------
    # 4. HAPUS DUPLIKAT NAMA DESTINASI
    # ------------------------------------------

    df_selected["nama_normalisasi"] = (
        df_selected["title"]
        .apply(normalize_text)
    )

    df_selected = df_selected.drop_duplicates(
        subset="nama_normalisasi",
        keep="first"
    )

    # ------------------------------------------
    # 5. KATEGORISASI DESTINASI
    # ------------------------------------------

    df_selected["jenis_wisata"] = (
        df_selected.apply(
            categorize_destination,
            axis=1
        )
    )

    # ------------------------------------------
    # 6. SELEKSI 60 DESTINASI
    # ------------------------------------------

    if len(df_selected) <= TARGET:

        final_df = df_selected.copy()

    else:

        final_df = (
            df_selected
            .groupby(
                "jenis_wisata",
                group_keys=False
            )
            .apply(
                lambda group: group.sample(
                    frac=1,
                    random_state=RANDOM_STATE
                )
            )
            .reset_index(drop=True)
        )

        # Mengacak hasil
        final_df = final_df.sample(
            frac=1,
            random_state=RANDOM_STATE
        ).reset_index(drop=True)

        # Mengambil maksimal 60 destinasi
        final_df = final_df.head(TARGET)

    # ------------------------------------------
    # 7. HAPUS KOLOM NORMALISASI
    # ------------------------------------------

    final_df = final_df.drop(
        columns=["nama_normalisasi"],
        errors="ignore"
    )

    # ------------------------------------------
    # 8. CARI DATASET RAW
    # ------------------------------------------

    raw_file = find_latest_raw_file()

    print(
        f"\nDataset raw terpilih: "
        f"{raw_file.name}"
    )

    # ------------------------------------------
    # 9. TAMBAHKAN KOORDINAT
    # ------------------------------------------

    final_df = add_coordinates_from_raw(
        final_df,
        raw_file
    )

    # ------------------------------------------
    # 10. SIMPAN DATA FINAL
    # ------------------------------------------

    output_file = (
        DATA_DIR / f"destinasi_{TARGET}_final.csv"
    )

    final_df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    # ==========================================
    # OUTPUT HASIL
    # ==========================================

    print("\n" + "=" * 50)
    print("HASIL SELEKSI")
    print("=" * 50)

    print(
        f"Jumlah destinasi terpilih: "
        f"{len(final_df)}"
    )

    # ------------------------------------------
    # DISTRIBUSI KATEGORI
    # ------------------------------------------

    if "jenis_wisata" in final_df.columns:

        print("\nDistribusi jenis wisata:")

        print(
            final_df["jenis_wisata"]
            .value_counts()
            .to_string()
        )

    # ------------------------------------------
    # STATUS KOORDINAT
    # ------------------------------------------

    if (
        "latitude" in final_df.columns
        and "longitude" in final_df.columns
    ):

        koordinat_lengkap = (
            final_df["latitude"].notna()
            & final_df["longitude"].notna()
        ).sum()

        print("\nStatus koordinat:")
        print(
            f"Koordinat lengkap: "
            f"{koordinat_lengkap}/{len(final_df)}"
        )

    # ------------------------------------------
    # OUTPUT FILE
    # ------------------------------------------

    print("\nFile berhasil disimpan:")
    print(output_file)

    print("\nSeleksi destinasi selesai!")


# ==========================================
# EXECUTION
# ==========================================

if __name__ == "__main__":
    main()
