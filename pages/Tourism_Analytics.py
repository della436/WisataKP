
import streamlit as st
import pandas as pd
import folium
import html

from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from pathlib import Path


# ==========================================
# PAGE CONFIG
# ==========================================

st.set_page_config(
    page_title="Tourism Map | WisataKP",
    page_icon="🗺️",
    layout="wide"
)


# ==========================================
# PATH
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "destinasi"
    / "destinasi_clean.csv"
)


# ==========================================
# CUSTOM CSS
# ==========================================

st.markdown("""
<style>

.map-title {
    font-size: 2.1rem;
    font-weight: 800;
    margin-bottom: 0;
}

.map-subtitle {
    color: #8b95a7;
    font-size: 0.95rem;
    margin-bottom: 1.5rem;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# KATEGORI SINGKAT
# ==========================================

CATEGORY_MAPPING = {
    "Pantai": "🏖️ Pantai",
    "Wisata Air": "💧 Wisata Air",
    "Alam": "🌿 Alam",
    "Desa & Budaya": "🏘️ Desa & Budaya",
    "Taman & Kebun": "🌳 Taman & Kebun",
    "Kuliner": "☕ Kuliner",
    "Panorama": "📸 Panorama",
    "Lainnya": "📍 Lainnya"
}


CATEGORY_ORDER = list(CATEGORY_MAPPING.values())


def categorize_destination(row):
    """
    Mengelompokkan kategori wisata menjadi 8 kategori singkat.
    Menggunakan categoryName, title, dan address.
    """

    category = str(row.get("categoryName", "")).lower()
    title = str(row.get("title", "")).lower()
    address = str(row.get("address", "")).lower()

    text = f"{category} {title} {address}"

    # ------------------------------
    # PANTAI
    # ------------------------------

    beach_keywords = [
        "pantai",
        "beach",
        "pesisir",
        "laguna"
    ]

    if any(keyword in text for keyword in beach_keywords):
        return CATEGORY_MAPPING["Pantai"]

    # ------------------------------
    # WISATA AIR
    # ------------------------------

    water_keywords = [
        "air terjun",
        "waterfall",
        "curug",
        "river",
        "sungai",
        "waduk",
        "embung",
        "bendungan",
        "kolam renang",
        "waterpark",
        "pemandian",
        "water park",
        "wisata air",
        "rafting",
        "arung jeram",
        "danau",
        "lake"
    ]

    if any(keyword in text for keyword in water_keywords):
        return CATEGORY_MAPPING["Wisata Air"]

    # ------------------------------
    # KULINER
    # ------------------------------

    culinary_keywords = [
        "restaurant",
        "restoran",
        "rumah makan",
        "warung",
        "cafe",
        "café",
        "coffee",
        "kopi",
        "bakery",
        "food",
        "kuliner",
        "makan",
        "seafood",
        "mie",
        "mi ",
        "bakso",
        "sate",
        "ayam",
        "pizza",
        "burger",
        "dessert",
        "ice cream",
        "es krim"
    ]

    if any(keyword in text for keyword in culinary_keywords):
        return CATEGORY_MAPPING["Kuliner"]

    # ------------------------------
    # DESA & BUDAYA
    # ------------------------------

    culture_keywords = [
        "desa wisata",
        "kampung wisata",
        "desa budaya",
        "kampung budaya",
        "kebudayaan",
        "budaya",
        "tradisional",
        "museum",
        "kerajinan",
        "craft",
        "batik",
        "wayang",
        "tari",
        "seni",
        "art",
        "heritage",
        "sejarah",
        "historical",
        "candi",
        "monumen",
        "makam",
        "religi",
        "masjid",
        "gereja",
        "vihara",
        "pura"
    ]

    if any(keyword in text for keyword in culture_keywords):
        return CATEGORY_MAPPING["Desa & Budaya"]

    # ------------------------------
    # TAMAN & KEBUN
    # ------------------------------

    garden_keywords = [
        "taman",
        "park",
        "garden",
        "kebun",
        "perkebunan",
        "agrowisata",
        "agriculture",
        "hortikultura",
        "flower",
        "bunga",
        "hutan wisata",
        "arboretum",
        "greenhouse"
    ]

    if any(keyword in text for keyword in garden_keywords):
        return CATEGORY_MAPPING["Taman & Kebun"]

    # ------------------------------
    # PANORAMA
    # ------------------------------

    panorama_keywords = [
        "panorama",
        "view",
        "viewpoint",
        "spot foto",
        "spot photography",
        "sunset",
        "sunrise",
        "healing",
        "instagramable",
        "pemandangan",
        "landscape",
        "sky",
        "sky view",
        "bukit",
        "hill",
        "terasering",
        "balon udara"
    ]

    if any(keyword in text for keyword in panorama_keywords):
        return CATEGORY_MAPPING["Panorama"]

    # ------------------------------
    # ALAM
    # ------------------------------

    nature_keywords = [
        "alam",
        "nature",
        "natural",
        "gunung",
        "mountain",
        "goa",
        "gua",
        "cave",
        "geopark",
        "geologi",
        "geological",
        "hutan",
        "forest",
        "flora",
        "fauna",
        "wildlife",
        "resort alam",
        "eco",
        "ekowisata",
        "glamping"
    ]

    if any(keyword in text for keyword in nature_keywords):
        return CATEGORY_MAPPING["Alam"]

    # ------------------------------
    # LAINNYA
    # ------------------------------

    return CATEGORY_MAPPING["Lainnya"]


# ==========================================
# LOAD DATA
# ==========================================

@st.cache_data
def load_destination_data():

    # Cek file dataset
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset tidak ditemukan:\n{DATA_FILE}"
        )

    df = pd.read_csv(DATA_FILE)

    # Validasi kolom
    required_columns = [
        "title",
        "latitude",
        "longitude"
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom dataset tidak lengkap: {missing_columns}"
        )

    # ======================================
    # KOORDINAT
    # ======================================

    df["latitude"] = pd.to_numeric(
        df["latitude"],
        errors="coerce"
    )

    df["longitude"] = pd.to_numeric(
        df["longitude"],
        errors="coerce"
    )

    # Hapus koordinat kosong
    df = df.dropna(
        subset=["latitude", "longitude"]
    ).copy()

    # Validasi koordinat
    df = df[
        df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
    ].copy()

    # ======================================
    # KATEGORI WISATA SINGKAT
    # ======================================

    df["jenis_wisata"] = df.apply(
        categorize_destination,
        axis=1
    )

    # ======================================
    # RATING
    # ======================================

    if "totalScore" in df.columns:

        df["totalScore"] = pd.to_numeric(
            df["totalScore"],
            errors="coerce"
        )

    # ======================================
    # JUMLAH REVIEW
    # ======================================

    if "reviewsCount" in df.columns:

        df["reviewsCount"] = pd.to_numeric(
            df["reviewsCount"],
            errors="coerce"
        )

    return df


# ==========================================
# LOAD DATA + DIAGNOSTIC
# ==========================================

try:

    df = load_destination_data()

except Exception as e:

    st.error(f"Gagal membaca dataset: {e}")

    st.code(str(DATA_FILE))

    st.stop()


if df.empty:

    st.warning(
        "Dataset berhasil dibaca, tetapi tidak ada "
        "destinasi dengan koordinat valid."
    )

    st.write("Lokasi dataset:", str(DATA_FILE))

    st.stop()


# ==========================================
# HEADER
# ==========================================

st.markdown(
    '<div class="map-title">🗺️ Tourism Map</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="map-subtitle">'
    'Explore persebaran destinasi wisata di Kulon Progo '
    'berdasarkan lokasi geografis.'
    '</div>',
    unsafe_allow_html=True
)


# ==========================================
# SUMMARY
# ==========================================

total_destination = len(df)

total_category = df["jenis_wisata"].nunique()

total_location = df[
    ["latitude", "longitude"]
].drop_duplicates().shape[0]


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        label="Total Destinasi",
        value=total_destination
    )


with col2:

    st.metric(
        label="Kategori Wisata",
        value=total_category
    )


with col3:

    st.metric(
        label="Lokasi Terpetakan",
        value=total_location
    )


st.divider()


# ==========================================
# FILTER
# ==========================================

st.subheader("Explore Destinations")

col_filter, col_info = st.columns([2, 1])


with col_filter:

    categories = [
        category
        for category in CATEGORY_ORDER
        if category in df["jenis_wisata"].unique()
    ]

    selected_categories = st.multiselect(
        "Filter kategori wisata",
        options=categories,
        default=categories,
        key="map_category_filter"
    )


with col_info:

    st.markdown(
        "Pilih kategori untuk menampilkan "
        "destinasi tertentu pada peta."
    )


# ==========================================
# FILTER DATA
# ==========================================

filtered_df = df[
    df["jenis_wisata"].isin(selected_categories)
].copy()


st.caption(
    f"Menampilkan **{len(filtered_df)} destinasi** "
    f"dari total **{len(df)} destinasi**."
)


# ==========================================
# MAP CENTER
# ==========================================

if not filtered_df.empty:

    center_lat = filtered_df["latitude"].mean()
    center_lon = filtered_df["longitude"].mean()

else:

    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()


# ==========================================
# CREATE MAP
# ==========================================

m = folium.Map(
    location=[
        center_lat,
        center_lon
    ],
    zoom_start=11,
    tiles="OpenStreetMap",
    control_scale=True
)


# ==========================================
# MARKER CLUSTER
# ==========================================

marker_cluster = MarkerCluster().add_to(m)


# ==========================================
# MARKER DESTINATIONS
# ==========================================

for _, row in filtered_df.iterrows():

    title = html.escape(
        str(row["title"])
    )

    category = html.escape(
        str(row.get("jenis_wisata", "📍 Lainnya"))
    )

    latitude = row["latitude"]
    longitude = row["longitude"]

    # ======================================
    # RATING
    # ======================================

    rating = row.get(
        "totalScore",
        None
    )

    if pd.notna(rating):

        rating_html = f"""
        <div style="margin-top:8px;">
            ⭐ <b>{rating:.1f}</b> / 5
        </div>
        """

    else:

        rating_html = """
        <div style="margin-top:8px; color:#888;">
            Rating belum tersedia
        </div>
        """

    # ======================================
    # JUMLAH REVIEW
    # ======================================

    review_count = row.get(
        "reviewsCount",
        None
    )

    if pd.notna(review_count):

        review_html = f"""
        <div style="
            font-size:12px;
            color:#777;
            margin-top:4px;
        ">
            💬 {int(review_count):,} ulasan
        </div>
        """

    else:

        review_html = ""

    # ======================================
    # ADDRESS
    # ======================================

    address = row.get(
        "address",
        "Alamat tidak tersedia"
    )

    if pd.isna(address) or str(address).strip() == "":

        address = "Alamat tidak tersedia"

    address = html.escape(
        str(address)
    )

    # ======================================
    # POPUP
    # ======================================

    popup_html = f"""
    <div style="
        width:220px;
        font-family:Arial,sans-serif;
        padding:8px;
    ">

        <h4 style="
            color:#17365d;
            margin-top:5px;
            margin-bottom:10px;
            font-size:15px;
        ">
            {title}
        </h4>

        <div style="
            background:#e8f1fb;
            color:#17365d;
            padding:5px 10px;
            border-radius:8px;
            display:inline-block;
            font-size:12px;
        ">
            {category}
        </div>

        {rating_html}

        {review_html}

        <div style="
            font-size:12px;
            color:#777;
            margin-top:10px;
            line-height:1.5;
        ">
            📍 {address}
        </div>

    </div>
    """

    popup = folium.Popup(
        popup_html,
        max_width=320
    )

    # ======================================
    # MARKER
    # ======================================

    folium.Marker(
        location=[
            latitude,
            longitude
        ],
        tooltip=title,
        popup=popup,
        icon=folium.Icon(
            color="blue",
            icon="info-sign"
        )
    ).add_to(marker_cluster)


# ==========================================
# MAP DISPLAY
# ==========================================

if filtered_df.empty:

    st.warning(
        "Tidak ada destinasi yang sesuai dengan filter."
    )

else:

    st_folium(
        m,
        width=None,
        height=620,
        returned_objects=[],
        key="tourism_map"
    )


# ==========================================
# DESTINATION TABLE
# ==========================================

with st.expander("📋 Lihat daftar destinasi yang tampil"):

    display_columns = [
        "title",
        "jenis_wisata",
        "latitude",
        "longitude"
    ]

    optional_columns = [
        "totalScore",
        "reviewsCount",
        "address"
    ]

    for column in optional_columns:

        if column in filtered_df.columns:
            display_columns.append(column)

    display_df = filtered_df[
        display_columns
    ].reset_index(drop=True)

    # Rename kolom agar lebih mudah dibaca
    display_df = display_df.rename(
        columns={
            "title": "Nama Destinasi",
            "jenis_wisata": "Kategori",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "totalScore": "Rating",
            "reviewsCount": "Jumlah Review",
            "address": "Alamat"
        }
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )


# ==========================================
# FOOTER
# ==========================================

st.markdown("---")

st.caption(
    "WisataKP | Tourism Map • Kulon Progo, Yogyakarta"
)
