# ============================================================
# WISATAKP - EXPLORE DESTINATIONS
# ============================================================

import streamlit as st
import pandas as pd
import sqlite3
import joblib
import random
import re

from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

import folium
from streamlit_folium import st_folium


# ============================================================
# 1. PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DESTINATION_FILE = BASE_DIR / "data" / "processed" / "destinasi" / "destinasi_clean.csv"
REVIEW_FILE = BASE_DIR / "data" / "processed" / "reviews" / "wisata_kp_reviews_labeled.csv"
MODEL_FILE = BASE_DIR / "models" / "final" / "sentiment_model.pkl"
VECTORIZER_FILE = BASE_DIR / "models" / "final" / "tfidf_vectorizer.pkl"
DB_FILE = BASE_DIR / "data" / "user_reviews.db"

def load_css():
    BASE_DIR = Path(__file__).resolve().parent

    css_files = [
        BASE_DIR / "assets" / "css" / "style.css",
        BASE_DIR / "assets" / "css" / "components.css",
    ]

    for css_file in css_files:
        if css_file.exists():
            st.markdown(
                f"<style>{css_file.read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True
            )

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


@st.cache_data
def load_reviews():
    if not REVIEW_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(REVIEW_FILE)

    required = [
        "nama_destinasi",
        "review",
        "rating",
        "sentiment"
    ]

    for col in required:
        if col not in df.columns:
            df[col] = None

    return df


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


destinations = load_destinations()
reviews_dataset = load_reviews()
model = load_model()
vectorizer = load_vectorizer()


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
    value = re.sub(r"[^a-z0-9]", "", value)
    return value


def normalize_sentiment(value):
    if pd.isna(value):
        return "Unknown"

    value = str(value).strip().lower()

    if value in ["positive", "positif", "pos", "1"]:
        return "Positive"

    if value in ["neutral", "netral", "neu", "0"]:
        return "Neutral"

    if value in ["negative", "negatif", "neg", "-1"]:
        return "Negative"

    return "Unknown"


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


# ============================================================
# 5. REVIEW DESTINATION MATCHING
# ============================================================

