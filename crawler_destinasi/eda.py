
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ==========================================================
# 1. PERSIAPAN DAN MEMBACA DATASET
# ==========================================================

# Lokasi dataset hasil cleaning
file_path = "crawler_destinasi/data/processed/reviews/wisata_kp_reviews_clean.csv"

# Folder untuk menyimpan hasil EDA
output_dir = Path("crawler_destinasi/data/processed/eda")
output_dir.mkdir(parents=True, exist_ok=True)

# Membaca dataset
df = pd.read_csv(file_path)

# Memastikan kolom yang dibutuhkan tersedia
required_columns = [
    "id_destinasi",
    "nama_destinasi",
    "review",
    "rating"
]

missing_columns = [
    column for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(f"Kolom tidak ditemukan: {missing_columns}")

# ==========================================================
# 2. OVERVIEW DATASET
# ==========================================================

print("=" * 60)
print("OVERVIEW DATASET WISATAKP")
print("=" * 60)

print(f"Jumlah review       : {len(df):,}")
print(f"Jumlah kolom       : {len(df.columns)}")
print(f"Jumlah destinasi   : {df['id_destinasi'].nunique()}")

print("\nNama kolom:")
print(df.columns.tolist())

print("\nInformasi dataset:")
df.info()

print("\n5 data pertama:")
print(df.head())

print("\nStatistik rating:")
print(df["rating"].describe())

# ==========================================================
# 3. ANALISIS DISTRIBUSI RATING
# ==========================================================

print("\n" + "=" * 60)
print("ANALISIS DISTRIBUSI RATING")
print("=" * 60)

# Menghitung jumlah review pada setiap rating
rating_counts = df["rating"].value_counts().sort_index()

print("\nJumlah review pada setiap rating:")
print(rating_counts)

# Menghitung persentase rating
rating_percentage = (
    rating_counts / rating_counts.sum() * 100
).round(2)

print("\nPersentase distribusi rating:")
print(rating_percentage)

# Membuat grafik distribusi rating
plt.figure(figsize=(8, 5))

bars = plt.bar(
    rating_counts.index,
    rating_counts.values
)

plt.title("Distribusi Rating Review Wisata Kulon Progo")
plt.xlabel("Rating")
plt.ylabel("Jumlah Review")
plt.xticks([1, 2, 3, 4, 5])

# Menampilkan jumlah di atas setiap batang
for bar in bars:
    height = bar.get_height()
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        height,
        f"{int(height):,}",
        ha="center",
        va="bottom"
    )

plt.tight_layout()

# Menyimpan grafik
plt.savefig(
    output_dir / "distribusi_rating.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()
plt.close()

# ==========================================================
# 4. ANALISIS JUMLAH REVIEW PER DESTINASI
# ==========================================================

print("\n" + "=" * 60)
print("ANALISIS REVIEW PER DESTINASI")
print("=" * 60)

# Menghitung jumlah review pada setiap destinasi
review_per_destinasi = (
    df.groupby("nama_destinasi")["review"]
    .count()
    .sort_values(ascending=True)
)

print("\nJumlah review pada setiap destinasi:")
print(review_per_destinasi)

# Membuat grafik seluruh destinasi
plt.figure(figsize=(12, max(8, len(review_per_destinasi) * 0.3)))

bars = plt.barh(
    review_per_destinasi.index,
    review_per_destinasi.values
)

plt.title("Distribusi Jumlah Review pada Seluruh Destinasi Wisata")
plt.xlabel("Jumlah Review")
plt.ylabel("Nama Destinasi")

# Menampilkan angka jumlah review
for bar in bars:
    width = bar.get_width()
    plt.text(
        width,
        bar.get_y() + bar.get_height() / 2,
        f" {int(width)}",
        va="center",
        fontsize=8
    )

plt.tight_layout()

# Menyimpan grafik
plt.savefig(
    output_dir / "review_seluruh_destinasi.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()
plt.close()

# ==========================================================
# 5. ANALISIS PANJANG REVIEW
# ==========================================================

print("\n" + "=" * 60)
print("ANALISIS PANJANG REVIEW")
print("=" * 60)

# Menghitung jumlah kata dalam setiap review
df["jumlah_kata"] = df["review"].astype(str).apply(
    lambda text: len(text.split())
)

# Menampilkan statistik panjang review
length_statistics = df["jumlah_kata"].describe()

print("\nStatistik panjang review:")
print(length_statistics)

# Membuat histogram panjang review
plt.figure(figsize=(8, 5))

plt.hist(
    df["jumlah_kata"],
    bins=30
)

plt.title("Distribusi Panjang Review Wisata")
plt.xlabel("Jumlah Kata dalam Review")
plt.ylabel("Jumlah Review")

plt.tight_layout()

# Menyimpan grafik
plt.savefig(
    output_dir / "distribusi_panjang_review.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()
plt.close()

# ==========================================================
# 6. MENYIMPAN RINGKASAN HASIL EDA
# ==========================================================

# Ringkasan distribusi rating
rating_summary = pd.DataFrame({
    "rating": rating_counts.index,
    "jumlah_review": rating_counts.values,
    "persentase": rating_percentage.values
})

rating_summary.to_csv(
    output_dir / "ringkasan_rating.csv",
    index=False
)

# Ringkasan review per destinasi
review_summary = review_per_destinasi.reset_index()

review_summary.columns = [
    "nama_destinasi",
    "jumlah_review"
]

review_summary.to_csv(
    output_dir / "ringkasan_review_destinasi.csv",
    index=False
)

# Ringkasan statistik panjang review
length_statistics.to_csv(
    output_dir / "statistik_panjang_review.csv"
)

# ==========================================================
# 7. SELESAI
# ==========================================================

print("\n" + "=" * 60)
print("EDA WISATAKP SELESAI")
print("=" * 60)

print(f"Seluruh hasil EDA disimpan di: {output_dir}")
