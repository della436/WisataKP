import pandas as pd
import re
import unicodedata
from pathlib import Path

# ==========================================
# KONFIGURASI
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"

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


def find_latest_validation_file():
    files = list(DATA_DIR.glob("destinasi_validation_*.csv"))

    if not files:
        raise FileNotFoundError(
            "File destinasi_validation tidak ditemukan."
        )

    # Mengambil file validasi terbaru
    return max(files, key=lambda file: file.stat().st_mtime)


def find_decision_column(df):
    """
    Mencari kolom yang berisi keputusan Pertahankan.
    """

    for column in df.columns:
        values = df[column].astype(str).str.strip().str.lower()

        if values.eq("pertahankan").any():
            return column

    raise ValueError(
        "Kolom keputusan 'Pertahankan' tidak ditemukan."
    )


def categorize_destination(row):
    """
    Mengelompokkan destinasi berdasarkan nama dan kategori.
    """

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
# MAIN PROGRAM
# ==========================================

def main():

    print("=" * 50)
    print("SELEKSI 60 DESTINASI WISATA")
    print("=" * 50)

    # 1. Ambil file validasi terbaru
    input_file = find_latest_validation_file()

    print(f"\nFile input: {input_file.name}")

    df = pd.read_csv(input_file)

    # 2. Cari kolom keputusan
    decision_column = find_decision_column(df)

    print(f"Kolom keputusan: {decision_column}")

    # 3. Ambil destinasi Pertahankan
    df_selected = df[
        df[decision_column]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("pertahankan")
    ].copy()

    print(f"Destinasi Pertahankan: {len(df_selected)}")

    # 4. Hapus duplikat berdasarkan nama destinasi
    df_selected["nama_normalisasi"] = (
        df_selected["title"].apply(normalize_text)
    )

    df_selected = df_selected.drop_duplicates(
        subset="nama_normalisasi",
        keep="first"
    )

    # 5. Kategorisasi destinasi
    df_selected["jenis_wisata"] = df_selected.apply(
        categorize_destination,
        axis=1
    )

    # 6. Seleksi berdasarkan variasi kategori
    if len(df_selected) <= TARGET:
        final_df = df_selected.copy()

    else:
        final_df = (
            df_selected
            .groupby("jenis_wisata", group_keys=False)
            .apply(
                lambda group: group.sample(
                    frac=1,
                    random_state=RANDOM_STATE
                )
            )
            .reset_index(drop=True)
        )

        # Mengacak hasil agar kategori tidak berurutan
        final_df = final_df.sample(
            frac=1,
            random_state=RANDOM_STATE
        ).reset_index(drop=True)

        final_df = final_df.head(TARGET)

    # 7. Simpan hasil
    final_df = final_df.drop(
        columns=["nama_normalisasi"],
        errors="ignore"
    )

    output_file = DATA_DIR / f"destinasi_{TARGET}_final.csv"

    final_df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    # ==========================================
    # OUTPUT
    # ==========================================

    print("\n" + "=" * 50)
    print("HASIL SELEKSI")
    print("=" * 50)

    print(f"Jumlah destinasi terpilih: {len(final_df)}")

    if "jenis_wisata" in final_df.columns:
        print("\nDistribusi jenis wisata:")
        print(final_df["jenis_wisata"].value_counts().to_string())
    else:
        print("\nKolom jenis_wisata tidak ditemukan.")

    print("\nFile berhasil disimpan:")
    print(output_file)

    print("\nSeleksi destinasi selesai!")

if __name__ == "__main__":
    main()