from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import re
import base64
import html

# ============================================================
# 01. PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="WisataKP | Explore Kulon Progo",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 02. PROJECT PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MAIN_CSS_PATH = BASE_DIR / "styles" / "main.css"
DASHBOARD_CSS_PATH = BASE_DIR / "styles" / "dashboard.css"

BACKGROUND_IMAGE_PATH = (
    BASE_DIR / "assets" / "images" / "kp.png" 
)

DESTINATION_PATH = (
    BASE_DIR / "data" / "processed" / "destinasi"
    / "destinasi_clean.csv"
)

REVIEW_PATH = (
    BASE_DIR / "data" / "processed" / "reviews"
    / "wisata_kp_reviews_clean.csv"
)

LABELED_REVIEW_CANDIDATES = [
    BASE_DIR / "data" / "processed" / "reviews"
    / "wisata_kp_reviews_labeled.csv",

    BASE_DIR / "data" / "processed" / "reviews"
    / "wisata_kp_reviews_preprocessed.csv",

    BASE_DIR / "data" / "processed" / "reviews"
    / "wisata_kp_reviews_clean.csv",
]

# ============================================================
# 03. GLOBAL CSS
# ============================================================

@st.cache_data(show_spinner=False)
def encode_image(path_string):
    """Encode gambar ke base64 (di-cache supaya tidak diulang tiap rerun)."""

    return base64.b64encode(
        Path(path_string).read_bytes()
    ).decode("utf-8")


