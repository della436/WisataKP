# ============================================================
# WISATAKP - DASHBOARD
# KPI SUMMARY | REVIEW DISTRIBUTION | SENTIMENT INSIGHT
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import re
from pathlib import Path

# ============================================================
# 01. PAGE CONFIG & PROJECT PATH
# ============================================================

st.set_page_config(
    page_title="WisataKP | Explore Kulon Progo",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)


def find_project_root():
    current_path = Path(__file__).resolve().parent

    for path in [current_path, *current_path.parents]:
        if (
            (path / "data" / "processed" / "destinasi").exists()
            and (path / "assets" / "css").exists()
        ):
            return path

    return current_path.parent


BASE_DIR = find_project_root()

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
# 02. CSS
# ============================================================
from pathlib import Path
import streamlit as st

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
# 03. HELPER FUNCTIONS
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
        normalized_candidate = normalize_column_name(candidate)

        if normalized_candidate in normalized_columns:
            return normalized_columns[normalized_candidate]

    # Partial match
    for candidate in candidates:
        normalized_candidate = normalize_column_name(candidate)

        for normalized_col, original_col in normalized_columns.items():
            if normalized_candidate in normalized_col:
                return original_col

    return None


def read_csv_safe(path):
    """
    Membaca CSV secara aman dengan beberapa encoding.
    """
    if not path.exists():
        return pd.DataFrame()

    encodings = ["utf-8", "utf-8-sig", "latin1"]

    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding)
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
# 04. LOAD DATA
# ============================================================

@st.cache_data
def load_datasets():

    destination_df = read_csv_safe(DESTINATION_PATH)
    review_df = read_csv_safe(REVIEW_PATH)

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

    return destination_df, review_df, sentiment_df


destination_raw, review_raw, sentiment_raw = load_datasets()

# ============================================================
# 05. DETECT COLUMNS
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
# 06. PREPARE DESTINATION DATA
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
        & (destinations[DESTINATION_NAME_COL] != "")
        & (destinations[DESTINATION_NAME_COL].str.lower() != "nan")
    ]

    destinations = destinations.drop_duplicates(
        subset=[DESTINATION_NAME_COL]
    )

else:
    destinations = pd.DataFrame()


# ============================================================
# 07. PREPARE REVIEW DATA
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
        & (reviews[REVIEW_DESTINATION_COL] != "")
        & (reviews[REVIEW_DESTINATION_COL].str.lower() != "nan")
    ]

    reviews["_destination_normalized"] = (
        reviews[REVIEW_DESTINATION_COL]
        .apply(normalize_text)
    )

else:
    reviews["_destination_normalized"] = ""


# ============================================================
# 08. KPI DATA
# ============================================================

total_destinations = len(destinations)

total_reviews = len(review_raw)

# ============================================================
# 09. REVIEW DISTRIBUTION - TOP 5 MOST REVIEWED DESTINATIONS
# ============================================================

review_counts = pd.DataFrame()

if (
    not reviews.empty
    and REVIEW_DESTINATION_COL is not None
):

    review_counts = (
        reviews.groupby(REVIEW_DESTINATION_COL)
        .size()
        .reset_index(name="jumlah_review")
    )

    review_counts = review_counts[
        review_counts["jumlah_review"] > 0
    ]

    review_counts = (
        review_counts
        .sort_values("jumlah_review", ascending=False)
        .head(5)
        .reset_index(drop=True)
    )

    review_counts["ranking"] = range(1, len(review_counts) + 1)

    review_counts["label_destinasi"] = (
        review_counts["ranking"].astype(str)
        + ". "
        + review_counts[REVIEW_DESTINATION_COL].astype(str)
    )

# ============================================================
# 10. SENTIMENT DATA
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
            ["Positif", "Netral", "Negatif"]
        )
    ]

    sentiment_counts = (
        sentiment_data["_sentiment_normalized"]
        .value_counts()
        .reindex(
            ["Positif", "Netral", "Negatif"],
            fill_value=0
        )
        .to_dict()
    )

    total_labeled_sentiment = sum(sentiment_counts.values())

    if total_labeled_sentiment > 0:

        sentiment_percentages = {
            label: (count / total_labeled_sentiment) * 100
            for label, count in sentiment_counts.items()
        }


# ============================================================
# 11. HEADER
# ============================================================

st.markdown("### Explore Kulon Progo")

st.caption(
    "Discover tourism destinations and visitor insights across Kulon Progo."
)

st.divider()


# ============================================================
# 12. KPI SUMMARY
# ============================================================

st.markdown("## 01 KPI Summary")

