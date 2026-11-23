
import pandas as pd
from pathlib import Path

# =========================================================
# 1. PATH DATASET
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE_DIR / "data" / "processed" / "reviews"
    / "wisata_kp_reviews_labeled.csv"
)

OUTPUT_FILE = (
    BASE_DIR / "data" / "processed" / "reviews"
    / "wisata_kp_validation_sample.csv"
)

# Jumlah sampel dari setiap kelas
SAMPLE_PER_CLASS = 30

# =========================================================
# 2. MEMBACA DATA
# =========================================================

def main():

    print("Membaca dataset labeled...")

    df = pd.read_csv(INPUT_FILE)

    print(f"Total data: {len(df)}")

    # =====================================================
    # 3. SAMPLING PER KELAS
    # =====================================================

    samples = []

    for label in [-1, 0, 1]:

        class_data = df[df["label"] == label]

        sample_size = min(SAMPLE_PER_CLASS, len(class_data))

        sampled_data = class_data.sample(
            n=sample_size,
            random_state=42
        )

        samples.append(sampled_data)

    validation_df = pd.concat(samples, ignore_index=True)

    # Acak urutan sampel agar tidak dikelompokkan berdasarkan sentimen
    validation_df = validation_df.sample(
        frac=1,
        random_state=42
    ).reset_index(drop=True)

    # =====================================================
    # 4. KOLOM UNTUK VALIDASI MANUAL
    # =====================================================

    validation_df["manual_label"] = ""

    validation_df["validation_status"] = ""

    # =====================================================
    # 5. SIMPAN DATA
    # =====================================================

    validation_df.to_csv(OUTPUT_FILE, index=False)

    # =====================================================
    # 6. RINGKASAN
    # =====================================================

    print("\n===== VALIDATION SAMPLE =====")
    print(f"Total sampel: {len(validation_df)}")

    print("\nDistribusi sampel:")
    print(validation_df["sentiment"].value_counts())

    print("\nFile validation berhasil dibuat:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