def load_global_css():

    css_files = [
        MAIN_CSS_PATH,
        DASHBOARD_CSS_PATH
    ]

    # --------------------------------------------------------
    # LOAD CSS FILES
    # --------------------------------------------------------

    for css_file in css_files:

        if css_file.exists():

            css = css_file.read_text(
                encoding="utf-8"
            )

            st.markdown(
                f"<style>{css}</style>",
                unsafe_allow_html=True
            )

    # --------------------------------------------------------
    # BACKGROUND - SAMA DENGAN HALAMAN EXPLORE DESTINATIONS
    # --------------------------------------------------------

    if BACKGROUND_IMAGE_PATH.exists():

        mime = (
            "image/png"
            if BACKGROUND_IMAGE_PATH.suffix.lower() == ".png"
            else "image/jpeg"
        )

        encoded_background = encode_image(
            str(BACKGROUND_IMAGE_PATH)
        )

        st.markdown(
            f"""
            <style>
            [data-testid="stMain"] {{
                background-image:
                    linear-gradient(
                        rgba(240, 247, 253, 0.72),
                        rgba(240, 247, 253, 0.82)
                    ),
                    url("data:{mime};base64,{encoded_background}") !important;

                background-size: cover !important;
                background-position: center !important;
                background-repeat: no-repeat !important;
                background-attachment: fixed !important;
            }}

            [data-testid="stMainBlockContainer"],
            [data-testid="stHeader"] {{
                background: transparent !important;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

    else:

        st.warning(
            "Background image tidak ditemukan. "
            "Pastikan file kp.png "
            "berada di folder assets/images/kp.png"
        )


load_global_css()

# ============================================================
# 04. HELPER FUNCTIONS
# ============================================================

def normalize_text(value):

    if pd.isna(value):
        return ""

    value = str(value).strip().lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\s]", "", value)

    return value.strip()


def normalize_column_name(column):

    column = str(column).lower().strip()
    column = re.sub(r"[^a-z0-9]", "", column)

    return column


def find_column(df, candidates):
    """
    Mencari nama kolom berdasarkan beberapa kemungkinan nama.
    """

    if df is None or df.empty:
        return None

    normalized_columns = {
        normalize_column_name(col): col
        for col in df.columns
    }

    # Exact match
    for candidate in candidates:

        normalized_candidate = normalize_column_name(
            candidate
        )

        if normalized_candidate in normalized_columns:

            return normalized_columns[
                normalized_candidate
            ]

    # Partial match
    for candidate in candidates:

        normalized_candidate = normalize_column_name(
            candidate
        )

        for normalized_col, original_col in (
            normalized_columns.items()
        ):

            if normalized_candidate in normalized_col:

                return original_col

    return None


def read_csv_safe(path):
    """
    Membaca CSV secara aman dengan beberapa encoding.
    """

    if not path.exists():
        return pd.DataFrame()

    encodings = [
        "utf-8",
        "utf-8-sig",
        "latin1"
    ]

    for encoding in encodings:

        try:

            return pd.read_csv(
                path,
                encoding=encoding
            )

        except Exception:

            continue

    return pd.DataFrame()


def format_number(number):

    try:

        return f"{int(number):,}".replace(",", ".")

    except Exception:

        return "0"


def normalize_sentiment(value):
    """
    Menyamakan berbagai label sentimen.
    """

    if pd.isna(value):
        return None

    value = str(value).lower().strip()

    positive_labels = [
        "positive", "positif", "pos", "1",
        "sentiment_positive", "sentimen positif"
    ]

    neutral_labels = [
        "neutral", "netral", "neu", "0",
        "sentiment_neutral", "sentimen netral"
    ]

    negative_labels = [
        "negative", "negatif", "neg", "-1",
        "sentiment_negative", "sentimen negatif"
    ]

    if value in positive_labels:
        return "Positif"

    if value in neutral_labels:
        return "Netral"

    if value in negative_labels:
        return "Negatif"

    if "posit" in value or "positive" in value:
        return "Positif"

    if "netral" in value or "neutral" in value:
        return "Netral"

    if "negat" in value or "negative" in value:
        return "Negatif"

    return None


# ============================================================
# 05. LOAD DATA
# ============================================================

@st.cache_data
def load_datasets():

    destination_df = read_csv_safe(
        DESTINATION_PATH
    )

    review_df = read_csv_safe(
        REVIEW_PATH
    )

    sentiment_df = pd.DataFrame()

    for path in LABELED_REVIEW_CANDIDATES:

        candidate_df = read_csv_safe(path)

        if candidate_df.empty:
            continue

        sentiment_column = find_column(
            candidate_df,
            [
                "sentiment",
                "sentimen",
                "label_sentiment",
                "sentiment_label",
                "label",
                "kelas_sentimen",
                "sentiment_class"
            ]
        )

        if sentiment_column is not None:

            sentiment_df = candidate_df.copy()
            break

    return (
        destination_df,
        review_df,
        sentiment_df
    )


destination_raw, review_raw, sentiment_raw = (
    load_datasets()
)

# ============================================================
# 06. DETECT COLUMNS
# ============================================================

DESTINATION_NAME_COL = find_column(
    destination_raw,
    [
        "nama_destinasi",
        "nama wisata",
        "nama_tempat",
        "destination_name",
        "destinasi",
        "nama",
        "name",
        "title"
    ]
)

REVIEW_DESTINATION_COL = find_column(
    review_raw,
    [
        "nama_destinasi",
        "destinasi",
        "nama wisata",
        "destination_name",
        "destination",
        "place_name",
        "wisata",
        "name"
    ]
)

SENTIMENT_COL = find_column(
    sentiment_raw,
    [
        "sentiment",
        "sentimen",
        "label_sentiment",
        "sentiment_label",
        "label",
        "kelas_sentimen",
        "sentiment_class"
    ]
)

# ============================================================
# 07. PREPARE DESTINATION DATA
# ============================================================

destinations = destination_raw.copy()

if DESTINATION_NAME_COL is not None:

    destinations[DESTINATION_NAME_COL] = (
        destinations[DESTINATION_NAME_COL]
        .astype(str)
        .str.strip()
    )

    destinations = destinations[
        destinations[DESTINATION_NAME_COL].notna()
        & (
            destinations[DESTINATION_NAME_COL]
            != ""
        )
        & (
            destinations[DESTINATION_NAME_COL]
            .str.lower() != "nan"
        )
    ]

    destinations = destinations.drop_duplicates(
        subset=[DESTINATION_NAME_COL]
    )

else:

    destinations = pd.DataFrame()

# ============================================================
# 08. PREPARE REVIEW DATA
# ============================================================

reviews = review_raw.copy()

if REVIEW_DESTINATION_COL is not None:

    reviews[REVIEW_DESTINATION_COL] = (
        reviews[REVIEW_DESTINATION_COL]
        .astype(str)
        .str.strip()
    )

    reviews = reviews[
        reviews[REVIEW_DESTINATION_COL].notna()
        & (
            reviews[REVIEW_DESTINATION_COL]
            != ""
        )
        & (
            reviews[REVIEW_DESTINATION_COL]
            .str.lower() != "nan"
        )
    ]

    reviews["_destination_normalized"] = (
        reviews[REVIEW_DESTINATION_COL]
        .apply(normalize_text)
    )

else:

    reviews["_destination_normalized"] = ""

# ============================================================
# 09. KPI DATA
# ============================================================

total_destinations = len(destinations)

total_reviews = len(review_raw)

# ============================================================
# 10. TOP 3 DESTINATIONS - RATING + REVIEW COUNT
# ============================================================

rating_col = find_column(
    destinations,
    [
        "totalScore",
        "rating",
        "average_rating",
        "avg_rating",
        "rating_google",
        "rating_destinasi",
        "nilai_rating",
        "score",
        "stars"
    ]
)

review_count_col = find_column(
    destinations,
    [
        "reviewsCount",
        "review_count",
        "reviews_count",
        "jumlah_review",
        "jumlah_ulasan",
        "total_review",
        "total_reviews"
    ]
)

top_rating = pd.DataFrame()

if (
    not destinations.empty
    and DESTINATION_NAME_COL is not None
    and rating_col is not None
    and review_count_col is not None
):

    top_rating = destinations.copy()

    # Konversi rating ke numerik
    top_rating[rating_col] = pd.to_numeric(
        top_rating[rating_col],
        errors="coerce"
    )

    # Konversi jumlah review ke numerik
    top_rating[review_count_col] = pd.to_numeric(
        top_rating[review_count_col],
        errors="coerce"
    ).fillna(0)

    # Hapus rating tidak valid
    top_rating = top_rating.dropna(
        subset=[rating_col]
    )

    top_rating = top_rating[
        top_rating[rating_col] > 0
    ]

    # Ranking:
    # 1. Rating tertinggi
    # 2. Jumlah review terbanyak jika rating sama
    top_rating = (
        top_rating
        .sort_values(
            by=[
                rating_col,
                review_count_col
            ],
            ascending=[
                False,
                False
            ],
            kind="stable"
        )
        .head(3)
        .reset_index(drop=True)
    )

    top_rating["ranking"] = range(
        1,
        len(top_rating) + 1
    )

else:

    top_rating = pd.DataFrame()
# ============================================================
# 11. SENTIMENT DATA
# ============================================================

sentiment_counts = {
    "Positif": 0,
    "Netral": 0,
    "Negatif": 0
}

sentiment_percentages = {
    "Positif": 0,
    "Netral": 0,
    "Negatif": 0
}

if (
    not sentiment_raw.empty
    and SENTIMENT_COL is not None
):

    sentiment_data = sentiment_raw.copy()

    sentiment_data["_sentiment_normalized"] = (
        sentiment_data[SENTIMENT_COL]
        .apply(normalize_sentiment)
    )

    sentiment_data = sentiment_data[
        sentiment_data["_sentiment_normalized"].isin(
            [
                "Positif",
                "Netral",
                "Negatif"
            ]
        )
    ]

    sentiment_counts = (
        sentiment_data["_sentiment_normalized"]
        .value_counts()
        .reindex(
            [
                "Positif",
                "Netral",
                "Negatif"
            ],
            fill_value=0
        )
        .to_dict()
    )

    total_labeled_sentiment = sum(
        sentiment_counts.values()
    )

    if total_labeled_sentiment > 0:

        sentiment_percentages = {
            label: (
                count / total_labeled_sentiment
            ) * 100

            for label, count in (
                sentiment_counts.items()
            )
        }

# ============================================================
# 12. DASHBOARD HEADER
# ============================================================

def section_header(title, caption=""):
    """Judul section + garis tipis (menggantikan st.divider)."""

    st.html(
        f"""
        <div class="dash-section">
            <div class="dash-section-title">{html.escape(title)}</div>
            <div class="dash-section-caption">{html.escape(caption)}</div>
        </div>
        """
    )


st.html(
    """
    <div class="dash-hero">
        <div class="dash-eyebrow">DISCOVER · EXPLORE · EXPERIENCE</div>
        <div class="dash-title">EXPLORE KULON PROGO</div>
        <div class="dash-subtitle">
            Discover tourism destinations and visitor insights
            across Kulon Progo.
        </div>
    </div>
    """
)

# ============================================================
# 13. KPI SUMMARY
# ============================================================

section_header(
    "KPI Summary",
    "Ringkasan data destinasi dan ulasan pengunjung."
)

kpi_col1, kpi_col2 = st.columns(2, gap="medium")

kpi_html_1 = f"""
<div class="kpi-card kpi-destination">

    <div class="kpi-icon">📍</div>

    <div class="kpi-body">

        <div class="kpi-label">
            Total Destinasi
        </div>

        <div class="kpi-value">
            {format_number(total_destinations)}
        </div>

        <div class="kpi-description">
            Destinasi wisata yang terdaftar di Kulon Progo
        </div>

    </div>

</div>
"""

kpi_html_2 = f"""
<div class="kpi-card kpi-review">

    <div class="kpi-icon">💬</div>

    <div class="kpi-body">

        <div class="kpi-label">
            Total Ulasan
        </div>

        <div class="kpi-value">
            {format_number(total_reviews)}
        </div>

        <div class="kpi-description">
            Ulasan pengunjung yang terkumpul dalam dataset
        </div>

    </div>

</div>
"""

with kpi_col1:
    st.html(kpi_html_1)

with kpi_col2:
    st.html(kpi_html_2)

# ============================================================
# 14. TOP 3 HIGHEST RATED DESTINATIONS
# ============================================================

section_header(
    "Top 3 Highest Rated Destinations",
    "Peringkat berdasarkan rating tertinggi dan jumlah "
    "ulasan sebagai penentu jika rating sama."
)

# ------------------------------------------------------------
# CREATE CARD
# ------------------------------------------------------------

def create_rating_card(row, rank):

    name = html.escape(
        str(row[DESTINATION_NAME_COL])
    )

    rating = float(row[rating_col])

    review_count = int(
        row[review_count_col]
    )

    if rank == 1:

        medal = "🏆"
        rank_label = "Peringkat 1"
        card_class = "rank-1"

        badge = """
        <div class="rating-badge">
            Top Rated
        </div>
        """

    elif rank == 2:

        medal = "🥈"
        rank_label = "Peringkat 2"
        card_class = "rank-2"
        badge = ""

    else:

        medal = "🥉"
        rank_label = "Peringkat 3"
        card_class = "rank-3"
        badge = ""

    return f"""
    <div class="rating-card {card_class}">

        <div class="rating-medal">
            {medal}
        </div>

        <div class="rating-rank">
            {rank_label}
        </div>

        <div class="rating-name">
            {name}
        </div>

        <div class="rating-score">
            <span class="rating-star">★</span>
            {rating:.2f}
        </div>

        <div class="rating-caption">
            Destination Rating
        </div>

        <div class="rating-review-count">
            💬 {review_count:,} Reviews
        </div>

        {badge}

    </div>
    """


# ------------------------------------------------------------
# DISPLAY TOP 3
# URUTAN TAMPIL: RANK 2 - RANK 1 - RANK 3 (podium)
# ------------------------------------------------------------

if not top_rating.empty:

    if len(top_rating) >= 3:
        podium_order = [1, 0, 2]

    elif len(top_rating) == 2:
        podium_order = [1, 0]

    else:
        podium_order = [0]

    podium_cards = "".join(
        create_rating_card(top_rating.iloc[index], index + 1)
        for index in podium_order
    )

    st.html(
        f"""
        <div class="podium podium-{len(podium_order)}">
            {podium_cards}
        </div>
        """
    )

else:

    st.warning(
        "Ranking belum dapat ditampilkan. "
        "Pastikan dataset destinasi memiliki kolom rating "
        "dan jumlah review."
    )

# ============================================================
# 15. SENTIMENT INSIGHT
# ============================================================

section_header(
    "Sentiment Insight",
    "Ringkasan hasil analisis sentimen ulasan pengunjung."
)

if not sentiment_raw.empty and SENTIMENT_COL is not None:

    sentiment_config = {
        "Positif": {
            "icon": "😊",
            "class_name": "positive",
        },
        "Netral": {
            "icon": "😐",
            "class_name": "neutral",
        },
        "Negatif": {
            "icon": "☹️",
            "class_name": "negative",
        },
    }

    sentiment_html = """
    <div class="sentiment-wrapper">
    """

    for sentiment in ["Positif", "Netral", "Negatif"]:

        config = sentiment_config[sentiment]
        count = sentiment_counts[sentiment]
        percentage = sentiment_percentages[sentiment]

        sentiment_html += f"""
        <div class="sentiment-item {config['class_name']}">

            <div class="sentiment-item-top">
                <div class="sentiment-emoji">
                    {config['icon']}
                </div>

                <div class="sentiment-name">
                    {sentiment}
                </div>
            </div>

            <div class="sentiment-data">

                <div class="sentiment-total">
                    {format_number(count)}
                </div>

                <div class="sentiment-caption">
                    Jumlah ulasan
                </div>

            </div>

            <div class="sentiment-meter">
                <span style="width: {percentage:.1f}%"></span>
            </div>

            <div class="sentiment-stat">
                <div class="sentiment-stat-value">
                    {percentage:.1f}%
                </div>

                <div class="sentiment-stat-label">
                    dari data berlabel
                </div>
            </div>

        </div>
        """

    sentiment_html += "</div>"

    st.html(sentiment_html)

else:

    st.info(
        "Dataset sentimen belum ditemukan atau kolom sentimen "
        "belum terdeteksi."
    )


# ============================================================
# 16. FOOTER
# ============================================================

st.html(
    """
    <div class="dash-footer">
        Powered by WisataKP · Explore more, travel better
    </div>
    """
)