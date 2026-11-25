
# ============================================================
# WISATAKP - WISABOT
# Rule-Based Tourism Chatbot
# ============================================================

import streamlit as st
import pandas as pd
import random
import re

from pathlib import Path
from difflib import SequenceMatcher


# ============================================================
# 1. PAGE CONFIG
# ============================================================

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
# 2. PATH DATA
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DESTINATION_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "destinasi"
    / "destinasi_clean.csv"
)


# ============================================================
# 3. LOAD DATA
# ============================================================

@st.cache_data
def load_destinations():

    if not DESTINATION_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(DESTINATION_FILE)

    required_columns = [
        "title",
        "categoryName",
        "address",
        "totalScore",
        "reviewsCount",
        "latitude",
        "longitude"
    ]

    for column in required_columns:
        if column not in df.columns:
            df[column] = None

    df["title"] = df["title"].fillna("").astype(str)
    df["categoryName"] = df["categoryName"].fillna("").astype(str)
    df["address"] = df["address"].fillna("").astype(str)

    df["totalScore"] = pd.to_numeric(
        df["totalScore"],
        errors="coerce"
    )

    df["reviewsCount"] = pd.to_numeric(
        df["reviewsCount"],
        errors="coerce"
    ).fillna(0)

    return df


destinations = load_destinations()


# ============================================================
# 4. SESSION STATE
# ============================================================

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None


# ============================================================
# 5. HEADER
# ============================================================

header_col1, header_col2 = st.columns([8, 1])

with header_col1:

    st.title("🌿 WisaBot")

    st.caption(
        "🟢 Online · Asisten wisata Kulon Progo"
    )

with header_col2:

    if st.button(
        "↻",
        help="Mulai percakapan baru",
        use_container_width=True
    ):

        st.session_state.chat_history = []
        st.session_state.pending_prompt = None

        st.rerun()


st.divider()


# ============================================================
# 6. UTILITIES
# ============================================================

def normalize_text(text):

    text = str(text).lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def safe_value(value, default="Tidak tersedia"):

    if pd.isna(value):
        return default

    value = str(value).strip()

    if not value or value.lower() == "nan":
        return default

    return value


def get_rating(row):

    rating = row.get("totalScore")

    if pd.isna(rating):
        return "Belum tersedia"

    return f"{float(rating):.1f}/5"


def get_reviews(row):

    value = row.get("reviewsCount", 0)

    if pd.isna(value):
        return 0

    return int(value)


def get_maps_link(row):

    latitude = row.get("latitude")
    longitude = row.get("longitude")

    if pd.isna(latitude) or pd.isna(longitude):
        return None

    return (
        "https://www.google.com/maps/search/?api=1"
        f"&query={latitude},{longitude}"
    )


# ============================================================
# 7. DESTINATION CARD
# ============================================================

def show_destination(row):

    name = safe_value(row.get("title"))
    category = safe_value(row.get("categoryName"))
    address = safe_value(row.get("address"))

    rating = get_rating(row)
    reviews = get_reviews(row)
    maps_link = get_maps_link(row)

    with st.container(border=True):

        st.markdown(f"### 📍 {name}")

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "⭐ Rating",
                rating
            )

        with col2:
            st.metric(
                "💬 Jumlah Ulasan",
                f"{reviews:,}"
            )

        st.write(f"🏷️ **Kategori:** category")

        st.write(f"📌 **Alamat:** {address}")

        if maps_link:
            st.link_button(
                "📍 Buka Google Maps",
                maps_link,
                use_container_width=True
            )


def show_multiple_destinations(df):

    if df is None or df.empty:
        return

    for _, row in df.iterrows():
        show_destination(row)


# ============================================================
# 8. SEARCH DESTINATION
# ============================================================

