# ============================================================
# WISATAKP - WISBOT (AI TRAVEL ASSISTANT)
# Styling ada di: styles/main.css, sidebar.css, wisbot.css
# ============================================================

import base64
import math
import sys
from html import escape
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st


# ============================================================
# PATH & IMPORT
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR
sys.path.insert(0, str(BASE_DIR))

# Simpan gambar background di path ini (disarankan dikompres)
BACKGROUND_PATH = ROOT_DIR / "assets" / "images" / "kp.png"

from utils.wisbot_rules import (
    DESTINATIONS,
    handle_wisbot,
    recommend_destinations,
    extract_category_preference,
    detect_intent,
    find_destination,
    get_destination,
    popular_destinations,
    positive_review_destinations,
    format_number,
    safe_float,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="WisBot | WisataKP",
    page_icon="🌿",
    layout="wide"
)


# ============================================================
# LOAD CSS & BACKGROUND
# ============================================================

def load_css():

    css_files = [
        ROOT_DIR / "styles" / "main.css",
        ROOT_DIR / "styles" / "sidebar.css",
        ROOT_DIR / "styles" / "wisbot.css",
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


@st.cache_data(show_spinner=False)
def encode_image(path_string):

    return base64.b64encode(
        Path(path_string).read_bytes()
    ).decode("utf-8")


def apply_background():

    if not BACKGROUND_PATH.exists():

        st.warning(
            f"Background WisBot tidak ditemukan: {BACKGROUND_PATH}"
        )

        return

    mime = (
        "image/png"
        if BACKGROUND_PATH.suffix.lower() == ".png"
        else "image/jpeg"
    )

    encoded = encode_image(str(BACKGROUND_PATH))

    st.markdown(
        f"""
        <style>
        [data-testid="stMain"] {{
            background-image:
                linear-gradient(
                    rgba(235, 244, 253, 0.30),
                    rgba(235, 244, 253, 0.10)
                ),
                url("data:{mime};base64,{encoded}");

            background-size: cover;
            background-position: center bottom;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}

        [data-testid="stMainBlockContainer"],
        [data-testid="stHeader"] {{
            background: transparent !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )


load_css()
apply_background()


# ============================================================
# CONFIGURATION
# ============================================================

# Kolom gambar yang dicari pada destinasi_clean.csv
IMAGE_COLUMNS = [
    "imageUrl",
    "image_url",
    "image",
    "thumbnail",
    "photo",
    "imageUrls/0",
]

# Kartu menu pada welcome section
QUICK_PROMPTS = [
    {
        "icon": "⛰️",
        "art": "🏔️",
        "title": "Rekomendasi Wisata",
        "desc": "Dapatkan rekomendasi destinasi sesuai minatmu",
        "question": "Rekomendasi wisata",
    },
    {
        "icon": "🏆",
        "art": "📷",
        "title": "Destinasi Paling Populer",
        "desc": "Lihat destinasi dengan jumlah review terbanyak",
        "question": "Destinasi paling populer",
    },
    {
        "icon": "💚",
        "art": "⭐",
        "title": "Review Positif Terbanyak",
        "desc": "Temukan destinasi dengan ulasan positif terbanyak",
        "question": "Destinasi dengan review positif paling banyak",
    },
    {
        "icon": "🗓️",
        "art": "🗺️",
        "title": "Buat Itinerary",
        "desc": "Rencanakan perjalananmu di Kulon Progo",
        "question": "Buat itinerary 1 hari",
    },
]

# Chip "Coba tanyakan, misalnya"
TRY_QUESTIONS = [
    "Rekomendasikan wisata alam",
    "Pantai untuk liburan santai",
    "Tempat kuliner enak",
    "Buat itinerary 1 hari",
]

# Kategori wisata (pilihan kategori)
WISATA_CATEGORIES = [
    {"icon": "🏖️", "label": "Pantai", "query": "Rekomendasi wisata pantai"},
    {"icon": "🌳", "label": "Wisata Alam", "query": "Rekomendasi wisata alam"},
    {"icon": "💧", "label": "Air Terjun", "query": "Rekomendasi wisata air terjun"},
    {"icon": "🏡", "label": "Desa Wisata & Budaya", "query": "Rekomendasi desa wisata dan budaya"},
    {"icon": "🌺", "label": "Taman & Kebun", "query": "Rekomendasi wisata taman dan kebun"},
    {"icon": "🌄", "label": "Panorama", "query": "Rekomendasi wisata panorama"},
]

CATEGORY_ICONS = {
    "Pantai": "🏖️",
    "Wisata Air": "💧",
    "Desa & Budaya": "🏡",
    "Kuliner": "🍽️",
    "Taman & Kebun": "🌺",
    "Panorama": "🌄",
    "Wisata Alam": "🌳",
    "Lainnya": "📍",
}

CATEGORY_CLASSES = {
    "Pantai": "wb-cat-pantai",
    "Wisata Air": "wb-cat-air",
    "Desa & Budaya": "wb-cat-desa",
    "Kuliner": "wb-cat-kuliner",
    "Taman & Kebun": "wb-cat-taman",
    "Panorama": "wb-cat-panorama",
    "Wisata Alam": "wb-cat-alam",
    "Lainnya": "wb-cat-lain",
}

CATEGORY_REASONS = {
    "Pantai": "Menikmati suasana laut dan waktu santai",
    "Wisata Air": "Bermain air dan menikmati kesegaran alam",
    "Desa & Budaya": "Mengenal budaya dan kehidupan desa",
    "Kuliner": "Mencicipi makanan dan nongkrong santai",
    "Taman & Kebun": "Berjalan santai di tengah tanaman",
    "Panorama": "Healing dan menikmati pemandangan",
    "Wisata Alam": "Udara segar dan suasana alam",
    "Lainnya": "Menambah pilihan liburanmu",
}

ITINERARY_KEYWORDS = [
    "itinerary",
    "rencana perjalanan",
    "jadwal wisata",
]

ITINERARY_SLOTS = [
    ("🌅", "Pagi", "08.00"),
    ("☀️", "Siang", "12.00"),
    ("🌇", "Sore", "16.00"),
]

DEFAULT_SUGGESTIONS = [
    ("🌿", "Rekomendasi wisata"),
    ("🏆", "Destinasi paling populer"),
    ("💚", "Destinasi dengan review positif paling banyak"),
    ("🗓️", "Buat itinerary 1 hari"),
]

TYPING_HTML = (
    '<div class="wb-typing">'
    '<div class="wb-typing-icon">🤖</div>'
    '<div class="wb-typing-bubble">'
    '<div class="wb-typing-text">Sedang mencari destinasi terbaik untukmu</div>'
    '<div class="wb-dots"><span></span><span></span><span></span></div>'
    '</div>'
    '</div>'
)


# ============================================================
# SESSION STATE
# ============================================================

if "wisbot_messages" not in st.session_state:
    st.session_state.wisbot_messages = []

if "wisbot_recommendation_state" not in st.session_state:
    st.session_state.wisbot_recommendation_state = None


# ============================================================
# HELPER
# ============================================================

def to_html(value):
    """Escape teks agar aman dimasukkan ke HTML."""

    return escape(str(value)).replace("$", "&#36;")


def rating_label(value):

    number = safe_float(value)

    if number is None:
        return "Tidak tersedia"

    return f"{number:.1f} / 5"


def get_image_url(row):
    """Mengambil URL gambar destinasi (jika ada di dataset)."""

    if row is None:
        return ""

    for column in IMAGE_COLUMNS:

        try:
            value = row.get(column)
        except AttributeError:
            return ""

        if value is None or pd.isna(value):
            continue

        value = str(value).strip()

        if value.lower().startswith(("http://", "https://")):
            return value

    return ""


def photo_html(image_url, category, css_class=""):
    """Foto destinasi, atau gradient + ikon kategori jika tidak ada foto."""

    if image_url:
        return (
            f'<img class="wb-photo {css_class}" '
            f'src="{escape(image_url, quote=True)}" '
            'alt="" loading="lazy">'
        )

    icon = CATEGORY_ICONS.get(category, "📍")

    return (
        f'<div class="wb-photo wb-photo-fallback {css_class}">{icon}</div>'
    )


def chip_html(category):

    css_class = CATEGORY_CLASSES.get(category, "wb-cat-lain")

    icon = CATEGORY_ICONS.get(category, "📍")

    return (
        f'<span class="wb-chip {css_class}">'
        f'{icon} {to_html(category)}</span>'
    )


def rank_class(rank):

    return {1: "gold", 2: "silver", 3: "bronze"}.get(rank, "plain")


def maps_url_for(name, address):

    query = quote(f"{name}, {address}, Kulon Progo, Yogyakarta")

    return (
        "https://www.google.com/maps/search/?api=1"
        f"&query={query}"
    )


def clean_address(value):

    if value is None or pd.isna(value):
        return "Kulon Progo, Yogyakarta"

    value = str(value).strip()

    if value.lower() in ["", "nan", "none"]:
        return "Kulon Progo, Yogyakarta"

    return value


def add_message(role, content="", kind="text", data=None, suggestions=None):

    st.session_state.wisbot_messages.append(
        {
            "role": role,
            "content": content,
            "kind": kind,
            "data": data,
            "suggestions": suggestions or [],
        }
    )


def is_general_recommendation(question):
    """Rekomendasi umum tanpa kategori -> tampilkan pilihan kategori."""

    normalized_question = str(question).lower().strip()

    recommendation_triggers = [
        "rekomendasi wisata",
        "rekomendasikan wisata",
        "rekomendasi tempat wisata",
        "rekomendasi destinasi"
    ]

    category_words = [
        "pantai",
        "alam",
        "air terjun",
        "kuliner",
        "desa",
        "budaya",
        "taman",
        "kebun",
        "panorama",
        "bukit"
    ]

    return (
        any(
            trigger in normalized_question
            for trigger in recommendation_triggers
        )
        and not any(
            word in normalized_question
            for word in category_words
        )
    )


# ============================================================
# DATA: POPULER & REVIEW POSITIF (di-cache)
# ============================================================

@st.cache_data(show_spinner=False)
def get_popular_data(limit=5):

    result = popular_destinations(limit)

    if result is None or result.empty:
        return []

    items = []

    for _, row in result.iterrows():

        items.append(
            {
                "name": str(row["title"]),
                "reviews": format_number(row.get("reviews_num")),
                "rating": rating_label(row.get("totalScore")),
                "category": str(row.get("kategori", "Lainnya")),
                "image": get_image_url(row),
            }
        )

    return items


@st.cache_data(show_spinner=False)
def get_positive_data(limit=5):

    result = positive_review_destinations(limit)

    if result is None or result.empty:
        return []

    items = []

    for _, row in result.iterrows():

        name = str(row["title"])

        destination = get_destination(name)

        category = (
            str(destination.get("kategori", "Lainnya"))
            if destination is not None
            else "Lainnya"
        )

        items.append(
            {
                "name": name,
                "rating": rating_label(row.get("rating")),
                "positive": int(row["positive"]),
                "neutral": int(row["neutral"]),
                "negative": int(row["negative"]),
                "percentage": float(row["positive_percentage"]),
                "category": category,
                "image": get_image_url(destination),
            }
        )

    return items


# ============================================================
# HTML: PANEL POPULER
# ============================================================

def build_popular_html(items):

    cards = ""

    for rank, item in enumerate(items, start=1):

        cards += (
            '<div class="wb-pop-card">'
            '<div class="wb-pop-media">'
            f'{photo_html(item["image"], item["category"])}'
            f'<span class="wb-rank wb-rank-{rank_class(rank)}">{rank}</span>'
            '</div>'
            f'<div class="wb-pop-name">{to_html(item["name"])}</div>'
            f'<div class="wb-pop-meta">💬 {to_html(item["reviews"])} ulasan</div>'
            f'<div class="wb-pop-meta">⭐ {to_html(item["rating"])}</div>'
            f'{chip_html(item["category"])}'
            '</div>'
        )

    return (
        '<div class="wb-panel">'
        '<div class="wb-panel-head">'
        '<div>'
        '<div class="wb-panel-title">🏆 Destinasi Paling Populer</div>'
        '<div class="wb-panel-sub">'
        'Diurutkan berdasarkan jumlah review terbanyak pada dataset.'
        '</div>'
        '</div>'
        '<div class="wb-panel-deco">🔭📍</div>'
        '</div>'
        f'<div class="wb-pop-grid">{cards}</div>'
        '</div>'
    )


# ============================================================
# HTML: PANEL REVIEW POSITIF
# ============================================================

def build_positive_html(items):

    rows = ""

    for rank, item in enumerate(items, start=1):

        positive = item["positive"]
        neutral = item["neutral"]
        negative = item["negative"]

        total = positive + neutral + negative

        if total > 0:
            width_positive = positive / total * 100
            width_neutral = neutral / total * 100
            width_negative = negative / total * 100
        else:
            width_positive = width_neutral = width_negative = 0

        rows += (
            '<div class="wb-pos-row">'
            f'<span class="wb-rank wb-rank-{rank_class(rank)}">{rank}</span>'
            '<div class="wb-pos-photo">'
            f'{photo_html(item["image"], item["category"])}'
            '</div>'
            '<div>'
            f'<div class="wb-pos-name">{to_html(item["name"])}</div>'
            f'<div class="wb-pos-meta">⭐ {to_html(item["rating"])}</div>'
            '<div class="wb-pos-meta">📍 Kulon Progo</div>'
            '</div>'
            '<div class="wb-pos-counts">'
            f'<div><i class="wb-dot wb-dot-pos"></i>Positif: <b>{positive}</b></div>'
            f'<div><i class="wb-dot wb-dot-neu"></i>Netral: <b>{neutral}</b></div>'
            f'<div><i class="wb-dot wb-dot-neg"></i>Negatif: <b>{negative}</b></div>'
            '</div>'
            '<div class="wb-bar">'
            f'<span class="wb-bar-pos" style="width:{width_positive:.1f}%"></span>'
            f'<span class="wb-bar-neu" style="width:{width_neutral:.1f}%"></span>'
            f'<span class="wb-bar-neg" style="width:{width_negative:.1f}%"></span>'
            '</div>'
            '<div class="wb-pct">'
            f'<b>{item["percentage"]:.1f}%</b>'
            '<span>ulasan positif</span>'
            '</div>'
            '</div>'
        )

    return (
        '<div class="wb-panel">'
        '<div class="wb-panel-head">'
        '<div>'
        '<div class="wb-panel-title">💚 Destinasi dengan Review Positif Terbanyak</div>'
        '<div class="wb-panel-sub">Diurutkan berdasarkan jumlah review positif.</div>'
        '</div>'
        '<div class="wb-panel-deco">👍</div>'
        '</div>'
        f'<div class="wb-pos-list">{rows}</div>'
        '</div>'
    )


# ============================================================
# REKOMENDASI KATEGORI (KARTU)
# ============================================================

def build_cards(result):

    cards = []

    for _, row in result.iterrows():

        name = str(row.get("title", "Destinasi"))

        address = clean_address(row.get("address"))

        cards.append(
            {
                "name": name,
                "category": str(row.get("kategori", "Lainnya")),
                "address": address,
                "rating": rating_label(row.get("totalScore")),
                "maps_url": maps_url_for(name, address),
                "image": get_image_url(row),
            }
        )

    return cards


def build_cards_html(cards):

    items = ""

    for rank, card in enumerate(cards, start=1):

        category = card["category"]

        reason = CATEGORY_REASONS.get(
            category,
            CATEGORY_REASONS["Lainnya"]
        )

        items += (
            '<div class="wb-card">'
            '<div class="wb-card-cover">'
            f'{photo_html(card["image"], category)}'
            f'<span class="wb-rank wb-rank-{rank_class(rank)}">{rank}</span>'
            '</div>'
            '<div class="wb-card-body">'
            f'{chip_html(category)}'
            f'<div class="wb-card-name">{to_html(card["name"])}</div>'
            f'<div class="wb-card-loc">📍 {to_html(card["address"])}</div>'
            f'<div class="wb-card-rating">⭐ {to_html(card["rating"])}</div>'
            f'<div class="wb-card-reason">✨ Cocok untuk: {to_html(reason)}</div>'
            f'<a class="wb-link" href="{escape(card["maps_url"], quote=True)}" '
            'target="_blank" rel="noopener noreferrer">'
            'Lihat lokasi di Google Maps ↗</a>'
            '</div>'
            '</div>'
        )

    return f'<div class="wb-cards">{items}</div>'


# ============================================================
# ITINERARY 1 HARI
# ============================================================

def distance_km(row_a, row_b):
    """Jarak antar dua destinasi (haversine). inf jika koordinat kosong."""

    lat1 = safe_float(row_a.get("latitude"))
    lon1 = safe_float(row_a.get("longitude"))
    lat2 = safe_float(row_b.get("latitude"))
    lon2 = safe_float(row_b.get("longitude"))

    if None in (lat1, lon1, lat2, lon2):
        return float("inf")

    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )

    return 6371 * 2 * math.asin(math.sqrt(a))


def build_itinerary(question):
    """
    Itinerary 1 hari: destinasi dengan rating tertinggi,
    ditambah dua destinasi terdekat darinya.
    """

    if DESTINATIONS is None or DESTINATIONS.empty:
        return None

    category = extract_category_preference(question)

    df = DESTINATIONS.copy()

    if category:

        filtered = df[df["kategori"] == category]

        if len(filtered) >= 3:
            df = filtered

    df = df.sort_values(
        ["rating_num", "reviews_num"],
        ascending=False,
        na_position="last"
    ).head(15)

    rows = [row for _, row in df.iterrows()]

    if not rows:
        return None

    seed = rows[0]

    others = sorted(
        rows[1:],
        key=lambda row: distance_km(seed, row)
    )

    picks = [seed] + others[:2]

    items = []

    for (icon, slot, time_label), row in zip(ITINERARY_SLOTS, picks):

        name = str(row.get("title", "Destinasi"))

        address = clean_address(row.get("address"))

        items.append(
            {
                "icon": icon,
                "slot": slot,
                "time": time_label,
                "name": name,
                "category": str(row.get("kategori", "Lainnya")),
                "address": address,
                "rating": rating_label(row.get("totalScore")),
                "maps_url": maps_url_for(name, address),
                "image": get_image_url(row),
            }
        )

    return items


def build_itinerary_html(items):

    rows = ""

    for item in items:

        rows += (
            '<div class="wb-trip-row">'
            '<div class="wb-trip-time">'
            f'{item["icon"]}<b>{item["slot"]}</b><span>{item["time"]}</span>'
            '</div>'
            '<div class="wb-trip-photo">'
            f'{photo_html(item["image"], item["category"])}'
            '</div>'
            '<div class="wb-trip-body">'
            f'{chip_html(item["category"])}'
            f'<div class="wb-pos-name">{to_html(item["name"])}</div>'
            f'<div class="wb-pos-meta">⭐ {to_html(item["rating"])} · '
            f'📍 {to_html(item["address"])}</div>'
            f'<a class="wb-link" href="{escape(item["maps_url"], quote=True)}" '
            'target="_blank" rel="noopener noreferrer">'
            'Lihat lokasi di Google Maps ↗</a>'
            '</div>'
            '</div>'
        )

    return (
        '<div class="wb-panel">'
        '<div class="wb-panel-head">'
        '<div>'
        '<div class="wb-panel-title">🗓️ Itinerary 1 Hari di Kulon Progo</div>'
        '<div class="wb-panel-sub">'
        'Disusun dari rating tertinggi dan destinasi yang saling berdekatan.'
        '</div>'
        '</div>'
        '<div class="wb-panel-deco">🗺️</div>'
        '</div>'
        f'<div class="wb-trip-list">{rows}</div>'
        '<div class="wb-trip-note">'
        'Jam hanya usulan awal. Cek jam buka dan waktu tempuh '
        'sebelum berangkat.'
        '</div>'
        '</div>'
    )


# ============================================================
# RESPONSE GENERATOR
# ============================================================

def generate_response(question):
    """
    Menentukan jenis jawaban:
    itinerary, populer, review positif, rekomendasi (kartu), atau teks.
    """

    try:

        normalized = str(question).lower()

        # Itinerary
        if any(keyword in normalized for keyword in ITINERARY_KEYWORDS):

            items = build_itinerary(question)

            if items:
                return {"kind": "itinerary", "content": "", "data": items}

            return {
                "kind": "text",
                "content": "Maaf, data destinasi belum tersedia untuk menyusun itinerary.",
                "data": None,
            }

        intent = detect_intent(question)

        category = extract_category_preference(question)

        # Destinasi paling populer
        if intent == "popular":

            items = get_popular_data()

            if items:
                return {"kind": "popular", "content": "", "data": items}

        # Review positif terbanyak
        if intent == "positive_reviews":

            items = get_positive_data()

            if items:
                return {"kind": "positive", "content": "", "data": items}

        # Rekomendasi
        if intent == "recommendation" or (intent == "unknown" and category):

            result = recommend_destinations(question, limit=5)

            if result is not None and not result.empty:

                category_matched = (
                    category
                    and "kategori" in result.columns
                    and (result["kategori"] == category).all()
                )

                if category_matched:
                    intro = (
                        "**Aku punya rekomendasi untukmu!** 🌿\n\n"
                        f"Berikut destinasi **{category}** "
                        "dengan rating tertinggi di Kulon Progo."
                    )
                elif category:
                    intro = (
                        "**Aku punya rekomendasi untukmu!** 🌿\n\n"
                        f"Belum ada destinasi kategori **{category}** "
                        "di data, jadi ini destinasi dengan rating "
                        "tertinggi di Kulon Progo."
                    )
                else:
                    intro = (
                        "**Aku punya rekomendasi untukmu!** 🌿\n\n"
                        "Berikut destinasi dengan rating tertinggi "
                        "di Kulon Progo."
                    )

                return {
                    "kind": "recommendation",
                    "content": intro,
                    "data": build_cards(result),
                }

        return {
            "kind": "text",
            "content": handle_wisbot(question),
            "data": None,
        }

    except Exception as error:

        print(f"[WisBot Error] {error}")

        return {
            "kind": "text",
            "content": (
                "Maaf, sepertinya terjadi kendala saat memproses "
                "pertanyaanmu. 😔\n\n"
                "Coba tanyakan kembali beberapa saat lagi."
            ),
            "data": None,
        }


# ============================================================
# SUGGESTED QUESTIONS
# ============================================================

def build_suggestions(question):
    """Pertanyaan lanjutan yang mengikuti konteks jawaban."""

    suggestions = []

    try:

        intent = detect_intent(question)

        category = extract_category_preference(question)

        if intent == "recommendation":

            if category == "Pantai":
                suggestions.append(("🌳", "Rekomendasi wisata alam"))
            else:
                suggestions.append(("🏖️", "Rekomendasi wisata pantai"))

        elif intent in ["information", "review"]:

            destination = find_destination(question)

            if destination:

                if intent == "information":
                    suggestions.append(
                        ("💬", f"Bagaimana sentimen pengunjung {destination}?")
                    )
                else:
                    suggestions.append(
                        ("📍", f"Ceritakan tentang {destination}")
                    )

    except Exception as error:

        print(f"[WisBot Suggestion Error] {error}")

    asked = str(question).strip().lower()

    for icon, text in DEFAULT_SUGGESTIONS:

        if len(suggestions) >= 3:
            break

        already_added = any(text == item[1] for item in suggestions)

        if text.lower() != asked and not already_added:
            suggestions.append((icon, text))

    return suggestions[:3]


# ============================================================
# RENDER PESAN
# ============================================================

def render_message(message):

    kind = message.get("kind", "text")

    data = message.get("data")

    if message.get("content"):
        st.markdown(message["content"], unsafe_allow_html=False)

    if kind == "recommendation" and data:
        st.markdown(build_cards_html(data), unsafe_allow_html=True)

    elif kind == "popular" and data:
        st.markdown(build_popular_html(data), unsafe_allow_html=True)

    elif kind == "positive" and data:
        st.markdown(build_positive_html(data), unsafe_allow_html=True)

    elif kind == "itinerary" and data:
        st.markdown(build_itinerary_html(data), unsafe_allow_html=True)


# ============================================================
# HANDLE INPUT
# ============================================================

user_input = st.chat_input(
    "Tanyakan destinasi, wisata, atau rencana perjalananmu..."
)

pending_question = st.session_state.pop(
    "wisbot_pending_question",
    None
)

question = user_input or pending_question

needs_response = False

if question:

    question = str(question).strip()

    add_message("user", question)

    # Rekomendasi umum -> pilihan kategori
    if is_general_recommendation(question):

        add_message(
            "assistant",
            "🌿 **Yuk, jelajahi wisata Kulon Progo!**\n\n"
            "Kamu sedang ingin menikmati wisata yang seperti apa? "
            "Pilih kategori yang paling menarik buatmu, ya."
        )

        st.session_state.wisbot_recommendation_state = "choose_category"

    # Pertanyaan biasa -> diproses setelah chat tampil
    else:

        st.session_state.wisbot_recommendation_state = None

        needs_response = True


messages = st.session_state.wisbot_messages


# ============================================================
# 1. HEADER
# ============================================================

st.markdown(
    '<div class="wb-header">'
    '<div class="wb-header-left">'
    '<div class="wb-logo">🤖</div>'
    '<div>'
    '<div class="wb-header-title">WisBot – AI Travel Assistant</div>'
    '<div class="wb-header-sub">Teman perjalananmu menjelajahi Kulon Progo</div>'
    '</div>'
    '</div>'
    '<div class="wb-online"><span class="wb-online-dot"></span>Online</div>'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# 2. WELCOME (saat chat masih kosong)
# ============================================================

if not messages:

    st.markdown(
        '<div class="wb-hero">'
        '<div class="wb-hero-title">'
        'Your Next <span class="wb-hl">Adventure</span> Starts Here ✨'
        '</div>'
        '<div class="wb-hero-sub">'
        'Bingung mau ke mana? Ceritakan perjalanan yang kamu inginkan, '
        'dan temukan destinasi terbaik di Kulon Progo.'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    prompt_columns = st.columns(4)

    for index, prompt in enumerate(QUICK_PROMPTS):

        with prompt_columns[index]:

            with st.container(key=f"wb_qp_card_{index}"):

                st.markdown(
                    f'<div class="wb-qp-icon">{prompt["icon"]}</div>'
                    f'<div class="wb-qp-title">{prompt["title"]}</div>'
                    f'<div class="wb-qp-desc">{prompt["desc"]}</div>',
                    unsafe_allow_html=True
                )

                art_column, button_column = st.columns([3, 1])

                with art_column:

                    st.markdown(
                        f'<div class="wb-qp-art">{prompt["art"]}</div>',
                        unsafe_allow_html=True
                    )

                with button_column:

                    if st.button("→", key=f"wb_qp_{index}"):

                        st.session_state.wisbot_pending_question = (
                            prompt["question"]
                        )

                        st.rerun()

    with st.container(key="wb_try"):

        st.markdown(
            '<div class="wb-try-title">✨ Coba tanyakan, misalnya:</div>',
            unsafe_allow_html=True
        )

        try_columns = st.columns(4)

        for index, text in enumerate(TRY_QUESTIONS):

            with try_columns[index]:

                if st.button(
                    f"💬 {text}",
                    key=f"wb_try_{index}",
                    use_container_width=True
                ):

                    st.session_state.wisbot_pending_question = text

                    st.rerun()


# ============================================================
# 3. CONVERSATION AREA
# ============================================================

else:

    toolbar_left, toolbar_right = st.columns([5, 1])

    with toolbar_left:

        st.markdown(
            '<div class="wb-toolbar-title">💬 Percakapan</div>',
            unsafe_allow_html=True
        )

    with toolbar_right:

        if st.button(
            "🗑️ Hapus chat",
            key="wb_clear",
            use_container_width=True
        ):

            st.session_state.wisbot_messages = []

            st.session_state.wisbot_recommendation_state = None

            st.session_state.pop("wisbot_pending_question", None)

            st.rerun()

    for message in messages:

        avatar = "🤖" if message["role"] == "assistant" else None

        with st.chat_message(message["role"], avatar=avatar):

            render_message(message)


# ============================================================
# 4. LOADING & RESPONSE
# ============================================================

if needs_response:

    typing_placeholder = st.empty()

    typing_placeholder.markdown(
        TYPING_HTML,
        unsafe_allow_html=True
    )

    response = generate_response(question)

    add_message(
        "assistant",
        response.get("content", ""),
        kind=response.get("kind", "text"),
        data=response.get("data"),
        suggestions=build_suggestions(question)
    )

    st.rerun()


# ============================================================
# 5. CATEGORY PICKER
# ============================================================

if st.session_state.wisbot_recommendation_state == "choose_category":

    with st.container(key="wb_picker"):

        st.markdown(
            '<div class="wb-picker-title">🌿 Jelajahi Wisata Kulon Progo</div>'
            '<div class="wb-picker-sub">'
            'Pilih kategori yang paling menarik buatmu.'
            '</div>',
            unsafe_allow_html=True
        )

        category_columns = st.columns(3)

        for index, category in enumerate(WISATA_CATEGORIES):

            with category_columns[index % 3]:

                if st.button(
                    f"{category['icon']} {category['label']}",
                    key=f"wb_cat_{index}",
                    use_container_width=True
                ):

                    st.session_state.wisbot_pending_question = (
                        category["query"]
                    )

                    st.session_state.wisbot_recommendation_state = None

                    st.rerun()


# ============================================================
# 6. SUGGESTED QUESTIONS
# ============================================================

elif messages and messages[-1]["role"] == "assistant":

    suggestions = messages[-1].get("suggestions", [])

    if suggestions:

        with st.container(key="wb_suggest"):

            st.markdown(
                '<div class="wb-suggest-title">Mungkin kamu juga tertarik</div>',
                unsafe_allow_html=True
            )

            for index, (icon, text) in enumerate(suggestions):

                if st.button(
                    f"{icon}  {text}",
                    key=f"wb_sg_{len(messages)}_{index}",
                    use_container_width=True
                ):

                    st.session_state.wisbot_pending_question = text

                    st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    '<div class="wb-footer">'
    'Powered by WisataKP · Explore more, travel better'
    '</div>',
    unsafe_allow_html=True
)