
import pandas as pd
import re
from pathlib import Path

from Sastrawi.StopWordRemover.StopWordRemoverFactory import (
    StopWordRemoverFactory
)


# =========================================================
# 1. PATH KONFIGURASI
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "reviews"
    / "wisata_kp_reviews_clean.csv"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "reviews"
    / "wisata_kp_reviews_preprocessed.csv"
)


# =========================================================
# 2. INISIALISASI STOPWORD
# =========================================================

stopword_factory = StopWordRemoverFactory()
stopwords = set(stopword_factory.get_stop_words())


# Kata negasi dan kata penting untuk sentimen yang dipertahankan
KEEP_WORDS = {
    "tidak",
    "bukan",
    "belum",
    "jangan",
    "kurang",
    "sangat",
    "terlalu",
    "cukup",
}

stopwords = stopwords - KEEP_WORDS


# =========================================================
# 3. NORMALISASI KATA TIDAK BAKU
# =========================================================

normalisasi_kata = {
    # Negasi
    "gak": "tidak",
    "ga": "tidak",
    "nggak": "tidak",
    "enggak": "tidak",
    "ngga": "tidak",
    "ndak": "tidak",
    "tak": "tidak",

    # Kata umum
    "aja": "saja",
    "aj": "saja",
    "yg": "yang",
    "tp": "tetapi",
    "tpi": "tetapi",
    "kalo": "kalau",
    "kl": "kalau",
    "krn": "karena",
    "utk": "untuk",
    "bbrp": "beberapa",
    "blm": "belum",
    "jg": "juga",
    "jd": "jadi",
    "dr": "dari",
    "dgn": "dengan",
    "sdh": "sudah",
    "udh": "sudah",
    "sm": "sama",
    "sy": "saya",

    # Intensitas
    "banget": "sangat",
    "bgt": "sangat",

    # Kata penilaian
    "keren": "bagus",
    "mantap": "bagus",
    "ok": "baik",
    "oke": "baik",
    "good": "baik",
    "nice": "bagus",

    # Rekomendasi
    "worth": "layak",
    "recommended": "rekomendasi",
    "rekomen": "rekomendasi",
}


# =========================================================
# 4. CASE FOLDING
# =========================================================

def case_folding(text):
    """Mengubah teks menjadi huruf kecil."""

    if pd.isna(text):
        return ""

    return str(text).lower()


# =========================================================
# 5. CLEANING TEXT
# =========================================================

def cleaning_text(text):
    """
    Membersihkan teks dari:
    - URL
    - Mention
    - Angka
    - Simbol dan karakter non-huruf
    - Spasi berlebih
    """

    if pd.isna(text):
        return ""

    text = str(text)

    # Menghapus URL
    text = re.sub(
        r"https?://\S+|www\.\S+",
        " ",
        text
    )

    # Menghapus mention
    text = re.sub(
        r"@\w+",
        " ",
        text
    )

    # Menghapus simbol hashtag, mempertahankan katanya
    text = re.sub(
        r"#",
        "",
        text
    )

    # Menghapus angka
    text = re.sub(
        r"\d+",
        " ",
        text
    )

    # Mempertahankan huruf dan spasi
    text = re.sub(
        r"[^a-zA-Z\s]",
        " ",
        text
    )

    # Menghapus spasi berlebih
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# 6. NORMALISASI
# =========================================================

def normalisasi_text(text):
    """Mengubah kata tidak baku berdasarkan dictionary."""

    if not text:
        return ""

    tokens = text.split()

    normalized_tokens = [
        normalisasi_kata.get(token, token)
        for token in tokens
    ]

    return " ".join(normalized_tokens)


# =========================================================
# 7. TOKENIZATION
# =========================================================

def tokenization(text):
    """Memecah teks menjadi token atau kata."""

    if not text:
        return []

    return text.split()


# =========================================================
# 8. STOPWORD REMOVAL
# =========================================================

def stopword_removal(tokens):
    """Menghapus stopword tanpa menghapus kata penting sentimen."""

    return [
        token
        for token in tokens
        if token not in stopwords
    ]


# =========================================================
# 9. PIPELINE PREPROCESSING
# =========================================================

def preprocessing(text):

    # Case folding
    text = case_folding(text)

    # Cleaning text
    text = cleaning_text(text)

    # Normalisasi
    text = normalisasi_text(text)

    # Tokenization
    tokens = tokenization(text)

    # Stopword removal
    tokens = stopword_removal(tokens)

    # Menggabungkan kembali token
    return " ".join(tokens)


# =========================================================
# 10. MAIN PROGRAM
# =========================================================

def main():

    print("=" * 60)
    print("PREPROCESSING DATA REVIEW WISATA KP")
    print("=" * 60)

    # Memastikan file input tersedia
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"File dataset tidak ditemukan:\n{INPUT_FILE}"
        )

    # Membaca dataset
    df = pd.read_csv(INPUT_FILE)

    print(f"Jumlah data awal: {len(df)}")

    # Validasi kolom
    required_columns = [
        "id_destinasi",
        "nama_destinasi",
        "review",
        "rating"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom yang dibutuhkan tidak ditemukan: {missing_columns}"
        )

    # Preprocessing review
    df["preprocessed_text"] = (
        df["review"]
        .fillna("")
        .apply(preprocessing)
    )

    # Menghitung review kosong setelah preprocessing
    empty_mask = (
        df["preprocessed_text"]
        .str.strip()
        .eq("")
    )

    jumlah_review_kosong = empty_mask.sum()
    jumlah_review_terisi = len(df) - jumlah_review_kosong

    # Membuat folder output
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Menyimpan hasil
    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # =====================================================
    # LAPORAN
    # =====================================================

    print("\n" + "=" * 60)
    print("HASIL PREPROCESSING")
    print("=" * 60)

    print(f"Jumlah data awal       : {len(df)}")
    print(f"Review terisi          : {jumlah_review_terisi}")
    print(f"Review kosong          : {jumlah_review_kosong}")
    print(f"Jumlah kolom          : {len(df.columns)}")
    print(f"Output               : {OUTPUT_FILE}")

    print("\nContoh hasil preprocessing:")

    print(
        df[
            [
                "review",
                "preprocessed_text"
            ]
        ].head(5).to_string(index=False)
    )

    print("\nPREPROCESSING SELESAI")


# =========================================================
# 11. RUN PROGRAM
# =========================================================

if __name__ == "__main__":
    main()