def search_destination(keyword):

    keyword = normalize_text(keyword)

    if not keyword:
        return []

    results = []

    for _, row in destinations.iterrows():

        title = normalize_text(row["title"])
        category = normalize_text(row["categoryName"])
        address = normalize_text(row["address"])

        score = 0

        if keyword in title:
            score = 100

        elif keyword in category:
            score = 70

        elif keyword in address:
            score = 40

        else:

            similarity = SequenceMatcher(
                None,
                keyword,
                title
            ).ratio()

            if similarity >= 0.55:
                score = similarity * 50

        if score > 0:

            results.append({
                "score": score,
                "row": row
            })

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results


# ============================================================
# 9. CATEGORY KEYWORDS
# ============================================================

CATEGORY_KEYWORDS = {

    "pantai": [
        "pantai",
        "laut",
        "pesisir"
    ],

    "alam": [
        "alam",
        "hutan",
        "gunung",
        "bukit",
        "pemandangan",
        "panorama",
        "air terjun",
        "sungai",
        "perbukitan"
    ],

    "sejarah": [
        "sejarah",
        "historis",
        "heritage",
        "budaya",
        "museum"
    ],

    "religi": [
        "religi",
        "ziarah",
        "makam",
        "masjid"
    ],

    "rekreasi": [
        "rekreasi",
        "hiburan",
        "keluarga",
        "taman",
        "bermain"
    ],

    "kuliner": [
        "kuliner",
        "makan",
        "restoran",
        "warung",
        "cafe",
        "kafe",
        "kopi"
    ],

    "instagramable": [
        "instagramable",
        "instagram",
        "estetik",
        "foto",
        "selfie",
        "spot foto"
    ],

    "healing": [
        "healing",
        "tenang",
        "santai",
        "relax",
        "relaksasi"
    ]
}


# ============================================================
# 10. CATEGORY MATCHING
# ============================================================

def get_category_matches(category):

    keywords = CATEGORY_KEYWORDS.get(category, [])

    results = []

    for _, row in destinations.iterrows():

        text = normalize_text(
            f"{row['title']} "
            f"{row['categoryName']} "
            f"{row['address']}"
        )

        if any(
            normalize_text(keyword) in text
            for keyword in keywords
        ):
            results.append(row)

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results)


# ============================================================
# 11. RANK DESTINATIONS
# ============================================================

def rank_destinations(df):

    if df is None or df.empty:
        return df

    df = df.copy()

    df["totalScore"] = pd.to_numeric(
        df["totalScore"],
        errors="coerce"
    )

    df["reviewsCount"] = pd.to_numeric(
        df["reviewsCount"],
        errors="coerce"
    ).fillna(0)

    return df.sort_values(
        by=["totalScore", "reviewsCount"],
        ascending=False,
        na_position="last"
    )


# ============================================================
# 12. RANDOM DESTINATION
# ============================================================

def get_random_destination(category=None):

    if category:

        filtered = get_category_matches(category)

        if filtered.empty:
            return None

        return filtered.sample(1).iloc[0]

    if destinations.empty:
        return None

    return destinations.sample(1).iloc[0]


# ============================================================
# 13. INTENT DETECTION
# ============================================================

def detect_intent(message):

    text = normalize_text(message)

    greeting_keywords = [
        "halo",
        "hai",
        "hello",
        "hi",
        "hey",
        "selamat pagi",
        "selamat siang",
        "selamat sore",
        "selamat malam"
    ]

    if any(keyword in text for keyword in greeting_keywords):
        return "greeting"

    help_keywords = [
        "bisa apa",
        "fitur",
        "bantuan",
        "help",
        "cara menggunakan",
        "kamu bisa apa"
    ]

    if any(keyword in text for keyword in help_keywords):
        return "help"

    random_keywords = [
        "acak",
        "random",
        "terserah",
        "bebas",
        "kejutan",
        "pilihkan",
        "pilih tempat",
        "rekomendasi secara acak"
    ]

    if any(keyword in text for keyword in random_keywords):
        return "random"

    popular_keywords = [
        "paling populer",
        "terpopuler",
        "paling banyak review",
        "paling banyak ulasan",
        "paling ramai"
    ]

    if any(keyword in text for keyword in popular_keywords):
        return "popular"

    ranking_keywords = [
        "rating tertinggi",
        "rating terbaik",
        "wisata terbaik",
        "destinasi terbaik",
        "paling bagus",
        "top destinasi"
    ]

    if any(keyword in text for keyword in ranking_keywords):
        return "ranking"

    # Kategori
    for category, keywords in CATEGORY_KEYWORDS.items():

        if any(
            normalize_text(keyword) in text
            for keyword in keywords
        ):
            return f"category_{category}"

    search_keywords = [
        "cari",
        "informasi",
        "info",
        "tentang",
        "dimana",
        "lokasi",
        "alamat"
    ]

    if any(keyword in text for keyword in search_keywords):
        return "search"

    return "unknown"


