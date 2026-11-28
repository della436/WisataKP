
import os
import re
import html
import pandas as pd
from urllib.parse import urlparse

# =========================================================
# KONFIGURASI
# =========================================================

INPUT_FILE = "data/scraping/artikel_raw.csv"
OUTPUT_FILE = "data/processed/artikel_clean.csv"


# =========================================================
# CLEANING TEKS
# =========================================================

def clean_text(text):
    """
    Membersihkan teks dari HTML entity,
    whitespace berlebih, dan karakter pengganggu.
    """

    if pd.isna(text):
        return ""

    text = str(text)

    # Mengubah HTML entity
    text = html.unescape(text)

    # Menghapus whitespace berlebih
    text = re.sub(r"\s+", " ", text)

    # Menghapus spasi awal dan akhir
    text = text.strip()

    return text


# =========================================================
# CLEANING JUDUL
# =========================================================

def clean_title(title):
    """
    Membersihkan judul artikel.
    """

    title = clean_text(title)

    # Menghapus frasa yang bukan bagian dari judul
    unwanted_phrases = [
        "baca selengkapnya",
        "selengkapnya",
        "read more"
    ]

    for phrase in unwanted_phrases:
        title = re.sub(
            re.escape(phrase),
            "",
            title,
            flags=re.IGNORECASE
        )

    # Merapikan spasi kembali
    title = re.sub(r"\s+", " ", title).strip()

    return title


# =========================================================
# CLEANING URL
# =========================================================

def clean_url(url):
    """
    Membersihkan URL dari whitespace.
    URL asli tetap dipertahankan.
    """

    return clean_text(url)


def is_valid_url(url):
    """
    Memeriksa apakah URL memiliki format
    http atau https dan domain yang valid.
    """

    if not url:
        return False

    try:
        parsed = urlparse(url)

        return (
            parsed.scheme in ["http", "https"]
            and bool(parsed.netloc)
            and "." in parsed.netloc
        )

    except Exception:
        return False


# =========================================================
# CLEANING TANGGAL PUBLIKASI
# =========================================================

def clean_date(value):
    """
    Menyeragamkan tanggal publikasi
    menjadi YYYY-MM-DD.

    Jika format tidak dikenali,
    nilai aslinya tetap dipertahankan.
    """

    if pd.isna(value) or str(value).strip() == "":
        return ""

    value = clean_text(value)

    try:
        parsed = pd.to_datetime(
            value,
            errors="coerce",
            dayfirst=True
        )

        if pd.isna(parsed):
            return value

        return parsed.strftime("%Y-%m-%d")

    except Exception:
        return value


# =========================================================
# CLEANING TIMESTAMP SCRAPING
# =========================================================

def clean_datetime(value):
    """
    Menyeragamkan timestamp scraping
    dengan tetap mempertahankan jam.
    """

    if pd.isna(value) or str(value).strip() == "":
        return ""

    value = clean_text(value)

    try:
        parsed = pd.to_datetime(
            value,
            errors="coerce",
            format="%Y-%m-%d %H: %M: %S"
        )

        if pd.isna(parsed):
            return value

        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    except Exception:
        return value


# =========================================================
# PROSES CLEANING DATA
# =========================================================

