import pandas as pd
from pathlib import Path

# ==========================================
# KONFIGURASI
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"

FILE_NAME = "destinasi_raw_20261123_015554.csv"
FILE_PATH = RAW_DIR / FILE_NAME


# ==========================================
# MEMBACA DATASET
# ==========================================

df = pd.read_csv(FILE_PATH)

print("=" * 60)
print("RAW DATA INSPECTION - WISATAKP")
print("=" * 60)


# ==========================================
# 1. UKURAN DATASET
# ==========================================

print("\n[1] UKURAN DATASET")
print("-" * 60)

print(f"Jumlah baris : {df.shape[0]}")
print(f"Jumlah kolom : {df.shape[1]}")


# ==========================================
# 2. DAFTAR NAMA KOLOM
# ==========================================

print("\n[2] DAFTAR KOLOM")
print("-" * 60)

for i, column in enumerate(df.columns, start=1):
    print(f"{i}. {column}")


# ==========================================
# 3. TIPE DATA
# ==========================================

print("\n[3] TIPE DATA SETIAP KOLOM")
print("-" * 60)

print(df.dtypes)


# ==========================================
# 4. PREVIEW DATA
# ==========================================

print("\n[4] PREVIEW DATA (5 DATA PERTAMA)")
print("-" * 60)

print(df.head())


# ==========================================
# 5. INFORMASI DATASET
# ==========================================

print("\n[5] INFORMASI DATASET")
print("-" * 60)

df.info()


# ==========================================
# 6. MISSING VALUE
# ==========================================

print("\n[6] ANALISIS MISSING VALUE")
print("-" * 60)

missing = pd.DataFrame({
    "Jumlah Missing Value": df.isnull().sum(),
    "Persentase Missing (%)": (
        df.isnull().sum() / len(df) * 100
    ).round(2)
})

missing = missing[missing["Jumlah Missing Value"] > 0]
missing = missing.sort_values(
    by="Jumlah Missing Value",
    ascending=False
)

if missing.empty:
    print("Tidak ditemukan missing value.")
else:
    print(missing)


# ==========================================
# 7. PEMERIKSAAN DUPLIKASI placeId
# ==========================================

print("\n[7] PEMERIKSAAN DUPLIKASI placeId")
print("-" * 60)

if "placeId" in df.columns:

    jumlah_duplikat = df["placeId"].duplicated().sum()

    print(f"Jumlah placeId duplikat : {jumlah_duplikat}")

    if jumlah_duplikat > 0:
        print("\nData dengan placeId duplikat:")
        print(
            df[df["placeId"].duplicated(keep=False)]
            [["title", "placeId"]]
            .sort_values("placeId")
        )

else:
    print("Kolom placeId tidak ditemukan.")


# ==========================================
# 8. RINGKASAN INSPEKSI
# ==========================================

print("\n[8] RINGKASAN INSPEKSI")
print("-" * 60)

print(f"Total data              : {len(df)}")
print(f"Total atribut           : {len(df.columns)}")
print(f"Total missing value     : {df.isnull().sum().sum()}")
print(f"Total data duplikat     : {df.duplicated().sum()}")

print("\nInspeksi raw data selesai.")