# ============================================================
# 14. CATEGORY RESPONSE
# ============================================================

def category_response(category):

    results = get_category_matches(category)

    if results.empty:

        return (
            "Hmm, aku belum menemukan destinasi yang cocok "
            "dengan kategori tersebut dari data yang tersedia. 😊 "
            "Coba kategori wisata lainnya ya!",
            None
        )

    results = rank_destinations(results).head(5)

    templates = [
        f"🌿 Kalau kamu mencari wisata {category}, berikut beberapa tempat yang bisa kamu pertimbangkan.",
        "Aku punya beberapa rekomendasi menarik nih! ✨ Mungkin ada yang cocok dengan rencana jalan-jalanmu.",
        "Siap! Ini beberapa destinasi yang berhasil aku temukan untukmu. 😊",
        "Wah, seru! Berikut pilihan destinasi yang bisa kamu jelajahi."
    ]

    return random.choice(templates), results


# ============================================================
# 15. CHATBOT RESPONSE
# ============================================================

def chatbot_response(message):

    text = normalize_text(message)
    intent = detect_intent(message)

    # Greeting
    if intent == "greeting":

        responses = [
            "Halo! 👋 Mau jalan-jalan ke Kulon Progo? Aku bisa bantu menemukan destinasi menarik.",
            "Hai! 🌿 Selamat datang. Lagi mencari tempat wisata untuk dikunjungi?",
            "Halo traveler! ✨ Mau mencari wisata alam, pantai, kuliner, atau tempat seru lainnya?"
        ]

        return random.choice(responses), None

    # Help
    if intent == "help":

        response = """
Aku bisa bantu kamu mencari berbagai destinasi wisata di Kulon Progo! 🌿

Kamu bisa mencoba:

- 🏖️ Rekomendasi wisata pantai
- 🌳 Wisata alam
- 📸 Tempat instagramable
- 🧘 Tempat untuk healing
- 🍽️ Wisata kuliner
- ⭐ Destinasi dengan rating terbaik
- 🔎 Mencari destinasi tertentu
- 🎲 Rekomendasi destinasi secara acak

Coba tanyakan apa yang ingin kamu cari!
"""

        return response, None

    # Random
    if intent == "random":

        row = get_random_destination()

        if row is None:
            return "Maaf, aku belum menemukan destinasi yang bisa direkomendasikan.", None

        responses = [
            "🎲 Aku punya pilihan spontan untukmu! Bagaimana kalau mencoba destinasi ini?",
            "✨ Ini rekomendasi acak dariku. Siapa tahu jadi tempat favoritmu!",
            "🌿 Coba pertimbangkan destinasi ini untuk petualangan berikutnya."
        ]

        return random.choice(responses), row.to_frame().T

    # Popular
    if intent == "popular":

        results = destinations.sort_values(
            "reviewsCount",
            ascending=False
        ).head(5)

        return (
            "🔥 Berikut destinasi dengan jumlah ulasan terbanyak berdasarkan dataset WisataKP.",
            results
        )

    # Ranking
    if intent == "ranking":

        results = destinations.sort_values(
            ["totalScore", "reviewsCount"],
            ascending=False
        ).head(5)

        return (
            "⭐ Ini beberapa destinasi dengan rating tertinggi dalam dataset WisataKP.",
            results
        )

    # Category
    if intent.startswith("category_"):

        category = intent.replace("category_", "")

        return category_response(category)

    # Search
    search_results = search_destination(message)

    if search_results:

        first = search_results[0]

        if first["score"] >= 60:

            row = first["row"]

            responses = [
                f"✨ Aku menemukan destinasi **{row['title']}**! Berikut informasi yang tersedia.",
                f"Ini dia destinasi yang kamu cari! 😊 Aku menemukan **{row['title']}**.",
                f"Yup, aku menemukan informasinya. Berikut detail **{row['title']}**."
            ]

            return random.choice(responses), row.to_frame().T

        results = pd.DataFrame(
            [
                item["row"]
                for item in search_results[:5]
            ]
        )

        return (
            "Aku menemukan beberapa destinasi yang mungkin sesuai dengan pencarianmu. 😊",
            results
        )

    # Unknown
    responses = [
        "Hmm, aku belum memahami pertanyaanmu sepenuhnya. 😊 Coba sebutkan nama destinasi atau jenis wisata yang ingin kamu cari.",
        "Aku belum menemukan informasi yang cocok nih. 🌿 Kamu bisa mencoba bertanya tentang wisata pantai, alam, kuliner, atau nama destinasi.",
        "Boleh coba gunakan kata kunci lain? ✨ Misalnya pantai, wisata alam, healing, kuliner, atau nama tempat yang ingin kamu kunjungi."
    ]

    return random.choice(responses), None


