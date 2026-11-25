
from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="WisataKP | Explore Kulon Progo",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "assets" / "css" / "style.css"

def load_global_css():
    if CSS_PATH.exists():
        css = CSS_PATH.read_text(encoding="utf-8")
        st.markdown(
            f"<style>{css}</style>",
            unsafe_allow_html=True
        )

load_global_css()
