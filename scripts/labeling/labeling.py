
import pandas as pd
import re
from pathlib import Path

# =========================================================
# 1. PATH DATASET
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE_DIR / "data" / "processed" / "reviews"
    / "wisata_kp_reviews_preprocessed.csv"
)

OUTPUT_FILE = (
    BASE_DIR / "data" / "processed" / "reviews"
    / "wisata_kp_reviews_labeled.csv"
)


# =========================================================
# 2. KAMUS SENTIMEN POSITIF
# =========================================================

positive_words = {
    # Keindahan dan daya tarik
    "bagus", "indah", "menarik", "cantik", "keren", "unik",
    "menawan", "memukau", "mempesona", "elok", "eksotis",
    "fantastis", "istimewa", "luarbiasa", "terbaik", "top",

    # Kenyamanan dan suasana
    "nyaman", "sejuk", "adem", "asri", "tenang", "damai",
    "menenangkan", "menyejukkan", "bersih", "rapi", "terawat",
    "luas", "teduh", "sunyi", "hening", "betah",

    # Pengalaman
    "menyenangkan", "seru", "asyik", "asik", "bahagia",
    "senang", "puas", "memuaskan", "berkesan", "istimewa",
    "favorit", "favorite", "fav", "suka", "love", "enjoy",
    "enjoyed", "amazing", "wonderful", "awesome", "excellent",
    "perfect", "beautiful", "breathtaking", "peaceful",
    "pleasant", "refreshing", "fun", "great", "good", "nice",

    # Fasilitas dan pelayanan
    "ramah", "membantu", "lengkap", "aman", "mudah",
    "strategis", "prima", "friendly", "helpful", "hospitality",

    # Ekonomi dan rekomendasi
    "murah", "terjangkau", "worth", "worthit", "affordable",
    "rekomendasi", "recommended", "rekomen", "layak",
    "cocok", "mantap", "mantab", "jos", "joss", "juoss",
    "menambah", "bermanfaat", "berharga", "hebat", "unggul",
    "delicious", "enak", "nikmat", "lezat", "seger", "segar",
    "favorable"
}


# =========================================================
# 3. KAMUS SENTIMEN NEGATIF
# =========================================================

negative_words = {
    # Kondisi dan kualitas
    "buruk", "jelek", "kotor", "rusak", "kumuh", "jorok",
    "tidaklayak", "parah", "payah", "zonk", "gagal",
    "mengecewakan", "kecewa", "menyesal", "buruk",
    "ugly", "bad", "worst", "terrible", "poor",
    "disappointing", "disappointed",

    # Kenyamanan dan keamanan
    "tidaknyaman", "berbahaya", "bahaya", "bising",
    "panas", "gerah", "gelap", "licin", "sempit",
    "angker", "menakutkan", "seram", "unsafe", "dangerous",
    "uncomfortable", "dirty", "messy",

    # Akses dan kondisi perjalanan
    "susah", "sulit", "macet", "curam", "ekstrem",
    "extreme", "melelahkan", "jauh", "terjal", "rusak",
    "berlubang", "ribet", "challenging", "difficult",
    "hard", "struggle",

    # Fasilitas dan pelayanan
    "mahal", "minim", "kurang", "lambat", "kekurangan",
    "mengganggu", "membosankan", "bosan", "penuh", "padat",
    "tidakramah", "unfriendly", "crowded", "overpriced",
    "expensive", "limited", "inadequate", "poorly",

    # Keluhan lainnya
    "sedih", "hate", "kacau", "pungli", "penipuan",
    "hilang", "terlantar", "terbengkalai", "tidakberfungsi",
    "notworth", "waste", "problem", "problems"
}


# =========================================================
# 4. NEGASI DAN KATA PENGUAT
# =========================================================

# Negasi yang dapat membalik sentimen kata setelahnya
negation_words = {
    "tidak", "bukan", "belum", "jangan", "never", "not",
    "no", "hardly"
}

# "kurang" diperlakukan sebagai negasi/modifier,
# bukan kata negatif yang berdiri sendiri
negation_modifiers = {
    "kurang"
}

# Kata penguat
intensifiers = {
    "sangat", "amat", "banget", "sekali", "begitu",
    "super", "really", "very", "extremely", "so",
    "too", "highly"
}

# Kata pelemah sentimen
diminishers = {
    "cukup", "lumayan", "agak", "sedikit", "quite",
    "fairly", "somewhat", "rather"
}

# Konjungsi yang sering menunjukkan perubahan sentimen
contrast_words = {
    "tetapi", "tapi", "namun", "sayangnya", "cuma",
    "sayang", "but", "however", "although", "though"
}


# =========================================================
# 5. FUNGSI TOKENISASI
# =========================================================

def tokenize(text):
    """
    Mengambil token berupa kata dan mengabaikan tanda baca.
    """

    text = str(text).lower()

    tokens = re.findall(
        r"[a-zA-Z]+",
        text
    )

    return tokens


# =========================================================
# 6. FUNGSI ANALISIS SENTIMEN
# =========================================================