def match_destination_reviews(destination_name):
    """
    Mencocokkan review dataset dengan nama destinasi.
    Menggunakan exact normalized match terlebih dahulu,
    kemudian similarity match sebagai fallback.
    """

    if reviews_dataset.empty:
        return pd.DataFrame()

    review_names = (
        reviews_dataset["nama_destinasi"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    target = normalize_name(destination_name)

    # Exact normalized match
    matched_names = [
        name for name in review_names
        if normalize_name(name) == target
    ]

    # Similarity fallback
    if not matched_names:

        best_name = None
        best_score = 0

        for name in review_names:
            score = SequenceMatcher(
                None,
                target,
                normalize_name(name)
            ).ratio()

            if score > best_score:
                best_score = score
                best_name = name

        # Hanya menerima nama yang sangat mirip
        if best_score >= 0.88 and best_name:
            matched_names = [best_name]

    if not matched_names:
        return pd.DataFrame()

    matched = reviews_dataset[
        reviews_dataset["nama_destinasi"]
        .astype(str)
        .isin(matched_names)
    ].copy()

    matched = matched.rename(
        columns={
            "nama_destinasi": "destination_name"
        }
    )

    matched["nickname"] = "Pengunjung"
    matched["created_at"] = ""
    matched["source"] = "Crawling"

    matched = matched.rename(
        columns={
            "review": "review_text"
        }
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
    ]


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

    user_reviews = user_reviews.rename(
        columns={
            "destination_name": "destination_name",
            "review_text": "review_text"
        }
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

    return all_reviews


# ============================================================
# 7. SENTIMENT
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


def generate_insight(counts):

    total = sum(counts.values())

    if total == 0:
        return "Belum tersedia ulasan yang cukup untuk menghasilkan insight."

    positive = counts["Positive"]
    neutral = counts["Neutral"]
    negative = counts["Negative"]

    positive_pct = positive / total * 100
    negative_pct = negative / total * 100

    if positive > negative:
        return (
            f"Pengalaman pengunjung cenderung positif. "
            f"{positive_pct:.1f}% ulasan menunjukkan pengalaman positif."
        )

    elif negative > positive:
        return (
            f"Terdapat beberapa hal yang perlu diperhatikan. "
            f"{negative_pct:.1f}% ulasan menunjukkan sentimen negatif."
        )

    else:
        return (
            "Sentimen pengunjung relatif berimbang. "
            "Terdapat pengalaman positif dan aspek yang masih perlu diperhatikan."
        )


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
# 9. REVIEW DISPLAY
# ============================================================

def show_review(review):

    nickname = safe_text(
        review.get("nickname"),
        "Pengunjung"
    )

    rating = safe_text(
        review.get("rating")
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

    icon = {
        "Positive": "🟢",
        "Neutral": "🟡",
        "Negative": "🔴",
        "Unknown": "⚪"
    }

    with st.container(border=True):

        st.markdown(f"**{nickname}**")

        st.caption(
            f"⭐ {rating}  ·  "
            f"{icon.get(sentiment, '⚪')} {sentiment}"
        )

        if date != "—" and date != "":
            st.caption(date)

        st.write(text_review)


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

        st.write(
            f"💬 {format_number(row.get('reviewsCount'))} review Google Maps"
        )

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
    <h1>Explore Destinations 🌿</h1>
    <p>Temukan tempat baru, rencanakan perjalanan,
    dan jelajahi keindahan Kulon Progo.</p>
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

    # Jumlah review aplikasi: dataset + user review
    total_reviews = len(all_reviews)

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "⭐ Rating Destinasi",
            f"{destination_rating:.1f}/5"
            if destination_rating is not None
            else "—"
        )

    with col2:
        st.metric(
            "📝 Total Ulasan",
            total_reviews
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
    # SENTIMENT
    # --------------------------------------------------------

    counts = get_sentiment_counts(all_reviews)

    total_sentiment = sum(counts.values())

    st.subheader("💬 Sentimen Pengunjung")

    col_positive, col_neutral, col_negative = st.columns(3)

    sentiment_columns = [
        (col_positive, "Positive", "🟢"),
        (col_neutral, "Neutral", "🟡"),
        (col_negative, "Negative", "🔴")
    ]

    for column, label, icon in sentiment_columns:

        count = counts[label]

        percentage = (
            count / total_sentiment * 100
            if total_sentiment > 0
            else 0
        )

        with column:
            st.metric(
                f"{icon} {label}",
                count,
                f"{percentage:.1f}%"
            )

    # --------------------------------------------------------
    # CHART
    # --------------------------------------------------------

    if total_sentiment > 0:

        chart_data = pd.DataFrame({
            "Jumlah": [
                counts["Positive"],
                counts["Neutral"],
                counts["Negative"]
            ]
        }, index=[
            "Positive",
            "Neutral",
            "Negative"
        ])

        st.bar_chart(chart_data)

    else:

        st.info(
            "Belum ada review yang memiliki label sentimen."
        )

    # --------------------------------------------------------
    # INSIGHT
    # --------------------------------------------------------

    st.subheader("✨ Insight Pengunjung")

    with st.container(border=True):
        st.write(generate_insight(counts))

    st.divider()

    # --------------------------------------------------------
    # REVIEW TABS
    # --------------------------------------------------------

    tab_positive, tab_negative, tab_all = st.tabs([
        "💚 Hal yang Disukai",
        "⚠️ Hal yang Perlu Diperhatikan",
        "📝 Semua Ulasan"
    ])

    positive_reviews = all_reviews[
        all_reviews["sentiment"] == "Positive"
    ]

    negative_reviews = all_reviews[
        all_reviews["sentiment"] == "Negative"
    ]

    # POSITIVE

    with tab_positive:

        st.subheader("Pengalaman Positif Pengunjung")

        if positive_reviews.empty:

            st.info("Belum terdapat ulasan positif.")

        else:

            for _, review in positive_reviews.iterrows():
                show_review(review)

    # NEGATIVE

    with tab_negative:

        st.subheader("Masukan Pengunjung")

        if negative_reviews.empty:

            st.success("Belum terdapat ulasan negatif.")

        else:

            for _, review in negative_reviews.iterrows():
                show_review(review)

    # ALL

    with tab_all:

        st.subheader(
            f"Semua Ulasan ({len(all_reviews)})"
        )

        if all_reviews.empty:

            st.info("Belum terdapat ulasan.")

        else:

            for _, review in all_reviews.iterrows():
                show_review(review)

    st.divider()

    # --------------------------------------------------------
    # ADD USER REVIEW
    # --------------------------------------------------------

    st.subheader("✍️ Bagikan Pengalamanmu")

    st.write(
        "Ceritakan pengalaman kunjunganmu "
        "untuk membantu pengunjung lainnya."
    )

    with st.form(
        key=f"review_form_{destination_name}"
    ):

        nickname = st.text_input(
            "Nama / Nickname",
            placeholder="Masukkan nama atau nickname"
        )

        rating_input = st.slider(
            "Rating pengalaman",
            min_value=1,
            max_value=5,
            value=5
        )

        review_text = st.text_area(
            "Ulasan",
            placeholder="Ceritakan pengalamanmu...",
            height=150
        )

        submit_review = st.form_submit_button(
            "Kirim Ulasan",
            use_container_width=True
        )

    if submit_review:

        nickname = nickname.strip()
        review_text = review_text.strip()

        if not nickname:

            st.warning("Nama atau nickname harus diisi.")

        elif len(review_text) < 10:

            st.warning(
                "Ulasan minimal terdiri dari 10 karakter."
            )

        else:

            sentiment = predict_sentiment(review_text)

            if sentiment is None:

                st.error(
                    "Prediksi sentimen gagal. "
                    "Pastikan model dan vectorizer tersedia."
                )

            else:

                save_user_review(
                    destination=destination_name,
                    nickname=nickname,
                    rating=rating_input,
                    review=review_text,
                    sentiment=sentiment
                )

                st.success(
                    f"Ulasan berhasil ditambahkan! "
                    f"Sentimen: {sentiment}"
                )

                st.rerun()


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