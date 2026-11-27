
import re
import joblib
import pandas as pd

from pathlib import Path
from difflib import SequenceMatcher


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DESTINATION_FILE = (
    BASE_DIR / "data" / "processed" / "destinasi" / "destinasi_clean.csv"
)

REVIEW_FILE = (
    BASE_DIR / "data" / "processed" / "reviews" / "wisata_kp_reviews_clean.csv"
)

MODEL_FILE = BASE_DIR / "models" / "final" / "sentiment_model.pkl"
VECTORIZER_FILE = BASE_DIR / "models" / "final" / "tfidf_vectorizer.pkl"


# ============================================================
# GENERAL UTILITIES
# ============================================================

def safe_text(value, default="-"):
    if pd.isna(value):
        return default

    value = str(value).strip()

    if value.lower() in ["", "nan", "none"]:
        return default

    return value


def normalize_text(text):
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_name(text):
    text = str(text).lower().strip()
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[^a-z0-9]", "", text)

    return text


def safe_float(value):
    try:
        if pd.isna(value):
            return None

        return float(value)

    except (TypeTypeError, TypeError, ValueError):
        return None


def format_number(value):
    try:
        return f"{int(float(value)):,}".replace(",", ".")

    except (TypeError, ValueError):
        return "0"


def format_rating(value):
    value = safe_float(value)

    if value is None:
        return "Tidak tersedia"

    return f"{value:.1f}/5"


def percentage(value, total):
    if total == 0:
        return 0

    return value / total * 100


# ============================================================
# DESTINATION CATEGORY
# ============================================================

CATEGORY_KEYWORDS = {
    "Pantai": [
        "pantai", "beach", "laut"
    ],

    "Wisata Air": [
        "air terjun", "waterfall", "waduk",
        "embung", "sungai", "waterpark"
    ],

    "Desa & Budaya": [
        "desa wisata", "desa", "budaya",
        "kampung", "museum"
    ],

    "Kuliner": [
        "kuliner", "restoran", "restaurant",
        "cafe", "café", "warung", "kopi"
    ],

    "Taman & Kebun": [
        "taman", "kebun", "garden", "agrowisata"
    ],

    "Panorama": [
        "bukit", "puncak", "view", "panorama",
        "sunrise", "sunset"
    ],

    "Wisata Alam": [
        "alam", "hutan", "goa", "gua", "gunung"
    ]
}


def get_category(name):

    name = str(name).lower()

    for category, keywords in CATEGORY_KEYWORDS.items():

        if any(keyword in name for keyword in keywords):
            return category

    return "Lainnya"


# ============================================================
# DATA LOADING
# ============================================================

def load_destinations():

    if not DESTINATION_FILE.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(DESTINATION_FILE)

        required_columns = [
            "title",
            "address",
            "latitude",
            "longitude",
            "totalScore",
            "reviewsCount"
        ]

        for column in required_columns:

            if column not in df.columns:
                df[column] = None

        df["title"] = df["title"].fillna("").astype(str)

        df["kategori"] = df["title"].apply(get_category)

        df["rating_num"] = pd.to_numeric(
            df["totalScore"],
            errors="coerce"
        )

        df["reviews_num"] = pd.to_numeric(
            df["reviewsCount"],
            errors="coerce"
        ).fillna(0)

        df = df[df["title"].str.strip() != ""]

        return df.reset_index(drop=True)

    except Exception as error:
        print(f"Error loading destinations: {error}")
        return pd.DataFrame()