st.caption(
    "Ringkasan data destinasi dan ulasan pengunjung."
)

kpi_col1, kpi_col2 = st.columns(2, gap="medium")

with kpi_col1:

    with st.container(border=True, key="kpi-blue"):

        st.metric(
            label="🌿 Total Destinasi",
            value=format_number(total_destinations)
        )

        st.caption("Destinasi wisata terdaftar")


with kpi_col2:

    with st.container(border=True, key="kpi-green"):

        st.metric(
            label="💬 Total Review",
            value=format_number(total_reviews)
        )

        st.caption("Total ulasan pengunjung")


st.divider()


# ============================================================
# 13. TOP 5 MOST REVIEWED DESTINATIONS
# ============================================================

st.markdown("## 02 Top 5 Most Reviewed Destinations")

st.caption(
    "Destinasi wisata dengan jumlah ulasan pengunjung terbanyak."
)

if not review_counts.empty:

    bars = (
        alt.Chart(review_counts)
        .mark_bar(
            color="#7298CE",
            cornerRadiusEnd=6,
            height=22
        )
        .encode(
            x=alt.X(
                "jumlah_review:Q",
                title="Jumlah Review",
                scale=alt.Scale(
                    domain=[
                        0,
                        review_counts["jumlah_review"].max() * 1.15
                    ]
                ),
                axis=alt.Axis(
                    grid=True,
                    gridColor="#E8EDF4",
                    tickColor="#DCE3EC"
                )
            ),
            y=alt.Y(
                "label_destinasi:N",
                sort="-x",
                title=None,
                axis=alt.Axis(
                    labelFontSize=13,
                    labelColor="#344256",
                    ticks=False,
                    domain=False
                )
            ),
            tooltip=[
                alt.Tooltip(
                    "ranking:Q",
                    title="Ranking"
                ),
                alt.Tooltip(
                    f"{REVIEW_DESTINATION_COL}:N",
                    title="Destinasi"
                ),
                alt.Tooltip(
                    "jumlah_review:Q",
                    title="Jumlah Review"
                )
            ]
        )
    )

    labels = (
        alt.Chart(review_counts)
        .mark_text(
            align="left",
            baseline="middle",
            dx=6,
            fontSize=12,
            fontWeight="bold",
            color="#40516A"
        )
        .encode(
            x=alt.X("jumlah_review:Q"),
            y=alt.Y(
                "label_destinasi:N",
                sort="-x"
            ),
            text=alt.Text("jumlah_review:Q")
        )
    )

    top5_chart = (
        (bars + labels)
        .properties(
            height=280
        )
    )

    st.altair_chart(
        top5_chart,
        use_container_width=True
    )

else:

    st.info(
        "Data review destinasi belum tersedia "
        "atau kolom destinasi belum terdeteksi."
    )

st.divider()

# ============================================================
# 14. SENTIMENT INSIGHT
# ============================================================

st.markdown("## 03 Sentiment Insight")

st.caption(
    "Ringkasan hasil analisis sentimen review pengunjung."
)


if (
    not sentiment_raw.empty
    and SENTIMENT_COL is not None
):

    sentiment_col1, sentiment_col2, sentiment_col3 = st.columns(
        3,
        gap="medium"
    )

    # POSITIF
    with sentiment_col1:

        with st.container(border=True, key="sentiment-positive"):

            st.markdown("**🟢 Positif**")

            st.metric(
                label="Jumlah Review",
                value=format_number(sentiment_counts["Positif"])
            )

            st.caption(
                f"{sentiment_percentages['Positif']:.1f}% "
                "dari data berlabel"
            )


    # NETRAL
    with sentiment_col2:

        with st.container(border=True, key="sentiment-neutral"):

            st.markdown("**🟡 Netral**")

            st.metric(
                label="Jumlah Review",
                value=format_number(sentiment_counts["Netral"])
            )

            st.caption(
                f"{sentiment_percentages['Netral']:.1f}% "
                "dari data berlabel"
            )


    # NEGATIF
    with sentiment_col3:

        with st.container(border=True, key="sentiment-negative"):

            st.markdown("**🔴 Negatif**")

            st.metric(
                label="Jumlah Review",
                value=format_number(sentiment_counts["Negatif"])
            )

            st.caption(
                f"{sentiment_percentages['Negatif']:.1f}% "
                "dari data berlabel"
            )

else:

    st.info(
        "Dataset sentimen belum ditemukan atau kolom sentimen "
        "belum terdeteksi. Dashboard tetap menampilkan KPI "
        "dan Review Distribution."
    )


# ============================================================
# 15. FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "WisataKP · Explore Kulon Progo"
)