# ============================================================
# 16. QUICK PROMPTS
# ============================================================

quick_prompts = [
    "🏖️ Rekomendasi wisata pantai",
    "🌿 Wisata alam yang menarik",
    "📸 Tempat instagramable",
    "🧘 Tempat untuk healing",
    "⭐ Wisata dengan rating terbaik",
    "🎲 Pilihkan wisata secara acak"
]


# ============================================================
# 17. EMPTY CHAT
# ============================================================

if not st.session_state.chat_history:

    st.markdown("## Halo, Traveler! 👋")

    st.write(
        "Mau menjelajahi destinasi wisata Kulon Progo? "
        "Ceritakan tempat seperti apa yang kamu cari."
    )

    st.markdown("### ✨ Mulai dari sini")

    cols = st.columns(2)

    for index, prompt in enumerate(quick_prompts):

        with cols[index % 2]:

            if st.button(
                prompt,
                key=f"quick_{index}",
                use_container_width=True
            ):

                st.session_state.pending_prompt = prompt

                st.rerun()


# ============================================================

# ============================================================
# 18. CHAT HISTORY - CUSTOM LAYOUT STREAMLIT
# ============================================================

for chat in st.session_state.chat_history:

    if chat["role"] == "user":

        # Pesan pengguna di sisi kanan
        left_space, message_col = st.columns([2.5, 7])

        with message_col:
            with st.container(border=True):
                st.markdown(
                    f"👤 **Kamu**\n\n{chat['content']}"
                )

    else:

        # Pesan bot di sisi kiri
        message_col, right_space = st.columns([7, 2.5])

        with message_col:
            with st.container(border=True):
                st.markdown(
                    f"🌿 **WisaBot**\n\n{chat['content']}"
                )

                if chat.get("data") is not None:
                    show_multiple_destinations(chat["data"])



# ============================================================
# 19. CHAT INPUT
# ============================================================

user_input = st.chat_input(
    "Tanyakan destinasi wisata Kulon Progo..."
)


# Quick prompt handling
if st.session_state.pending_prompt:

    user_input = st.session_state.pending_prompt

    st.session_state.pending_prompt = None


# ============================================================
# 20. PROCESS MESSAGE
# ============================================================

if user_input:

    st.session_state.chat_history.append({
        "role": "user",
        "content": user_input,
        "data": None
    })

    response, data = chatbot_response(user_input)

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": response,
        "data": data
    })

    st.rerun()