def analyze_sentiment(text):

    if pd.isna(text) or str(text).strip() == "":
        return pd.Series([
            0, 0, 0, "Neutral"
        ])

    tokens = tokenize(text)

    positive_score = 0
    negative_score = 0

    for i, word in enumerate(tokens):

        # ---------------------------------------------
        # Menentukan polaritas kata
        # ---------------------------------------------

        if word in positive_words:
            word_score = 1

        elif word in negative_words:
            word_score = -1

        else:
            continue

        # ---------------------------------------------
        # Pemeriksaan konteks sebelumnya
        # ---------------------------------------------

        start = max(0, i - 3)
        previous_words = tokens[start:i]

        # ---------------------------------------------
        # Penanganan negasi
        # ---------------------------------------------

        negated = any(
            negation in previous_words
            for negation in negation_words
        )

        negated_by_modifier = any(
            modifier in previous_words
            for modifier in negation_modifiers
        )

        if negated or negated_by_modifier:
            word_score *= -1

        # ---------------------------------------------
        # Penanganan intensifier
        # ---------------------------------------------

        if any(
            word_before in intensifiers
            for word_before in previous_words
        ):
            word_score *= 2

        # ---------------------------------------------
        # Penanganan kata pelemah
        # ---------------------------------------------

        if any(
            word_before in diminishers
            for word_before in previous_words
        ):
            word_score *= 0.5

        # ---------------------------------------------
        # Memisahkan skor positif dan negatif
        # ---------------------------------------------

        if word_score > 0:
            positive_score += word_score

        elif word_score < 0:
            negative_score += abs(word_score)

    # ---------------------------------------------
    # Skor akhir
    # ---------------------------------------------

    sentiment_score = positive_score - negative_score

    # ---------------------------------------------
    # Penentuan label sentimen
    # ---------------------------------------------

    if sentiment_score > 0:
        sentiment = "Positive"

    elif sentiment_score < 0:
        sentiment = "Negative"

    else:
        sentiment = "Neutral"

    return pd.Series([
        positive_score,
        negative_score,
        sentiment_score,
        sentiment
    ])


# =========================================================
# 7. PROSES LABELING DATASET
# =========================================================

def main():

    print("Membaca dataset preprocessing...")

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"File input tidak ditemukan: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    if "preprocessed_text" not in df.columns:
        raise ValueError(
            "Kolom 'preprocessed_text' tidak ditemukan!"
        )

    # ---------------------------------------------
    # Menghapus review kosong
    # ---------------------------------------------

    df = df[
        df["preprocessed_text"].notna()
        & (
            df["preprocessed_text"]
            .astype(str)
            .str.strip() != ""
        )
    ].copy()

    print(f"Jumlah review yang diproses: {len(df)}")

    # ---------------------------------------------
    # Analisis sentimen berdasarkan teks
    # ---------------------------------------------

    result = df["preprocessed_text"].apply(
        analyze_sentiment
    )

    result.columns = [
        "positive_score",
        "negative_score",
        "sentiment_score",
        "sentiment"
    ]

    df = pd.concat(
        [df.reset_index(drop=True),
         result.reset_index(drop=True)],
        axis=1
    )

    # ---------------------------------------------
    # Konversi label kategorikal menjadi angka
    # ---------------------------------------------

    label_mapping = {
        "Negative": -1,
        "Neutral": 0,
        "Positive": 1
    }

    df["label"] = df["sentiment"].map(label_mapping)

    # ---------------------------------------------
    # Simpan hasil
    # ---------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # =====================================================
    # 8. RINGKASAN HASIL LABELING
    # =====================================================

    print("\n===== HASIL SENTIMENT LABELING =====")
    print(df["sentiment"].value_counts())

    print("\n===== DISTRIBUSI LABEL =====")
    print(
        df["label"]
        .value_counts()
        .sort_index()
    )

    print("\n===== PERSENTASE SENTIMEN =====")
    print(
        df["sentiment"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
    )

    print("\n===== RATA-RATA SKOR SENTIMEN =====")
    print(
        df[
            [
                "positive_score",
                "negative_score",
                "sentiment_score"
            ]
        ].mean().round(2)
    )

    # ---------------------------------------------
    # Contoh hasil
    # ---------------------------------------------

    print("\n===== CONTOH HASIL LABELING =====")

    print(
        df[
            [
                "preprocessed_text",
                "positive_score",
                "negative_score",
                "sentiment_score",
                "sentiment",
                "label"
            ]
        ].head(10).to_string(index=False)
    )

    # ---------------------------------------------
    # Contoh review yang terdeteksi mixed sentiment
    # ---------------------------------------------

    mixed_reviews = df[
        (df["positive_score"] > 0)
        & (df["negative_score"] > 0)
    ]

    print("\n===== JUMLAH REVIEW MIXED SENTIMENT =====")
    print(len(mixed_reviews))

    print("\n===== CONTOH REVIEW MIXED SENTIMENT =====")

    if len(mixed_reviews) > 0:
        print(
            mixed_reviews[
                [
                    "preprocessed_text",
                    "positive_score",
                    "negative_score",
                    "sentiment_score",
                    "sentiment"
                ]
            ].head(10).to_string(index=False)
        )

    # ---------------------------------------------
    # Informasi output
    # ---------------------------------------------

    print("\nDataset labeling berhasil disimpan:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
