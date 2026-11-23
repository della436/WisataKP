import pandas as pd
from pathlib import Path

# ==================================================
# KONFIGURASI
# ==================================================

FILE_PATH = Path(
    "crawler_destinasi/data/processed/reviews/"
    "wisata_kp_validation_sample.csv"
)

# ==================================================
# LOAD DATA
# ==================================================

if not FILE_PATH.exists():
    print("File validation sample tidak ditemukan!")
    exit()

df = pd.read_csv(FILE_PATH)

# Pastikan kolom tersedia dan bertipe string
if "manual_label" not in df.columns:
    df["manual_label"] = ""
else:
    df["manual_label"] = df["manual_label"].fillna("").astype(str)

if "validation_status" not in df.columns:
    df["validation_status"] = ""
else:
    df["validation_status"] = (
        df["validation_status"].fillna("").astype(str)
    )

# ==================================================
# LABEL SENTIMEN
# ==================================================

labels = {
    "1": "Positive",
    "2": "Neutral",
    "3": "Negative"
}

# ==================================================
# FUNGSI MENYIMPAN DATA
# ==================================================

def save_data():
    df.to_csv(FILE_PATH, index=False)


# ==================================================
# MANUAL LABELING
# ==================================================

print("=" * 60)
print("         MANUAL SENTIMENT LABELING - WISATAKP")
print("=" * 60)

print("""
Petunjuk labeling:

1 = Positive
2 = Neutral
3 = Negative
4 = Skip review
5 = Keluar

Penentuan sentimen dilakukan berdasarkan isi review,
bukan berdasarkan label otomatis.
""")

# Mengambil data yang belum dilabeli manual
unlabeled_indices = df[
    df["manual_label"].isna() |
    (df["manual_label"].astype(str).str.strip() == "")
].index.tolist()

if len(unlabeled_indices) == 0:
    print("Semua review sudah selesai dilabeli!")
    exit()

total = len(unlabeled_indices)

# ==================================================
# LOOP MANUAL LABELING
# ==================================================

for progress, idx in enumerate(unlabeled_indices, start=1):

    row = df.loc[idx]

    print("\n" + "=" * 60)
    print(f"REVIEW {progress}/{total}")
    print("=" * 60)

    # Menampilkan nama destinasi
    if "nama_destinasi" in df.columns:
        print(f"Destinasi: {row['nama_destinasi']}")

    # Menampilkan isi review
    print("\nISI REVIEW:")
    print("-" * 60)
    print(row["review"])
    print("-" * 60)

    # Pilihan manual
    while True:

        choice = input(
            "\nTentukan sentimen:\n"
            "[1] Positive\n"
            "[2] Neutral\n"
            "[3] Negative\n"
            "[4] Skip\n"
            "[5] Keluar\n"
            "Pilihan: "
        ).strip()

        if choice in labels:
            manual_label = labels[choice]
            break

        elif choice == "4":
            manual_label = None
            break

        elif choice == "5":
            save_data()
            print("\nProgress tersimpan. Program dihentikan.")
            exit()

        else:
            print("Pilihan tidak valid. Masukkan angka 1-5.")

    # Jika review di-skip
    if manual_label is None:
        print("Review dilewati.")
        continue

    # Menyimpan label manual
    df.at[idx, "manual_label"] = manual_label

    # ==================================================
    # PERBANDINGAN LABEL MANUAL DAN OTOMATIS
    # ==================================================

    automatic_label = row["sentiment"]

    if pd.isna(automatic_label):
        status = "No automatic label"

    elif str(automatic_label).strip().lower() == manual_label.lower():
        status = "Correct"

    else:
        status = "Incorrect"

    df.at[idx, "validation_status"] = status

    # Simpan setiap kali selesai satu review
    save_data()

    # Menampilkan hasil perbandingan setelah labeling
    print("\nHASIL:")
    print(f"Label Manual     : {manual_label}")
    print(f"Label Otomatis  : {automatic_label}")
    print(f"Status          : {status}")

# ==================================================
# RINGKASAN
# ==================================================

completed = (
    df["manual_label"].notna() &
    (df["manual_label"].astype(str).str.strip() != "")
)

print("\n" + "=" * 60)
print("MANUAL LABELING SELESAI")
print("=" * 60)

print(f"Total review              : {len(df)}")
print(f"Sudah dilabeli manual    : {completed.sum()}")
print(f"Belum dilabeli           : {len(df) - completed.sum()}")

save_data()

print("\nSeluruh hasil berhasil disimpan.")