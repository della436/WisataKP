# ============================================================
# WISATAKP - EXPLORE DESTINATIONS
# ============================================================

import base64
import random
import re
import sqlite3

from datetime import datetime
from difflib import SequenceMatcher
from html import escape
from pathlib import Path

import folium
import joblib
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


# ============================================================
# 1. PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR

BACKGROUND_PATH = ROOT_DIR / "assets" / "images" / "kp.png"
DESTINATION_FILE = BASE_DIR / "data" / "processed" / "destinasi" / "destinasi_clean.csv"
REVIEW_FILE = BASE_DIR / "data" / "processed" / "reviews" / "wisata_kp_reviews_clean.csv"
MODEL_FILE = BASE_DIR / "models" / "final" / "sentiment_model.pkl"
VECTORIZER_FILE = BASE_DIR / "models" / "final" / "tfidf_vectorizer.pkl"
DB_FILE = BASE_DIR / "data" / "user_reviews.db"


# ============================================================
# EXPLORE PAGE BACKGROUND
# ============================================================

if BACKGROUND_PATH.exists():

    with open(BACKGROUND_PATH, "rb") as image_file:
        encoded_background = base64.b64encode(
            image_file.read()
        ).decode("utf-8")

    st.markdown(
        f"""
        <style>
        [data-testid="stMain"] {{
            background-image:
                linear-gradient(
                    rgba(240, 247, 253, 0.72),
                    rgba(240, 247, 253, 0.82)
                ),
                url("data:image/jpeg;base64,{encoded_background}");

            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}

        [data-testid="stMainBlockContainer"] {{
            background: transparent !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

else:
    st.warning(f"Background Explore tidak ditemukan: {BACKGROUND_PATH}")


# ============================================================
# LOAD GLOBAL CSS
# ============================================================

def load_css():

    css_files = [
        ROOT_DIR / "styles" / "main.css",
        ROOT_DIR / "styles" / "explore.css",
        ROOT_DIR / "styles" / "sentiment.css",
    ]

    for css_file in css_files:

        if css_file.exists():

            css = css_file.read_text(encoding="utf-8")

            st.markdown(
                f"<style>{css}</style>",
                unsafe_allow_html=True
            )

        else:

            st.warning(f"CSS tidak ditemukan: {css_file}")


load_css()


# ============================================================
# 2. LOAD DATA
# ============================================================

@st.cache_data
def load_destinations():
    if not DESTINATION_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(DESTINATION_FILE)

    required = [
        "title", "address", "latitude", "longitude",
        "totalScore", "reviewsCount"
    ]

    for col in required:
        if col not in df.columns:
            df[col] = None

    df["title"] = df["title"].fillna("").astype(str)
    df["address"] = df["address"].fillna("Alamat tidak tersedia")

    return df


def normalize_sentiment(value):
    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    if value in ["positive", "positif", "pos", "1"]:
        return "Positive"

    elif value in ["neutral", "netral", "neu", "0"]:
        return "Neutral"

    elif value in ["negative", "negatif", "neg", "-1"]:
        return "Negative"

    if "posit" in value:
        return "Positive"

    elif "neutral" in value or "netral" in value:
        return "Neutral"

    elif "negat" in value:
        return "Negative"

    return None


@st.cache_resource
def load_model():
    try:
        if MODEL_FILE.exists():
            return joblib.load(MODEL_FILE)
    except Exception as e:
        print("Model error:", e)

    return None


@st.cache_resource
def load_vectorizer():
    try:
        if VECTORIZER_FILE.exists():
            return joblib.load(VECTORIZER_FILE)
    except Exception as e:
        print("Vectorizer error:", e)

    return None


model = load_model()
vectorizer = load_vectorizer()


@st.cache_data
def load_reviews():
    if not REVIEW_FILE.exists():
        st.warning("Dataset review tidak ditemukan.")
        return pd.DataFrame()

    try:
        df = pd.read_csv(REVIEW_FILE)

        required_columns = [
            "nama_destinasi",
            "review",
            "rating",
        ]

        for column in required_columns:
            if column not in df.columns:
                df[column] = None

        df = df[required_columns].copy()

        # Bersihkan nama destinasi dan review
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

        # Buang review kosong
        df = df[df["review"] != ""].copy()

        # Pastikan model dan vectorizer tersedia
        if model is None or vectorizer is None:
            st.warning("Model sentiment atau vectorizer belum tersedia.")
            df["sentiment"] = "Neutral"
            return df.reset_index(drop=True)

        # Transformasi review menggunakan TF-IDF
        X = vectorizer.transform(df["review"])

        # Prediksi sentiment menggunakan model yang sudah dilatih
        predictions = model.predict(X)

        df["sentiment"] = pd.Series(
            predictions,
            index=df.index
        ).apply(normalize_sentiment)

        return df.reset_index(drop=True)

    except Exception as e:
        st.error(f"Gagal membaca dataset review: {e}")
        return pd.DataFrame()


destinations = load_destinations()
reviews_dataset = load_reviews()

# DEBUG REVIEW
print("=== DEBUG REVIEW ===")
print("Jumlah review:", len(reviews_dataset))
print("Kolom:", reviews_dataset.columns.tolist())

if not reviews_dataset.empty:
    print("Label sentiment:")
    print(reviews_dataset["sentiment"].value_counts(dropna=False))

    print("Nama destinasi:")
    print(reviews_dataset["nama_destinasi"].unique()[:10])


# ============================================================
# 3. DATABASE REVIEW USER
# ============================================================

def init_database():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination_name TEXT NOT NULL,
                nickname TEXT NOT NULL,
                rating INTEGER NOT NULL,
                review_text TEXT NOT NULL,
                sentiment TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def save_user_review(destination, nickname, rating, review, sentiment):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO user_reviews (
                destination_name,
                nickname,
                rating,
                review_text,
                sentiment,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            destination,
            nickname,
            rating,
            review,
            sentiment,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))


def get_user_reviews(destination=None):
    with sqlite3.connect(DB_FILE) as conn:
        if destination is None:
            return pd.read_sql_query(
                "SELECT * FROM user_reviews ORDER BY id DESC",
                conn
            )

        return pd.read_sql_query(
            """
            SELECT * FROM user_reviews
            WHERE destination_name = ?
            ORDER BY id DESC
            """,
            conn,
            params=(destination,)
        )


init_database()


# ============================================================
# 4. HELPER
# ============================================================

def safe_text(value, default="—"):
    if pd.isna(value):
        return default

    value = str(value).strip()

    if value.lower() in ["", "nan", "none"]:
        return default

    return value


def safe_float(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def format_number(value):
    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def normalize_name(value):
    value = str(value).lower().strip()

    # Hapus singkatan dalam tanda kurung, misalnya (MJAA)
    value = re.sub(r"\([^)]*\)", "", value)

    # Hapus karakter selain huruf dan angka
    value = re.sub(r"[^a-z0-9]", "", value)

    return value


def get_category(name):
    name = str(name).lower()

    categories = {
        "Pantai": [
            "pantai", "beach"
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

    for category, keywords in categories.items():
        if any(keyword in name for keyword in keywords):
            return category

    return "Lainnya"


def get_destination_row(name):
    matched = destinations[
        destinations["title"] == name
    ]

    if matched.empty:
        return None

    return matched.iloc[0]


def to_safe_html(value):
    """
    Membersihkan teks agar aman dimasukkan ke HTML:
    escape tag, hindari render LaTeX ($), dan ratakan baris baru.
    """

    text = escape(str(value))
    text = text.replace("$", "&#36;")
    text = text.replace("\r\n", "<br>").replace("\n", "<br>")

    return text


# ============================================================
# 5. REVIEW DESTINATION MATCHING
# ============================================================

def match_destination_reviews(destination_name):
    """
    Mencocokkan review dataset dengan nama destinasi.
    Exact match → normalized match → partial match → similarity fallback.
    """

    if reviews_dataset.empty:
        return pd.DataFrame()

    review_names = (
        reviews_dataset["nama_destinasi"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    target = normalize_name(destination_name)

    if not target:
        return pd.DataFrame()

    matched_names = []

    # 1. Exact match
    matched_names = [
        name for name in review_names
        if str(name).strip().lower() == str(destination_name).strip().lower()
    ]

    # 2. Normalized match
    if not matched_names:
        matched_names = [
            name for name in review_names
            if normalize_name(name) == target
        ]

    # 3. Partial match
    if not matched_names and len(target) >= 5:
        partial_matches = []

        for name in review_names:
            normalized_name = normalize_name(name)

            if (
                target in normalized_name
                or normalized_name in target
            ):
                partial_matches.append(name)

        if partial_matches:
            # Pilih nama yang paling spesifik
            matched_names = [
                max(
                    partial_matches,
                    key=lambda name: len(normalize_name(name))
                )
            ]

    # 4. Similarity fallback
    if not matched_names:
        scored_names = []

        for name in review_names:
            normalized_name = normalize_name(name)

            score = SequenceMatcher(
                None,
                target,
                normalized_name
            ).ratio()

            scored_names.append((name, score))

        scored_names.sort(
            key=lambda x: x[1],
            reverse=True
        )

        if scored_names and scored_names[0][1] >= 0.88:
            matched_names = [scored_names[0][0]]

    print("\n=== DEBUG MATCHING ===")
    print("Destinasi:", destination_name)
    print("Target normalized:", target)
    print("Matched names:", matched_names)

    if not matched_names:
        return pd.DataFrame()

    # Ambil review dari destinasi yang cocok
    matched = reviews_dataset[
        reviews_dataset["nama_destinasi"]
        .astype(str)
        .str.strip()
        .isin(
            [str(name).strip() for name in matched_names]
        )
    ].copy()

    if matched.empty:
        return pd.DataFrame()

    # Standarisasi kolom
    matched = matched.rename(
        columns={
            "nama_destinasi": "destination_name",
            "review": "review_text"
        }
    )

    matched["nickname"] = "Pengunjung"
    matched["created_at"] = ""
    matched["source"] = "Crawling"

    # Standarisasi label sentimen
    matched["sentiment"] = matched["sentiment"].apply(
        normalize_sentiment
    )

    return matched[
        [
            "destination_name",
            "review_text",
            "rating",
            "sentiment",
            "nickname",
            "created_at",
            "source"
        ]
    ].reset_index(drop=True)


# ============================================================
# 6. COMBINE REVIEWS
# ============================================================

def get_all_reviews(destination_name):

    crawling_reviews = match_destination_reviews(
        destination_name
    )

    user_reviews = get_user_reviews(
        destination_name
    )

    if not user_reviews.empty:
        user_reviews["source"] = "Pengguna"
    else:
        user_reviews["source"] = pd.Series(dtype=str)

    columns = [
        "destination_name",
        "review_text",
        "rating",
        "sentiment",
        "nickname",
        "created_at",
        "source"
    ]

    if crawling_reviews.empty:
        crawling_reviews = pd.DataFrame(columns=columns)

    if user_reviews.empty:
        user_reviews = pd.DataFrame(columns=columns)

    all_reviews = pd.concat(
        [crawling_reviews, user_reviews],
        ignore_index=True
    )

    if not all_reviews.empty:

        all_reviews["sentiment"] = (
            all_reviews["sentiment"]
            .apply(normalize_sentiment)
        )

        all_reviews["review_text"] = (
            all_reviews["review_text"]
            .fillna("")
            .astype(str)
        )

        # Buang review kosong
        all_reviews = all_reviews[
            all_reviews["review_text"].str.strip() != ""
        ]

    print("=== DEBUG ALL REVIEWS ===")
    print("Destinasi:", destination_name)
    print("Review crawling:", len(crawling_reviews))
    print("Review pengguna:", len(user_reviews))
    print("Total review:", len(all_reviews))

    return all_reviews


# ============================================================
# 7. SENTIMENT (DATA)
# ============================================================

def get_sentiment_counts(all_reviews):

    counts = {
        "Positive": 0,
        "Neutral": 0,
        "Negative": 0
    }

    if all_reviews.empty:
        return counts

    for sentiment in all_reviews["sentiment"]:

        sentiment = normalize_sentiment(sentiment)

        if sentiment in counts:
            counts[sentiment] += 1

    return counts


# ============================================================
# 7A. SENTIMENT CARD (TOTAL + DONUT + KPI)
# Styling ada di: styles/sentiment.css
# ============================================================

# Warna donut (samakan dengan --wk-*-chart di sentiment.css)
SENTIMENT_COLORS = {
    "Positive": "#5FA67C",   # Green
    "Neutral": "#E3B64F",    # Yellow
    "Negative": "#D96B6B",   # Red
}

# Bintang hanya representasi visual kategori, bukan rating asli
SENTIMENT_STARS = {
    "Positive": 5,
    "Neutral": 3,
    "Negative": 1,
}

# Label Bahasa Indonesia (tab & badge ulasan)
SENTIMENT_LABEL_ID = {
    "Positive": "Positif",
    "Neutral": "Netral",
    "Negative": "Negatif",
}


def build_donut_gradient(counts, total, gap_degree=1.4):
    """
    Membuat conic-gradient untuk donut.
    Urutan searah jarum jam dari atas: Positive → Neutral → Negative.
    """

    segments = [
        label for label in ["Positive", "Neutral", "Negative"]
        if counts[label] > 0
    ]

    gap = gap_degree if len(segments) > 1 else 0

    stops = []
    start = 0.0

    for label in segments:

        span = counts[label] / total * 360
        end = start + span

        color = SENTIMENT_COLORS[label]

        stops.append(f"#FFFFFF {start:.2f}deg {start + gap / 2:.2f}deg")
        stops.append(
            f"{color} {start + gap / 2:.2f}deg {end - gap / 2:.2f}deg"
        )
        stops.append(f"#FFFFFF {end - gap / 2:.2f}deg {end:.2f}deg")

        start = end

    return "conic-gradient(from 0deg, " + ", ".join(stops) + ")"


def render_sentiment_card(counts):

    total = sum(counts.values())

    # Donut (tidak ditampilkan jika belum ada review)
    donut_html = ""

    if total > 0:

        gradient = build_donut_gradient(counts, total)

        donut_html = (
            '<div class="sv-donut-wrapper">'
            f'<div class="sv-donut" style="background: {gradient};">'
            '<div class="sv-donut-hole"></div>'
            '</div>'
            '</div>'
        )

    # KPI cards
    stats_html = ""

    for label in ["Positive", "Neutral", "Negative"]:

        count = counts[label]

        percentage = (
            count / total * 100
            if total > 0
            else 0
        )

        stars = "★" * SENTIMENT_STARS[label]

        stats_html += (
            f'<div class="sv-stat sv-stat-{label.lower()}">'
            f'<div class="sv-stat-label">'
            f'<span class="sv-dot"></span>{label}'
            f'</div>'
            f'<div class="sv-stat-count">{count}</div>'
            f'<div class="sv-stat-percent">{percentage:.1f}%</div>'
            f'<div class="sv-stat-stars">{stars}</div>'
            f'</div>'
        )

    # Empty state
    empty_html = ""

    if total == 0:
        empty_html = (
            '<div class="sv-empty">'
            'Belum ada review yang dapat dianalisis.'
            '</div>'
        )

    html = (
        '<div class="sv-card">'
        '<div class="sv-title">💬 Sentimen Pengunjung</div>'
        '<div class="sv-subtitle">'
        'Distribusi penilaian berdasarkan analisis ulasan'
        '</div>'
        '<div class="sv-total">'
        f'<div class="sv-total-number">{total}</div>'
        '<div class="sv-total-label">Total Ulasan</div>'
        '</div>'
        f'{donut_html}'
        f'<div class="sv-stats">{stats_html}</div>'
        f'{empty_html}'
        '</div>'
    )

    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# 7B. INSIGHT CARD
# Styling ada di: styles/sentiment.css
# ============================================================

def build_insight(counts):
    """
    Menentukan kondisi insight berdasarkan distribusi sentimen.
    Logika sama seperti sebelumnya:
    positif > negatif, negatif > positif, atau berimbang.
    """

    total = sum(counts.values())

    if total == 0:
        return {
            "status": "empty",
            "icon": "💡",
            "badge": "Belum Ada Data",
            "title": "Belum ada insight",
            "description": (
                "Belum tersedia ulasan yang cukup "
                "untuk menghasilkan insight."
            ),
        }

    positive = counts["Positive"]
    negative = counts["Negative"]

    positive_pct = positive / total * 100
    negative_pct = negative / total * 100

    if positive > negative:
        return {
            "status": "positive",
            "icon": "✨",
            "badge": "Positif",
            "title": "Pengalaman pengunjung cenderung positif",
            "description": (
                f"<strong>{positive_pct:.1f}%</strong> dari "
                f"<strong>{total}</strong> ulasan menunjukkan "
                "pengalaman positif."
            ),
        }

    if negative > positive:
        return {
            "status": "attention",
            "icon": "💡",
            "badge": "Perlu Perhatian",
            "title": "Ada hal yang perlu diperhatikan",
            "description": (
                f"<strong>{negative_pct:.1f}%</strong> dari "
                f"<strong>{total}</strong> ulasan menunjukkan "
                "sentimen negatif."
            ),
        }

    return {
        "status": "neutral",
        "icon": "💡",
        "badge": "Netral",
        "title": "Sentimen pengunjung relatif berimbang",
        "description": (
            "Ada pengalaman positif, dan ada aspek yang "
            "<strong>masih perlu diperhatikan</strong>."
        ),
    }


def render_insight_card(counts):

    insight = build_insight(counts)

    html = (
        '<div class="wk-section-title">Insight Pengunjung</div>'
        f'<div class="iv-card iv-{insight["status"]}">'
        f'<div class="iv-icon">{insight["icon"]}</div>'
        '<div class="iv-body">'
        f'<div class="iv-title">{insight["title"]}</div>'
        f'<div class="iv-desc">{insight["description"]}</div>'
        '</div>'
        '<div class="iv-status">'
        '<span class="iv-status-dot"></span>'
        f'{insight["badge"]}'
        '</div>'
        '</div>'
    )

    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# 8. PREDICT USER REVIEW
# ============================================================

def predict_sentiment(text):

    if model is None or vectorizer is None:
        return None

    try:

        transformed = vectorizer.transform([text])
        prediction = model.predict(transformed)[0]

        # Label model dataset: -1 Negative, 0 Neutral, 1 Positive
        return normalize_sentiment(prediction)

    except Exception as e:
        print("Sentiment prediction error:", e)
        return None


# ============================================================
# 9. REVIEW DISPLAY (PENGALAMAN PENGUNJUNG)
# Styling ada di: styles/sentiment.css
# ============================================================

def build_review_card(review):
    """Membuat HTML satu kartu ulasan."""

    nickname = safe_text(
        review.get("nickname"),
        "Pengunjung"
    )

    sentiment = normalize_sentiment(
        review.get("sentiment")
    )

    text_review = safe_text(
        review.get("review_text"),
        ""
    )

    date = safe_text(
        review.get("created_at"),
        ""
    )

    source = safe_text(
        review.get("source"),
        ""
    )

    rating = safe_float(
        review.get("rating")
    )

    # Avatar
    initial = escape(nickname[0].upper()) if nickname else "P"

    # Sumber ulasan + tanggal (jika ada)
    source_label = (
        "User Review"
        if source == "Pengguna"
        else "Visitor Review"
    )

    if date:
        source_label += f" · {date}"

    # Badge sentimen
    if sentiment in SENTIMENT_LABEL_ID:
        badge_class = f"ev-badge-{sentiment.lower()}"
        badge_label = SENTIMENT_LABEL_ID[sentiment]
    else:
        badge_class = "ev-badge-unknown"
        badge_label = "Tidak diketahui"

    # Bintang rating
    if rating is None:

        stars_html = '<span class="ev-no-rating">Tanpa rating</span>'

    else:

        filled = max(0, min(5, int(round(rating))))

        stars_html = "".join(
            f'<span class="ev-star{" on" if i <= filled else ""}">★</span>'
            for i in range(1, 6)
        )

    return (
        '<div class="ev-card">'
        '<div class="ev-header">'
        f'<div class="ev-avatar">{initial}</div>'
        '<div class="ev-meta">'
        f'<div class="ev-name">{to_safe_html(nickname)}</div>'
        f'<div class="ev-source">{to_safe_html(source_label)}</div>'
        '</div>'
        f'<div class="ev-badge {badge_class}">{badge_label}</div>'
        '</div>'
        f'<div class="ev-stars">{stars_html}</div>'
        f'<div class="ev-text">{to_safe_html(text_review)}</div>'
        '</div>'
    )


def render_review_list(reviews, empty_message, empty_type="info"):
    """Menampilkan daftar ulasan, atau pesan kosong."""

    if reviews.empty:

        if empty_type == "success":
            st.success(empty_message)
        else:
            st.info(empty_message)

        return

    cards = "".join(
        build_review_card(review)
        for _, review in reviews.iterrows()
    )

    st.markdown(
        f'<div class="ev-list">{cards}</div>',
        unsafe_allow_html=True
    )


# ============================================================
# 10. DESTINATION CARD
# ============================================================

def show_destination_card(row, key):

    name = safe_text(row["title"])

    with st.container(border=True):

        st.caption(get_category(name))

        st.markdown(f"**{name}**")

        st.caption(
            f"📍 {safe_text(row.get('address'))}"
        )

        score = safe_float(row.get("totalScore"))

        if score is not None:
            st.write(f"⭐ {score:.1f}/5")

        if st.button(
            "Lihat Detail →",
            key=key,
            use_container_width=True
        ):

            st.session_state.selected_destination = name
            st.rerun()


# ============================================================
# 11. PAGE HEADER
# ============================================================

st.markdown("""
<div class="explore-hero">
    <div class="hero-eyebrow">DISCOVER · EXPLORE · EXPERIENCE</div>
    <h1>EXPLORE DESTINATIONS</h1>
</div>
""", unsafe_allow_html=True)


# ============================================================
# 12. DESTINATION DETAIL
# ============================================================

def show_detail(destination_name):

    row = get_destination_row(destination_name)

    if row is None:
        st.error("Destinasi tidak ditemukan.")
        return

    if st.button("← Kembali ke Explore"):
        st.session_state.selected_destination = None
        st.rerun()

    st.divider()

    # --------------------------------------------------------
    # INFORMATION
    # --------------------------------------------------------

    st.subheader(destination_name)

    st.caption(
        f"📍 {safe_text(row['address'])}"
    )

    destination_rating = safe_float(row["totalScore"])

    all_reviews = get_all_reviews(destination_name)

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "⭐ Rating Destinasi",
            f"{destination_rating:.1f}/5"
            if destination_rating is not None
            else "—"
        )

    st.divider()

    # --------------------------------------------------------
    # INTERACTIVE MAP
    # --------------------------------------------------------

    st.subheader("📍 Lokasi Destinasi")

    latitude = safe_float(row["latitude"])
    longitude = safe_float(row["longitude"])

    if latitude is not None and longitude is not None:

        destination_map = folium.Map(
            location=[latitude, longitude],
            zoom_start=15,
            tiles="OpenStreetMap"
        )

        folium.Marker(
            location=[latitude, longitude],
            tooltip=destination_name,
            popup=folium.Popup(
                f"<b>{destination_name}</b><br>{safe_text(row['address'])}",
                max_width=300
            ),
            icon=folium.Icon(
                color="green",
                icon="info-sign"
            )
        ).add_to(destination_map)

        st_folium(
            destination_map,
            width=None,
            height=420,
            returned_objects=[]
        )

        st.link_button(
            "Buka di Google Maps ↗",
            f"https://www.google.com/maps?q={latitude},{longitude}"
        )

    else:

        st.warning("Koordinat destinasi belum tersedia.")

        st.link_button(
            "Cari di Google Maps ↗",
            "https://www.google.com/maps/search/?api=1&query="
            + destination_name.replace(" ", "+")
        )

    st.divider()

    # --------------------------------------------------------
    # SENTIMEN PENGUNJUNG (TOTAL + DONUT + KPI)
    # --------------------------------------------------------

    counts = get_sentiment_counts(all_reviews)

    render_sentiment_card(counts)

    # --------------------------------------------------------
    # INSIGHT PENGUNJUNG
    # --------------------------------------------------------

    render_insight_card(counts)

    st.divider()

    # --------------------------------------------------------
    # PENGALAMAN PENGUNJUNG (POSITIF / NEGATIF / NETRAL)
    # --------------------------------------------------------

    st.markdown(
        '<div class="wk-section-title">Pengalaman Pengunjung</div>',
        unsafe_allow_html=True
    )

    positive_reviews = all_reviews[
        all_reviews["sentiment"] == "Positive"
    ]

    negative_reviews = all_reviews[
        all_reviews["sentiment"] == "Negative"
    ]

    neutral_reviews = all_reviews[
        all_reviews["sentiment"] == "Neutral"
    ]

    tab_positive, tab_negative, tab_neutral = st.tabs([
        f"💚 Positif ({len(positive_reviews)})",
        f"⚠️ Negatif ({len(negative_reviews)})",
        f"🟡 Netral ({len(neutral_reviews)})"
    ])

    # POSITIF

    with tab_positive:

        render_review_list(
            positive_reviews,
            "Belum terdapat ulasan positif."
        )

    # NEGATIF

    with tab_negative:

        render_review_list(
            negative_reviews,
            "Belum terdapat ulasan negatif.",
            empty_type="success"
        )

    # NETRAL

    with tab_neutral:

        render_review_list(
            neutral_reviews,
            "Belum terdapat ulasan netral."
        )

    st.divider()


# ============================================================
# 13. MAIN EXPLORE
# ============================================================

if destinations.empty:

    st.error(
        "Dataset destinasi tidak ditemukan. "
        "Periksa file destinasi_clean.csv."
    )

else:

    if "selected_destination" not in st.session_state:
        st.session_state.selected_destination = None

    if "surprise_destination" not in st.session_state:
        st.session_state.surprise_destination = None

    # DETAIL PAGE

    if st.session_state.selected_destination:

        show_detail(
            st.session_state.selected_destination
        )

    # EXPLORE PAGE

    else:

        st.subheader("🔎 Smart Explore")

        st.write(
            "Cari destinasi berdasarkan nama "
            "atau pilih kategori wisata."
        )

        col_search, col_category = st.columns([2, 1])

        with col_search:

            keyword = st.text_input(
                "Cari Destinasi",
                placeholder="Contoh: Pantai Glagah",
                key="explore_keyword"
            )

        destinations["kategori"] = (
            destinations["title"].apply(get_category)
        )

        categories = [
            "Semua Kategori"
        ] + sorted(
            destinations["kategori"].dropna().unique().tolist()
        )

        with col_category:

            selected_category = st.selectbox(
                "Kategori",
                categories,
                key="explore_category"
            )

        # FILTER

        filtered = destinations.copy()

        if keyword.strip():

            filtered = filtered[
                filtered["title"].str.contains(
                    keyword.strip(),
                    case=False,
                    na=False,
                    regex=False
                )
            ]

        if selected_category != "Semua Kategori":

            filtered = filtered[
                filtered["kategori"] == selected_category
            ]

        search_active = bool(keyword.strip())

        category_active = (
            selected_category != "Semua Kategori"
        )

        st.divider()

        # SURPRISE ME

        st.subheader("🎲 Surprise Me")

        st.write(
            "Temukan destinasi pilihan secara acak."
        )

        if st.button(
            "🎲 Pilihkan Destinasi",
            use_container_width=True
        ):

            st.session_state.surprise_destination = random.choice(
                destinations["title"].tolist()
            )

        surprise = st.session_state.surprise_destination

        if surprise:

            surprise_row = get_destination_row(surprise)

            if surprise_row is not None:

                show_destination_card(
                    surprise_row,
                    key="surprise_destination_card"
                )

                if st.button(
                    "🔄 Reroll",
                    key="surprise_reroll",
                    use_container_width=True
                ):

                    available = destinations[
                        destinations["title"] != surprise
                    ]["title"].tolist()

                    if available:
                        st.session_state.surprise_destination = random.choice(
                            available
                        )

                    st.rerun()

        # SEARCH RESULTS

        if search_active or category_active:

            st.divider()

            st.subheader("🌿 Hasil Explore")

            st.caption(
                f"Menampilkan {len(filtered)} destinasi"
            )

            if filtered.empty:

                st.info(
                    "Destinasi tidak ditemukan. "
                    "Coba kata kunci lainnya."
                )

            else:

                for start in range(0, len(filtered), 3):

                    chunk = filtered.iloc[start:start + 3]

                    columns = st.columns(3)

                    for column, (_, row) in zip(
                        columns,
                        chunk.iterrows()
                    ):

                        with column:

                            show_destination_card(
                                row,
                                key=f"result_{start}_{row['title']}"
                            )

        else:

            st.info(
                "🔍 Cari destinasi atau pilih kategori "
                "untuk mulai menjelajah."
            )