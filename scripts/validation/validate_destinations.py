
import pandas as pd
import re
import unicodedata
from pathlib import Path
from datetime import datetime

# =========================================================
# 1. PATH CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# Cari file cleaned terbaru
cleaned_files = list(
    PROCESSED_DIR.glob("destinasi_cleaned_*.csv")
)

if not cleaned_files:
    raise FileNotFoundError(
        "File destinasi_cleaned tidak ditemukan."
    )

INPUT_FILE = max(
    cleaned_files,
    key=lambda file: file.stat().st_mtime
)

# Output validasi
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

VALIDATION_OUTPUT = (
    PROCESSED_DIR
    / f"destinasi_validation_{TIMESTAMP}.csv"
)

DUPLICATE_OUTPUT = (
    PROCESSED_DIR
    / "duplicate_candidates.csv"
)


# =========================================================
# 2. NORMALIZATION FUNCTION
# =========================================================

def normalize_text(text):

    if pd.isna(text):
        return ""

    text = str(text).lower().strip()

    text = unicodedata.normalize("NFKD", text)

    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    text = re.sub(r"[^a-z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text


# =========================================================
# 3. REGION VALIDATION
# =========================================================

def validate_region(address):

    address = normalize_text(address)

    # Indikasi kuat berada di Kulon Progo
    kulon_progo_keywords = [
        "kulon progo",
        "kulonprogo",
        "wates",
        "temon",
        "kokap",
        "panjatan",
        "galur",
        "lendah",
        "sentolo",
        "pengasih",
        "nanggulan",
        "kalibawang",
        "samigaluh",
        "girimulyo",
    ]

    # Indikasi berada di luar Kulon Progo
    outside_keywords = [
        "sleman",
        "bantul",
        "gunungkidul",
        "gunung kidul",
        "kota yogyakarta",
        "yogyakarta city",
        "magelang",
        "purworejo",
    ]

    # Periksa Kulon Progo terlebih dahulu
    if any(
        keyword in address
        for keyword in kulon_progo_keywords
    ):
        return "Dalam Kulon Progo"

    # Periksa wilayah luar
    if any(
        keyword in address
        for keyword in outside_keywords
    ):
        return "Di luar Kulon Progo"

    # Jika alamat terlalu umum
    return "Perlu Pemeriksaan"


# =========================================================
# 4. TOURISM RELEVANCE VALIDATION
# =========================================================

def validate_relevance(title, category):

    title = normalize_text(title)
    category = normalize_text(category)

    combined = f"{title} {category}"

    # Kategori yang jelas bukan objek wisata
    irrelevant_keywords = [
        "sumur air umum",
        "sumur umum",
        "sekolah",
        "universitas",
        "rumah sakit",
        "kantor pemerintahan",
        "kantor",
        "atm",
        "bank",
        "bengkel",
        "pom bensin",
        "spbu",
        "toko",
        "minimarket",
        "supermarket",
        "perumahan",
        "tempat ibadah",
    ]

    if any(
        keyword in combined
        for keyword in irrelevant_keywords
    ):
        return "Tidak Relevan"

    # Kategori atau nama yang menunjukkan objek wisata
    relevant_keywords = [
        "wisata",
        "pantai",
        "air terjun",
        "waterfall",
        "curug",
        "goa",
        "gua",
        "cave",
        "bukit",
        "puncak",
        "hutan",
        "forest",
        "taman",
        "park",
        "waduk",
        "bendungan",
        "danau",
        "lake",
        "museum",
        "desa wisata",
        "kampung wisata",
        "agrowisata",
        "ekowisata",
        "outbound",
        "rafting",
        "arung jeram",
        "camping",
        "perkemahan",
        "glamping",
        "kebun",
        "gardens",
        "panorama",
        "landscape",
        "spot foto",
        "view",
        "pemandangan",
        "kuliner",
        "cafe",
        "coffee",
        "restoran",
        "restaurant",
        "kerajinan",
        "budaya",
        "atraksi",
        "rekreasi",
        "resort",
    ]

    if any(
        keyword in combined
        for keyword in relevant_keywords
    ):
        return "Relevan"

    # Tidak cukup informasi untuk menentukan relevansi
    return "Perlu Pemeriksaan"


# =========================================================
# 5. INITIAL DECISION
# =========================================================

def determine_decision(
    title,
    category,
    region_status,
    relevance_status,
    is_duplicate
):

    normalized_title = normalize_text(title)

    # Eliminasi khusus sesuai keputusan pengguna
    if normalized_title == "padusan":
        return "Eliminasi", "Kategori Sumur Air Umum"

    # Wilayah di luar Kulon Progo
    if region_status == "Di luar Kulon Progo":
        return "Eliminasi", "Lokasi di luar Kulon Progo"

    # Objek bukan wisata
    if relevance_status == "Tidak Relevan":
        return "Eliminasi", "Tidak sesuai cakupan objek wisata"

    # Data yang masih meragukan
    if region_status == "Perlu Pemeriksaan":
        return "Review Manual", "Lokasi belum dapat dipastikan"

    if relevance_status == "Perlu Pemeriksaan":
        return "Review Manual", "Relevansi wisata belum dapat dipastikan"

    # Kandidat duplikat belum ditentukan final
    if is_duplicate:
        return "Review Manual", "Nama destinasi terindikasi duplikat"

    # Jika semua pemeriksaan awal terpenuhi
    return "Pertahankan", "Lokasi dan relevansi sesuai kriteria awal"


# =========================================================
# 6. LOAD DATA
# =========================================================

df = pd.read_csv(INPUT_FILE)

print("=" * 65)
print("VALIDASI WILAYAH DAN RELEVANSI DESTINASI")
print("=" * 65)

print(f"File input  : {INPUT_FILE.name}")
print(f"Jumlah data : {len(df)}")
print(f"Kolom      : {len(df.columns)}")


# =========================================================
# 7. DUPLICATE DETECTION
# =========================================================

df["normalized_title"] = df["title"].apply(
    normalize_text
)

duplicate_mask = (
    df["normalized_title"].duplicated(keep=False)
    & (df["normalized_title"] != "")
)

df["is_duplicate"] = duplicate_mask

duplicate_df = df[duplicate_mask].copy()

if not duplicate_df.empty:

    duplicate_df = duplicate_df.sort_values(
        by=["normalized_title", "address"],
        na_position="last"
    )

    duplicate_df.drop(
        columns=["normalized_title", "is_duplicate"],
        inplace=True
    )

    duplicate_df.to_csv(
        DUPLICATE_OUTPUT,
        index=False,
        encoding="utf-8-sig"
    )


# =========================================================
# 8. REGION VALIDATION
# =========================================================

df["wilayah_status"] = df["address"].apply(
    validate_region
)


# =========================================================
# 9. RELEVANCE VALIDATION
# =========================================================

df["relevansi_status"] = df.apply(
    lambda row: validate_relevance(
        row["title"],
        row["categoryName"]
    ),
    axis=1
)


# =========================================================
# 10. INITIAL DECISION & REASON
# =========================================================

decisions = df.apply(
    lambda row: determine_decision(
        title=row["title"],
        category=row["categoryName"],
        region_status=row["wilayah_status"],
        relevance_status=row["relevansi_status"],
        is_duplicate=row["is_duplicate"]
    ),
    axis=1
)

df["keputusan"] = decisions.apply(lambda x: x[0])
df["alasan"] = decisions.apply(lambda x: x[1])


# =========================================================
# 11. CLEAN OUTPUT COLUMNS
# =========================================================

df.drop(
    columns=["normalized_title", "is_duplicate"],
    inplace=True
)


# =========================================================
# 12. SAVE VALIDATION DATASET
# =========================================================

df.to_csv(
    VALIDATION_OUTPUT,
    index=False,
    encoding="utf-8-sig"
)


# =========================================================
# 13. DISPLAY VALIDATION SUMMARY
# =========================================================

print("\n" + "=" * 65)
print("RINGKASAN VALIDASI WILAYAH")
print("=" * 65)

print(
    df["wilayah_status"]
    .value_counts()
    .to_string()
)

print("\n" + "=" * 65)
print("RINGKASAN VALIDASI RELEVANSI")
print("=" * 65)

print(
    df["relevansi_status"]
    .value_counts()
    .to_string()
)

print("\n" + "=" * 65)
print("RINGKASAN KEPUTUSAN")
print("=" * 65)

print(
    df["keputusan"]
    .value_counts()
    .to_string()
)


# =========================================================
# 14. DISPLAY MANUAL REVIEW
# =========================================================

review_df = df[
    df["keputusan"] == "Review Manual"
]

if not review_df.empty:

    print("\n" + "=" * 65)
    print("DESTINASI YANG MEMERLUKAN REVIEW MANUAL")
    print("=" * 65)

    for _, row in review_df.iterrows():

        print(f"\nNama     : {row['title']}")
        print(f"Kategori : {row['categoryName']}")
        print(f"Alamat  : {row['address']}")
        print(f"Wilayah : {row['wilayah_status']}")
        print(f"Relevansi: {row['relevansi_status']}")
        print(f"Alasan  : {row['alasan']}")


# =========================================================
# 15. DISPLAY ELIMINATION CANDIDATES
# =========================================================

elimination_df = df[
    df["keputusan"] == "Eliminasi"
]

if not elimination_df.empty:

    print("\n" + "=" * 65)
    print("KANDIDAT ELIMINASI")
    print("=" * 65)

    for _, row in elimination_df.iterrows():

        print(
            f"- {row['title']} | "
            f"{row['alasan']} | "
            f"{row['address']}"
        )


# =========================================================
# 16. FINAL INFORMATION
# =========================================================

print("\n" + "=" * 65)
print("VALIDASI SELESAI")
print("=" * 65)

print(f"Total data awal          : {len(df)}")
print(
    f"Pertahankan             : "
    f"{(df['keputusan'] == 'Pertahankan').sum()}"
)
print(
    f"Eliminasi               : "
    f"{(df['keputusan'] == 'Eliminasi').sum()}"
)
print(
    f"Review Manual            : "
    f"{(df['keputusan'] == 'Review Manual').sum()}"
)

print(f"\nFile validasi tersimpan : {VALIDATION_OUTPUT}")
print(f"File duplikat tersimpan : {DUPLICATE_OUTPUT}")

print("\nDataset cleaned asli tidak diubah.")
