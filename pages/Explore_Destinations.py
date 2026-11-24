
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import re


# ==========================================
# PAGE CONFIG
# ==========================================

st.set_page_config(
    page_title="Sentiment Analytics | WisataKP",
    page_icon="📊",
    layout="wide"
)


# ==========================================
# PATH
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

REVIEW_DIR = BASE_DIR / "data" / "processed" / "reviews"

# Kandidat file dataset hasil labeling
DATA_CANDIDATES = [
    REVIEW_DIR / "wisata_kp_reviews_sentiment.csv",
    REVIEW_DIR / "reviews_sentiment.csv",
    REVIEW_DIR / "wisata_kp_reviews_labeled.csv",
    REVIEW_DIR / "reviews_labeled.csv",
    REVIEW_DIR / "sentiment_clean.csv",
]


# ==========================================
# CUSTOM CSS
# ==========================================

st.markdown("""
<style>

.analytics-title {
    font-size: 2.1rem;
    font-weight: 800;
    margin-bottom: 0;
}

.analytics-subtitle {
    color: #8b95a7;
    font-size: 0.95rem;
    margin-bottom: 1.5rem;
}

.metric-card {
    padding: 12px 0;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# LOAD DATA
# ==========================================

@st.cache_data
def load_sentiment_data():

    data_file = next(
        (
            file
            for file in DATA_CANDIDATES
            if file.exists()
        ),
        None
    )

    # Cari file CSV sentimen secara otomatis
    if data_file is None:

        possible_files = list(
            (BASE_DIR / "data" / "processed").rglob("*sentiment*.csv")
        ) + list(
            (BASE_DIR / "data" / "processed").rglob("*labeled*.csv")
        )

        data_file = next(
            (
                file
                for file in possible_files
                if file.exists()
            ),
            None
        )

    if data_file is None:
        return None, None

    df = pd.read_csv(data_file)

    return df, data_file


# ==========================================
# NORMALIZE SENTIMENT
# ==========================================

def normalize_sentiment(value):

    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    mapping = {
        "positive": "Positif",
        "positif": "Positif",
        "1": "Positif",
        "1.0": "Positif",

        "neutral": "Netral",
        "netral": "Netral",
        "0": "Netral",
        "0.0": "Netral",

        "negative": "Negatif",
        "negatif": "Negatif",
        "-1": "Negatif",
        "-1.0": "Negatif"
    }

    return mapping.get(value)


# ==========================================
# LOAD DATA
# ==========================================

try:

    df, data_file = load_sentiment_data()

except Exception as e:

    st.error(f"Gagal membaca dataset sentimen: {e}")
    st.stop()


if df is None:

    st.warning(
        "Dataset hasil labeling sentimen belum ditemukan."
    )

    st.info(
        "Pastikan dataset hasil labeling tersedia di folder "
        "`data/processed/reviews/`."
    )

    st.stop()


# ==========================================
# IDENTIFY COLUMNS
# ==========================================

sentiment_candidates = [
    "sentiment",
    "sentiment_label",
    "label",
    "predicted_sentiment"
]

text_candidates = [
    "review_text",
    "review",
    "text",
    "preprocessed_text"
]

destination_candidates = [
    "nama_destinasi",
    "destination_name",
    "title",
    "destinasi"
]


sentiment_column = next(
    (
        col
        for col in sentiment_candidates
        if col in df.columns
    ),
    None
)

text_column = next(
    (
        col
        for col in text_candidates
        if col in df.columns
    ),
    None
)

destination_column = next(
    (
        col
        for col in destination_candidates
        if col in df.columns
    ),
    None
)


if sentiment_column is None:

    st.error(
        "Kolom label sentimen tidak ditemukan pada dataset."
    )

    st.write("Kolom yang tersedia:", df.columns.tolist())

    st.stop()


# ==========================================
# PROCESS SENTIMENT
# ==========================================

df["sentiment_display"] = df[
    sentiment_column
].apply(normalize_sentiment)


df = df.dropna(
    subset=["sentiment_display"]
).copy()


if df.empty:

    st.warning(
        "Tidak terdapat label sentimen yang valid."
    )

    st.stop()


# ==========================================
# HEADER
# ==========================================

st.markdown(
    '<div class="analytics-title">📊 Sentiment Analytics</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="analytics-subtitle">'
    'Analisis persepsi pengunjung berdasarkan ulasan '
    'destinasi wisata Kulon Progo.'
    '</div>',
    unsafe_allow_html=True
)


# ==========================================
# SUMMARY METRICS
# ==========================================

total_reviews = len(df)

sentiment_counts = df[
    "sentiment_display"
].value_counts()


positive_count = sentiment_counts.get(
    "Positif", 0
)

neutral_count = sentiment_counts.get(
    "Netral", 0
)

negative_count = sentiment_counts.get(
    "Negatif", 0
)


positive_percentage = (
    positive_count / total_reviews * 100
    if total_reviews > 0
    else 0
)

neutral_percentage = (
    neutral_count / total_reviews * 100
    if total_reviews > 0
    else 0
)

negative_percentage = (
    negative_count / total_reviews * 100
    if total_reviews > 0
    else 0
)


col1, col2, col3, col4 = st.columns(4)


with col1:

    st.metric(
        "Total Reviews",
        f"{total_reviews:,}"
    )


with col2:

    st.metric(
        "😊 Positif",
        f"{positive_count:,}",
        f"{positive_percentage:.1f}%"
    )


with col3:

    st.metric(
        "😐 Netral",
        f"{neutral_count:,}",
        f"{neutral_percentage:.1f}%"
    )


with col4:

    st.metric(
        "😞 Negatif",
        f"{negative_count:,}",
        f"{negative_percentage:.1f}%"
    )


st.divider()


# ==========================================
# SENTIMENT DISTRIBUTION
# ==========================================

st.subheader("Sentiment Distribution")

col_chart, col_summary = st.columns(
    [1.5, 1]
)


with col_chart:

    chart_data = pd.DataFrame({
        "Sentimen": [
            "Positif",
            "Netral",
            "Negatif"
        ],
        "Jumlah": [
            positive_count,
            neutral_count,
            negative_count
        ]
    })

    chart_data = chart_data.set_index(
        "Sentimen"
    )

    st.bar_chart(
        chart_data,
        y="Jumlah",
        color="#4C78A8"
    )


with col_summary:

    st.markdown("### Ringkasan Sentimen")

    st.markdown(
        f"""
        😊 **Positif**  
        {positive_percentage:.1f}% dari seluruh ulasan

        😐 **Netral**  
        {neutral_percentage:.1f}% dari seluruh ulasan

        😞 **Negatif**  
        {negative_percentage:.1f}% dari seluruh ulasan
        """
    )


st.divider()


# ==========================================
# SENTIMENT BY DESTINATION
# ==========================================

st.subheader("Sentiment by Destination")


if destination_column is not None:

    destination_sentiment = (
        df.groupby(
            [destination_column, "sentiment_display"]
        )
        .size()
        .unstack(fill_value=0)
    )

    for sentiment in [
        "Positif",
        "Netral",
        "Negatif"
    ]:

        if sentiment not in destination_sentiment.columns:
            destination_sentiment[sentiment] = 0

    destination_sentiment = destination_sentiment[
        ["Positif", "Netral", "Negatif"]
    ]

    destination_sentiment["Total Review"] = (
        destination_sentiment.sum(axis=1)
    )

    destination_sentiment = (
        destination_sentiment
        .sort_values(
            "Total Review",
            ascending=False
        )
    )

    col1, col2 = st.columns(2)


    with col1:

        st.markdown("#### Destinasi dengan Sentimen Positif Terbanyak")

        top_positive = (
            destination_sentiment
            .sort_values(
                "Positif",
                ascending=False
            )
            .head(10)
        )

        st.bar_chart(
            top_positive["Positif"],
            color="#59A14F"
        )


    with col2:

        st.markdown("#### Destinasi dengan Sentimen Negatif Terbanyak")

        top_negative = (
            destination_sentiment
            .sort_values(
                "Negatif",
                ascending=False
            )
            .head(10)
        )

        st.bar_chart(
            top_negative["Negatif"],
            color="#E15759"
        )


    # Tabel detail destinasi
    with st.expander("📋 Lihat detail sentimen setiap destinasi"):

        display_destination = (
            destination_sentiment
            .reset_index()
            .rename(
                columns={
                    destination_column: "Nama Destinasi"
                }
            )
        )

        st.dataframe(
            display_destination,
            use_container_width=True,
            hide_index=True
        )

else:

    st.info(
        "Data nama destinasi tidak tersedia, "
        "sehingga analisis per destinasi belum dapat ditampilkan."
    )


st.divider()


# ==========================================
# WORD CLOUD
# ==========================================

st.subheader("Word Cloud")

if text_column is not None:

    text_data = (
        df[text_column]
        .dropna()
        .astype(str)
    )

    combined_text = " ".join(
        text_data.tolist()
    )

    try:

        from wordcloud import WordCloud

        if combined_text.strip():

            wordcloud = WordCloud(
                width=1000,
                height=450,
                background_color="white",
                colormap="Blues",
                max_words=100,
                collocations=False
            ).generate(combined_text)

            fig, ax = plt.subplots(
                figsize=(12, 5)
            )

            ax.imshow(
                wordcloud,
                interpolation="bilinear"
            )

            ax.axis("off")

            st.pyplot(
                fig,
                use_container_width=True
            )

            plt.close(fig)

        else:

            st.info(
                "Tidak ada teks ulasan untuk Word Cloud."
            )

    except ImportError:

        st.info(
            "Library WordCloud belum terpasang. "
            "Install menggunakan `pip install wordcloud`."
        )

else:

    st.info(
        "Kolom teks ulasan tidak ditemukan."
    )


st.divider()


# ==========================================
# AUTOMATIC INSIGHT
# ==========================================

st.subheader("💡 Sentiment Insights")


if positive_percentage >= 60:

    positive_insight = (
        "Mayoritas ulasan menunjukkan pengalaman positif. "
        "Hal ini mengindikasikan pengunjung cenderung "
        "memberikan respons yang baik terhadap destinasi."
    )

elif positive_percentage >= 40:

    positive_insight = (
        "Sentimen positif menjadi salah satu sentimen dominan, "
        "tetapi masih terdapat variasi pengalaman pengunjung."
    )

else:

    positive_insight = (
        "Proporsi sentimen positif relatif rendah. "
        "Perlu ditinjau lebih lanjut faktor yang memengaruhi "
        "pengalaman pengunjung."
    )


if negative_percentage >= 20:

    negative_insight = (
        "Persentase sentimen negatif cukup tinggi. "
        "Ulasan negatif dapat ditelusuri lebih lanjut "
        "untuk mengetahui aspek yang perlu diperbaiki."
    )

else:

    negative_insight = (
        "Sentimen negatif relatif rendah dibandingkan total ulasan."
    )


if neutral_percentage >= 30:

    neutral_insight = (
        "Ulasan netral memiliki proporsi yang cukup besar, "
        "yang dapat menunjukkan pengalaman informatif atau "
        "ulasan dengan ekspresi sentimen terbatas."
    )

else:

    neutral_insight = (
        "Ulasan netral memiliki proporsi yang relatif lebih kecil."
    )


st.markdown(
    f"""
    - {positive_insight}
    - {neutral_insight}
    - {negative_insight}
    """
)


# ==========================================
# DATA INFORMATION
# ==========================================

with st.expander("ℹ️ Informasi Dataset"):

    st.write(
        f"**File dataset:** `{data_file.name}`"
    )

    st.write(
        f"**Total data dianalisis:** {len(df):,} ulasan"
    )

    st.write(
        f"**Kolom sentimen:** `{sentiment_column}`"
    )

    if text_column:

        st.write(
            f"**Kolom teks:** `{text_column}`"
        )

    if destination_column:

        st.write(
            f"**Kolom destinasi:** `{destination_column}`"
        )


# ==========================================
# FOOTER
# ==========================================

st.markdown("---")

st.caption(
    "WisataKP | Sentiment Analytics • Kulon Progo, Yogyakarta"
)