def cleaning_data():

    print("\n========================================")
    print("CLEANING DATA WISATAKP")
    print("========================================\n")

    # -----------------------------------------------------
    # 1. MEMERIKSA FILE RAW
    # -----------------------------------------------------

    if not os.path.exists(INPUT_FILE):
        print("[ERROR] File artikel_raw.csv tidak ditemukan.")
        print(f"[INFO] Lokasi yang dicari: {INPUT_FILE}")
        return

    # -----------------------------------------------------
    # 2. MEMBACA DATA RAW
    # -----------------------------------------------------

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig"
    )

    total_awal = len(df)

    print(f"[INFO] Data awal: {total_awal} artikel")

    # -----------------------------------------------------
    # 3. MEMASTIKAN KOLOM TERSEDIA
    # -----------------------------------------------------

    required_columns = [
        "judul",
        "url",
        "ringkasan",
        "tanggal_publikasi",
        "tanggal_scraping"
    ]

    for column in required_columns:
        if column not in df.columns:
            df[column] = ""

    # Menggunakan kolom yang dibutuhkan saja
    df = df[required_columns].copy()

    # -----------------------------------------------------
    # 4. CLEANING JUDUL
    # -----------------------------------------------------

    df["judul"] = df["judul"].apply(clean_title)

    # -----------------------------------------------------
    # 5. CLEANING RINGKASAN
    # -----------------------------------------------------

    df["ringkasan"] = df["ringkasan"].apply(clean_text)

    # -----------------------------------------------------
    # 6. CLEANING URL
    # -----------------------------------------------------

    df["url"] = df["url"].apply(clean_url)

    # -----------------------------------------------------
    # 7. CLEANING TANGGAL PUBLIKASI
    # -----------------------------------------------------

    df["tanggal_publikasi"] = (
        df["tanggal_publikasi"].apply(clean_date)
    )

    # -----------------------------------------------------
    # 8. CLEANING TANGGAL SCRAPING
    # -----------------------------------------------------

    df["tanggal_scraping"] = (
        df["tanggal_scraping"].apply(clean_datetime)
    )

    # -----------------------------------------------------
    # 9. MENGHAPUS DATA TANPA JUDUL
    # -----------------------------------------------------

    jumlah_judul_kosong = (df["judul"] == "").sum()

    df = df[df["judul"] != ""]

    # -----------------------------------------------------
    # 10. MENGHAPUS DATA TANPA URL
    # -----------------------------------------------------

    jumlah_url_kosong = (df["url"] == "").sum()

    df = df[df["url"] != ""]

    # -----------------------------------------------------
    # 11. MEMERIKSA URL TIDAK VALID
    # -----------------------------------------------------

    df["url_valid"] = df["url"].apply(is_valid_url)

    jumlah_url_invalid = (~df["url_valid"]).sum()

    # URL tidak valid dikeluarkan dari dataset clean
    df = df[df["url_valid"] == True]

    # Menghapus kolom pemeriksaan sementara
    df = df.drop(columns=["url_valid"])

    # -----------------------------------------------------
    # 12. MENGHAPUS DUPLIKAT URL
    # -----------------------------------------------------

    jumlah_duplikat = df.duplicated(
        subset=["url"],
        keep="first"
    ).sum()

    df = df.drop_duplicates(
        subset=["url"],
        keep="first"
    )

    # -----------------------------------------------------
    # 13. RESET INDEX
    # -----------------------------------------------------

    df = df.reset_index(drop=True)

    # -----------------------------------------------------
    # 14. MENYIMPAN DATA CLEAN
    # -----------------------------------------------------

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # -----------------------------------------------------
    # 15. LAPORAN HASIL CLEANING
    # -----------------------------------------------------

    total_akhir = len(df)
    total_dihapus = total_awal - total_akhir

    print("\n========================================")
    print("CLEANING SELESAI")
    print("========================================")

    print(f"[INFO] Data awal              : {total_awal}")
    print(f"[INFO] Judul kosong          : {jumlah_judul_kosong}")
    print(f"[INFO] URL kosong            : {jumlah_url_kosong}")
    print(f"[INFO] URL tidak valid       : {jumlah_url_invalid}")
    print(f"[INFO] Duplikat URL         : {jumlah_duplikat}")
    print(f"[INFO] Data dihapus         : {total_dihapus}")
    print(f"[INFO] Data setelah cleaning : {total_akhir}")

    print(f"\n[INFO] Output: {OUTPUT_FILE}")

    # -----------------------------------------------------
    # 16. MENAMPILKAN SAMPLE DATA
    # -----------------------------------------------------

    print("\n[INFO] Contoh data setelah cleaning:")

    print(
        df[
            [
                "judul",
                "tanggal_publikasi",
                "url"
            ]
        ].head(5).to_string(index=False)
    )

    print("\n[INFO] File artikel_raw.csv tidak diubah.")
    print("[INFO] Cleaning selesai.")


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    cleaning_data()