def load_reviews():

    if not REVIEW_FILE.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(REVIEW_FILE)

        required_columns = [
            "nama_destinasi",
            "review",
            "rating"
        ]

        for column in required_columns:

            if column not in df.columns:
                df[column] = None

        df = df[required_columns].copy()

        df["nama_destinasi"] = (
            df["nama_destinasi"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        df["review"] = (
            df["review"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        df = df[df["review"] != ""]

        return df.reset_index(drop=True)

    except Exception as error:
        print(f"Error loading reviews: {error}")
        return pd.DataFrame()


def load_sentiment_model():

    try:

        if MODEL_FILE.exists():
            return joblib.load(MODEL_FILE)

    except Exception as error:
        print(f"Error loading model: {error}")

    return None


def load_vectorizer():

    try:

        if VECTORIZER_FILE.exists():
            return joblib.load(VECTORIZER_FILE)

    except Exception as error:
        print(f"Error loading vectorizer: {error}")

    return None


# ============================================================
# SENTIMENT UTILITIES
# ============================================================

def normalize_sentiment(value):

    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    if value in ["positive", "positif", "pos", "1"]:
        return "Positive"

    if value in ["neutral", "netral", "neu", "0"]:
        return "Neutral"

    if value in ["negative", "negatif", "neg", "-1"]:
        return "Negative"

    if "posit" in value:
        return "Positive"

    if "neutral" in value or "netral" in value:
        return "Neutral"

    if "negat" in value:
        return "Negative"

    return None


def predict_reviews(df, model, vectorizer):

    df = df.copy()

    if df.empty:
        df["sentiment"] = pd.Series(dtype=str)
        return df

    # Gunakan model yang sudah tersedia
    if model is None or vectorizer is None:
        df["sentiment"] = None
        return df

    try:

        X = vectorizer.transform(df["review"])
        predictions = model.predict(X)

        df["sentiment"] = [
            normalize_sentiment(prediction)
            for prediction in predictions
        ]

    except Exception as error:

        print(f"Sentiment prediction error: {error}")
        df["sentiment"] = None

    return df


def get_sentiment_counts(df):

    counts = {
        "Positive": 0,
        "Neutral": 0,
        "Negative": 0
    }

    if df.empty or "sentiment" not in df.columns:
        return counts

    for value in df["sentiment"]:

        sentiment = normalize_sentiment(value)

        if sentiment in counts:
            counts[sentiment] += 1

    return counts


def get_total_sentiment(counts):
    return sum(counts.values())


def get_dominant_sentiment(counts):

    if sum(counts.values()) == 0:
        return "Tidak tersedia"

    return max(counts, key=counts.get)


# ============================================================
# INITIALIZE DATA
# ============================================================

DESTINATIONS = load_destinations()
RAW_REVIEWS = load_reviews()

MODEL = load_sentiment_model()
VECTORIZER = load_vectorizer()

REVIEWS = predict_reviews(
    RAW_REVIEWS,
    MODEL,
    VECTORIZER
)


# ============================================================
# DESTINATION MATCHING
# ============================================================

def find_destination(text):

    text_normalized = normalize_name(text)

    if not text_normalized or DESTINATIONS.empty:
        return None

    destination_names = DESTINATIONS["title"].tolist()

    # Exact match
    for name in destination_names:

        if normalize_name(name) == text_normalized:
            return name

    # Longest partial match
    for name in sorted(
        destination_names,
        key=lambda x: len(normalize_name(x)),
        reverse=True
    ):

        normalized_name = normalize_name(name)

        if (
            normalized_name
            and normalized_name in text_normalized
        ):
            return name

    # Similarity matching
    best_match = None
    best_score = 0

    for name in destination_names:

        score = SequenceMatcher(
            None,
            text_normalized,
            normalize_name(name)
        ).ratio()

        if score > best_score:
            best_score = score
            best_match = name

    if best_score >= 0.88:
        return best_match

    return None


def find_all_destinations_in_text(text):

    text_normalized = normalize_name(text)

    found = []

    if DESTINATIONS.empty:
        return found

    for name in DESTINATIONS["title"].tolist():

        normalized_name = normalize_name(name)

        if (
            normalized_name
            and normalized_name in text_normalized
        ):
            found.append(name)

    # Hilangkan duplikat
    found = list(set(found))

    # Nama destinasi terpanjang diprioritaskan
    return sorted(
        found,
        key=lambda x: len(normalize_name(x)),
        reverse=True
    )


def get_destination(name):

    if DESTINATIONS.empty:
        return None

    matched = DESTINATIONS[
        DESTINATIONS["title"] == name
    ]

    if matched.empty:
        return None

    return matched.iloc[0]


# ============================================================
# REVIEW MATCHING
# ============================================================

def get_destination_reviews(name):

    if REVIEWS.empty:
        return pd.DataFrame()

    target = normalize_name(name)

    review_names = (
        REVIEWS["nama_destinasi"]
        .dropna()
        .unique()
        .tolist()
    )

    matched_names = []

    # Exact match
    for review_name in review_names:

        if (
            str(review_name).strip().lower()
            == str(name).strip().lower()
        ):
            matched_names.append(review_name)

    # Normalized match
    if not matched_names:

        for review_name in review_names:

            if normalize_name(review_name) == target:
                matched_names.append(review_name)

    # Partial match
    if not matched_names and len(target) >= 5:

        partial_matches = []

        for review_name in review_names:

            normalized_review_name = normalize_name(
                review_name
            )

            if (
                target in normalized_review_name
                or normalized_review_name in target
            ):
                partial_matches.append(review_name)

        if partial_matches:

            matched_names = [
                max(
                    partial_matches,
                    key=lambda x: len(normalize_name(x))
                )
            ]

    # Similarity fallback
    if not matched_names:

        scored = []

        for review_name in review_names:

            score = SequenceMatcher(
                None,
                target,
                normalize_name(review_name)
            ).ratio()

            scored.append((review_name, score))

        scored.sort(
            key=lambda item: item[1],
            reverse=True
        )

        if scored and scored[0][1] >= 0.88:
            matched_names = [scored[0][0]]

    if not matched_names:
        return pd.DataFrame()

    return REVIEWS[
        REVIEWS["nama_destinasi"].isin(matched_names)
    ].copy()


# ============================================================
# INTENT KEYWORDS
# ============================================================

INTENT_KEYWORDS = {

    "comparison": [
        "bandingkan",
        "dibandingkan",
        "perbandingan",
        "vs",
        "mana lebih",
        "lebih bagus",
        "lebih baik",
        "bagusan",
        "perbedaan",
        "unggul"
    ],

    "review": [
        "review",
        "ulasan",
        "sentimen",
        "pengalaman pengunjung",
        "pengunjung",
        "komentar",
        "pendapat",
        "disukai",
        "tidak disukai",
        "kesan",
        "positif",
        "negatif",
        "negative",
        "positive",
        "neutral",
        "netral",
        "puas",
        "persepsi"
    ],

    "popular": [
        "populer",
        "popular",
        "terpopuler",
        "paling ramai",
        "paling banyak diulas",
        "review terbanyak",
        "ulasan terbanyak",
        "jumlah review terbanyak",
        "jumlah ulasan terbanyak",
        "terfavorit",
        "favorit",
        "ranking",
        "urutkan",
        "top ",
        "nomor satu",
        "nomor 1"
    ],

    "recommendation": [
        "rekomendasi",
        "rekomendasikan",
        "pilihkan",
        "cocok",
        "ingin pergi",
        "mau pergi",
        "healing",
        "liburan",
        "mau jalan",
        "enaknya ke mana",
        "tempat wisata",
        "wisata pantai",
        "wisata alam",
        "wisata kuliner"
    ],

    "information": [
        "ceritakan",
        "informasi",
        "info",
        "tentang",
        "seperti apa",
        "ada apa",
        "jelaskan",
        "detail",
        "bagaimana",
        "bagus tidak",
        "bagus nggak",
        "bagus atau tidak",
        "rating",
        "layak dikunjungi",
        "kualitas"
    ]
}


# ============================================================
# INTENT DETECTION
# ============================================================

def contains_keyword(text, keywords):

    return any(
        keyword in text
        for keyword in keywords
    )


def detect_intent(text):

    text_lower = normalize_text(text)

    destinations = find_all_destinations_in_text(text)

    # Ranking review positif harus dikenali sebelum intent review biasa.
    positive_ranking_phrases = [
        "review positif terbanyak",
        "ulasan positif terbanyak",
        "destinasi dengan review positif paling banyak",
        "destinasi dengan ulasan positif paling banyak",
        "review paling positif",
        "ulasan paling positif",
    ]

    if any(
        phrase in text_lower
        for phrase in positive_ranking_phrases
    ):
        return "positive_reviews"

    # --------------------------------------------------------
    # 1. COMPARISON
    # --------------------------------------------------------

    comparison_keywords = INTENT_KEYWORDS["comparison"]

    if (
        len(destinations) >= 2
        and contains_keyword(
            text_lower,
            comparison_keywords
        )
    ):
        return "comparison"

    # --------------------------------------------------------
    # 2. POPULAR DESTINATION
    # --------------------------------------------------------

    if contains_keyword(
        text_lower,
        INTENT_KEYWORDS["popular"]
    ):
        return "popular"

    # --------------------------------------------------------
    # 3. REVIEW & SENTIMENT
    # --------------------------------------------------------

    if contains_keyword(
        text_lower,
        INTENT_KEYWORDS["review"]
    ):
        return "review"

    # --------------------------------------------------------
    # 4. RECOMMENDATION
    # --------------------------------------------------------

    if contains_keyword(
        text_lower,
        INTENT_KEYWORDS["recommendation"]
    ):
        return "recommendation"

    # --------------------------------------------------------
    # 5. DESTINATION INFORMATION
    # --------------------------------------------------------

    if destinations:
        return "information"

    return "unknown"


# ============================================================
# DESTINATION INFORMATION
# ============================================================

def destination_information(name):

    row = get_destination(name)

    if row is None:
        return "Informasi destinasi belum ditemukan."

    reviews = get_destination_reviews(name)
    counts = get_sentiment_counts(reviews)

    rating = safe_float(
        row.get("totalScore")
    )

    response = f"## 🌿 {name}\n\n"

    response += (
        f"⭐ **Rating Destinasi**\n"
        f"{format_rating(rating)}\n\n"
    )

    response += "### 💬 Analisis Review Pengunjung\n\n"

    response += (
        f"🟢 **{format_number(counts['Positive'])}** "
        f"Positive\n\n"
    )

    response += (
        f"🟡 **{format_number(counts['Neutral'])}** "
        f"Neutral\n\n"
    )

    response += (
        f"🔴 **{format_number(counts['Negative'])}** "
        f"Negative"
    )

    return response


# ============================================================
# CATEGORY PREFERENCE
# ============================================================

def extract_category_preference(text):

    text = normalize_text(text)

    if any(word in text for word in [
        "pantai", "laut", "beach"
    ]):
        return "Pantai"

    if any(word in text for word in [
        "air terjun", "waduk", "sungai",
        "waterpark", "wisata air", "embung"
    ]):
        return "Wisata Air"

    if any(word in text for word in [
        "desa", "budaya", "kampung", "museum"
    ]):
        return "Desa & Budaya"

    if any(word in text for word in [
        "kuliner", "makan", "restoran",
        "cafe", "kafe", "kopi"
    ]):
        return "Kuliner"

    if any(word in text for word in [
        "taman", "kebun", "agrowisata"
    ]):
        return "Taman & Kebun"

    if any(word in text for word in [
        "panorama", "view", "pemandangan",
        "sunset", "sunrise", "bukit", "puncak"
    ]):
        return "Panorama"

    if any(word in text for word in [
        "alam", "hutan", "goa", "gua", "gunung"
    ]):
        return "Wisata Alam"

    return None


# ============================================================
# DESTINATION DATA HELPERS
# ============================================================

def get_destination_metrics(name):

    row = get_destination(name)

    if row is None:
        return None

    reviews = get_destination_reviews(name)

    counts = get_sentiment_counts(reviews)

    total_sentiment = sum(counts.values())

    rating = safe_float(
        row.get("totalScore")
    )

    review_count = safe_float(
        row.get("reviewsCount")
    )

    return {
        "name": name,
        "rating": rating,
        "review_count": review_count,
        "sentiment": counts,
        "sentiment_total": total_sentiment
    }


def get_positive_percentage(counts):

    total = sum(counts.values())

    return percentage(
        counts.get("Positive", 0),
        total
    )


# ============================================================
# RECOMMENDATION
# ============================================================

def recommend_destinations(text, limit=5):

    if DESTINATIONS.empty:
        return pd.DataFrame()

    category = extract_category_preference(text)

    df = DESTINATIONS.copy()

    if category:

        filtered = df[
            df["kategori"] == category
        ]

        if not filtered.empty:
            df = filtered.copy()

    # Ranking rating + jumlah review
    df = df.sort_values(
        ["rating_num", "reviews_num"],
        ascending=False,
        na_position="last"
    )

    return df.head(limit)


def recommendation_response(text, limit=5):

    result = recommend_destinations(
        text,
        limit=limit
    )

    if result.empty:
        return (
            "Maaf, belum ditemukan destinasi "
            "yang sesuai dengan permintaanmu."
        )

    category = extract_category_preference(text)

    response = "## 🌿 Rekomendasi Wisata\n\n"

    if category:
        response += f"Kategori: **{category}**\n\n"

    response += (
        "Berikut rekomendasi destinasi berdasarkan rating tertinggi.\n\n"
    )

    for index, (_, row) in enumerate(
        result.iterrows(),
        start=1
    ):

        name = row["title"]

        metrics = get_destination_metrics(name)

        response += f"### {index}. {name}\n\n"

        response += (
            f"⭐ Rating: "
            f"{format_rating(row.get('totalScore'))}\n\n"
        )

    return response


# ============================================================
# REVIEW & SENTIMENT ANALYSIS
# ============================================================

def review_analysis(name=None):

    # --------------------------------------------------------
    # ALL DESTINATIONS
    # --------------------------------------------------------

    if name is None:

        if REVIEWS.empty:
            return "Data review belum tersedia."

        counts = get_sentiment_counts(REVIEWS)

        total = sum(counts.values())

        if total == 0:
            return "Data sentimen belum tersedia."

        response = "## 💬 Analisis Sentimen Wisata Kulon Progo\n\n"

        response += f"Total review dianalisis: **{format_number(total)}**\n\n"

        response += (
            f"🟢 Positive: **{format_number(counts['Positive'])}** "
            f"({percentage(counts['Positive'], total):.1f}%)\n\n"
        )

        response += (
            f"🟡 Neutral: **{format_number(counts['Neutral'])}** "
            f"({percentage(counts['Neutral'], total):.1f}%)\n\n"
        )

        response += (
            f"🔴 Negative: **{format_number(counts['Negative'])}** "
            f"({percentage(counts['Negative'], total):.1f}%)\n\n"
        )

        response += (
            f"**Sentimen dominan: "
            f"{get_dominant_sentiment(counts)}**"
        )

        return response

    # --------------------------------------------------------
    # SINGLE DESTINATION
    # --------------------------------------------------------

    reviews = get_destination_reviews(name)

    if reviews.empty:

        return (
            f"Belum ditemukan data review untuk "
            f"**{name}** di dataset WisataKP."
        )

    counts = get_sentiment_counts(reviews)

    total = sum(counts.values())

    if total == 0:
        return "Belum tersedia data sentimen untuk destinasi ini."

    dominant = get_dominant_sentiment(counts)

    response = f"## 💬 Analisis Review {name}\n\n"

    response += f"Total review dianalisis: **{format_number(total)}**\n\n"

    response += (
        f"🟢 Positive: **{format_number(counts['Positive'])}** "
        f"({percentage(counts['Positive'], total):.1f}%)\n\n"
    )

    response += (
        f"🟡 Neutral: **{format_number(counts['Neutral'])}** "
        f"({percentage(counts['Neutral'], total):.1f}%)\n\n"
    )

    response += (
        f"🔴 Negative: **{format_number(counts['Negative'])}** "
        f"({percentage(counts['Negative'], total):.1f}%)\n\n"
    )

    response += f"**Sentimen Dominan: {dominant}**\n\n"

    if dominant == "Positive":

        response += (
            "Review pengunjung didominasi "
            "oleh sentimen positif."
        )

    elif dominant == "Negative":

        response += (
            "Review pengunjung didominasi "
            "oleh sentimen negatif."
        )

    else:

        response += (
            "Review pengunjung didominasi "
            "oleh sentimen netral."
        )

    return response


# ============================================================
# POPULAR DESTINATION
# ============================================================

def popular_destinations(limit=5):

    if DESTINATIONS.empty:
        return pd.DataFrame()

    df = DESTINATIONS.copy()

    df = df.sort_values(
        ["reviews_num", "rating_num"],
        ascending=False,
        na_position="last"
    )

    return df.head(limit)


def popular_destination_response(limit=5):

    result = popular_destinations(limit)

    if result.empty:
        return "Data destinasi belum tersedia."

    response = "## 🏆 Destinasi Paling Populer\n\n"

    response += (
        "Diurutkan berdasarkan jumlah review "
        "terbanyak pada dataset.\n\n"
    )

    for index, (_, row) in enumerate(
        result.iterrows(),
        start=1
    ):

        response += f"### {index}. {row['title']}\n\n"

        response += (
            f"📝 Review: **{format_number(row.get('reviews_num'))}**\n\n"
        )

        response += (
            f"⭐ Rating: **{format_rating(row.get('totalScore'))}**\n\n"
        )

    return response


# ============================================================
# DESTINATIONS WITH MOST POSITIVE REVIEWS
# ============================================================

def positive_review_destinations(limit=5):

    if REVIEWS.empty or DESTINATIONS.empty:
        return pd.DataFrame()

    result = []

    for _, row in DESTINATIONS.iterrows():

        name = row["title"]

        destination_reviews = get_destination_reviews(name)

        counts = get_sentiment_counts(
            destination_reviews
        )

        total = sum(counts.values())

        result.append({
            "title": name,
            "rating": safe_float(row.get("totalScore")),
            "review_count": total,
            "positive": counts["Positive"],
            "neutral": counts["Neutral"],
            "negative": counts["Negative"],
            "positive_percentage": percentage(
                counts["Positive"],
                total
            )
        })

    df = pd.DataFrame(result)

    if df.empty:
        return df

    return df.sort_values(
        ["positive", "positive_percentage", "rating"],
        ascending=False,
        na_position="last"
    ).head(limit)


def positive_review_response(limit=5):

    result = positive_review_destinations(limit)

    if result.empty:
        return "Data sentimen destinasi belum tersedia."

    response = (
        "## 💚 Destinasi dengan Review Positif Terbanyak\n\n"
        "Diurutkan berdasarkan jumlah review positif.\n\n"
    )

    for index, (_, row) in enumerate(
        result.iterrows(),
        start=1
    ):

        response += (
            f"### {index}. {row['title']}\n\n"
        )

        response += (
            f"⭐ Rating: **{format_rating(row['rating'])}**\n\n"
        )

        response += (
            f"🟢 Positive: **{format_number(row['positive'])}**\n\n"
        )

        response += (
            f"🟡 Neutral: **{format_number(row['neutral'])}**\n\n"
        )

        response += (
            f"🔴 Negative: **{format_number(row['negative'])}**\n\n"
        )

    return response


# ============================================================
# DESTINATION COMPARISON
# ============================================================

def compare_destinations(name1, name2):

    row1 = get_destination(name1)
    row2 = get_destination(name2)

    if row1 is None or row2 is None:
        return "Data salah satu destinasi tidak ditemukan."

    metrics1 = get_destination_metrics(name1)
    metrics2 = get_destination_metrics(name2)

    if metrics1 is None or metrics2 is None:
        return "Data perbandingan tidak tersedia."

    response = "## ⚖️ Perbandingan Destinasi\n\n"

    # Destination 1
    response += f"### 🌿 {name1}\n\n"

    response += (
        f"⭐ Rating: **{format_rating(metrics1['rating'])}**\n\n"
    )

    response += (
        f"📝 Review: **{format_number(metrics1['review_count'])}**\n\n"
    )

    response += (
        f"🟢 Positive: **{format_number(metrics1['sentiment']['Positive'])}**\n\n"
    )

    response += (
        f"🟡 Neutral: **{format_number(metrics1['sentiment']['Neutral'])}**\n\n"
    )

    response += (
        f"🔴 Negative: **{format_number(metrics1['sentiment']['Negative'])}**\n\n"
    )

    # Destination 2
    response += f"### 🌿 {name2}\n\n"

    response += (
        f"⭐ Rating: **{format_rating(metrics2['rating'])}**\n\n"
    )

    response += (
        f"📝 Review: **{format_number(metrics2['review_count'])}**\n\n"
    )

    response += (
        f"🟢 Positive: **{format_number(metrics2['sentiment']['Positive'])}**\n\n"
    )

    response += (
        f"🟡 Neutral: **{format_number(metrics2['sentiment']['Neutral'])}**\n\n"
    )

    response += (
        f"🔴 Negative: **{format_number(metrics2['sentiment']['Negative'])}**\n\n"
    )

    # Comparison summary
    response += "## 📊 Hasil Perbandingan\n\n"

    if (
        metrics1["rating"] is not None
        and metrics2["rating"] is not None
    ):

        if metrics1["rating"] > metrics2["rating"]:

            response += (
                f"⭐ **{name1}** memiliki rating lebih tinggi.\n\n"
            )

        elif metrics2["rating"] > metrics1["rating"]:

            response += (
                f"⭐ **{name2}** memiliki rating lebih tinggi.\n\n"
            )

        else:

            response += "⭐ Rating kedua destinasi sama.\n\n"

    if (
        metrics1["review_count"] is not None
        and metrics2["review_count"] is not None
    ):

        if metrics1["review_count"] > metrics2["review_count"]:

            response += (
                f"📝 **{name1}** memiliki jumlah review lebih banyak.\n\n"
            )

        elif metrics2["review_count"] > metrics1["review_count"]:

            response += (
                f"📝 **{name2}** memiliki jumlah review lebih banyak.\n\n"
            )

        else:

            response += "📝 Jumlah review kedua destinasi sama.\n\n"

    positive1 = metrics1["sentiment"]["Positive"]
    positive2 = metrics2["sentiment"]["Positive"]

    if positive1 > positive2:

        response += (
            f"💚 **{name1}** memiliki review positif lebih banyak."
        )

    elif positive2 > positive1:

        response += (
            f"💚 **{name2}** memiliki review positif lebih banyak."
        )

    else:

        response += "💚 Jumlah review positif kedua destinasi sama."

    return response


# ============================================================
# SHORTCUT HANDLER
# ============================================================

def handle_shortcut(shortcut):

    shortcut = str(shortcut).lower().strip()

    if "rekomendasi" in shortcut:
        return recommendation_response("rekomendasi wisata")

    if "populer" in shortcut:
        return popular_destination_response()

    if "review positif" in shortcut:
        return positive_review_response()

    return handle_wisbot(shortcut)


# ============================================================
# RESPONSE GENERATOR
# ============================================================

def handle_wisbot(text):

    if not text or not str(text).strip():

        return (
            "Silakan masukkan pertanyaan terlebih dahulu."
        )

    text = str(text).strip()

    intent = detect_intent(text)

    if intent == "positive_reviews":
        return positive_review_response()

    # --------------------------------------------------------
    # 1. DESTINATION INFORMATION
    # --------------------------------------------------------

    if intent == "information":

        destination = find_destination(text)

        if destination:

            return destination_information(
                destination
            )

        return (
            "Destinasi belum berhasil dikenali.\n\n"
            "Coba sebutkan nama tempat wisata "
            "secara lebih spesifik."
        )

    # --------------------------------------------------------
    # 2. DESTINATION RECOMMENDATION
    # --------------------------------------------------------

    elif intent == "recommendation":

        return recommendation_response(text)

    # --------------------------------------------------------
    # 3. REVIEW & SENTIMENT ANALYSIS
    # --------------------------------------------------------

    elif intent == "review":

        destination = find_destination(text)

        if destination:

            return review_analysis(
                destination
            )

        # Jika pengguna bertanya sentimen secara umum
        if any(
            keyword in normalize_text(text)
            for keyword in [
                "seluruh wisata",
                "semua wisata",
                "wisata kulon progo",
                "wisata di kulon progo",
                "destinasi wisata"
            ]
        ):

            return review_analysis()

        return (
            "Untuk menganalisis review, sebutkan "
            "nama destinasi yang ingin kamu ketahui.\n\n"
            "Contoh: Bagaimana sentimen pengunjung Pantai Glagah?"
        )

    # --------------------------------------------------------
    # 4. POPULAR DESTINATION
    # --------------------------------------------------------

    elif intent == "popular":

        return popular_destination_response()

    # --------------------------------------------------------
    # 5. DESTINATION COMPARISON
    # --------------------------------------------------------

    elif intent == "comparison":

        found = find_all_destinations_in_text(text)

        if len(found) >= 2:

            return compare_destinations(
                found[0],
                found[1]
            )

        return (
            "Sebutkan dua destinasi yang ingin dibandingkan.\n\n"
            "Contoh: Bandingkan Pantai Glagah dan Pantai Trisik."
        )

    # --------------------------------------------------------
    # UNKNOWN / DEFAULT
    # --------------------------------------------------------

    return (
        "## 👋 Hai! Aku WisBot\n\n"
        "Asisten wisata Kulon Progo yang siap membantu "
        "menemukan destinasi wisata berdasarkan data WisataKP.\n\n"
        "### 🌿 Yang bisa aku bantu:\n\n"
        "- Rekomendasi destinasi wisata\n"
        "- Informasi destinasi\n"
        "- Analisis review dan sentimen pengunjung\n"
        "- Destinasi paling populer\n"
        "- Perbandingan destinasi\n"
        "\n"
        "Coba tanyakan sesuatu tentang wisata Kulon Progo! 😊"
    )
