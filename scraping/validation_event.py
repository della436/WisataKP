
import pandas as pd
import re
from pathlib import Path

# =========================================================
# CONFIGURATION
# =========================================================

INPUT_FILE = "data/events/event_candidates.csv"

OUTPUT_VALID = "data/events/event_valid.csv"
OUTPUT_REVIEW = "data/events/event_review.csv"
OUTPUT_INVALID = "data/events/event_invalid.csv"


# =========================================================
# 1. UTILITAS
# =========================================================

def normalisasi_teks(teks):
    if pd.isna(teks):
        return ""

    teks = str(teks).lower()
    teks = re.sub(r"\s+", " ", teks)
    return teks.strip()


def nilai_kosong(nilai):
    if pd.isna(nilai):
        return True

    nilai = str(nilai).strip()

    if nilai == "":
        return True

    if nilai.lower() in ["nan", "none", "null", "nat"]:
        return True

    return False


def cek_url(url):
    if nilai_kosong(url):
        return False

    url = str(url).strip()

    return bool(
        re.match(r"^https?://", url, flags=re.I)
    )


# =========================================================
# 2. KEYWORD PEMERIKSAAN RELEVANSI
# =========================================================

KEYWORDS_EVENT = [
    "festival", "karnaval", "kirab", "pawai", "parade",
    "konser", "pentas seni", "pertunjukan", "pagelaran",
    "gelar budaya", "gelar seni", "lomba", "kompetisi",
    "turnamen", "kejuaraan", "maraton", "marathon",
    "half marathon", "fun run", "jalan sehat", "race",
    "pameran", "bazar", "bazaar", "pasar rakyat",
    "jemparingan", "wayang", "camping", "glamping",
    "outbound", "merti desa", "rasulan", "grebeg",
    "larung", "sedekah bumi", "bersih desa",
    "upacara adat", "touring", "fam trip",
    "familiarization trip", "travel fair", "sport tourism",
    "festival kuliner", "festival budaya",
    "festival musik", "festival pantai"
]


KEYWORDS_ADMINISTRATIF = [
    "rapat", "rapat koordinasi", "rakor",
    "evaluasi", "monitoring", "audiensi",
    "kunjungan kerja", "kunjungan dinas",
    "studi banding", "bimtek", "pelatihan pegawai",
    "pelantikan", "penyerahan bantuan",
    "penandatanganan", "sosialisasi",
    "koordinasi internal"
]


# =========================================================
# 3. PEMERIKSAAN RELEVANSI
# =========================================================

def cek_relevansi(judul, ringkasan):

    teks = normalisasi_teks(
        f"{judul} {ringkasan}"
    )

    keyword_event = [
        keyword for keyword in KEYWORDS_EVENT
        if keyword in teks
    ]

    keyword_admin = [
        keyword for keyword in KEYWORDS_ADMINISTRATIF
        if keyword in teks
    ]

    # Artikel tanpa indikasi event
    if not keyword_event:

        return (
            False,
            "Tidak ditemukan indikator event"
        )

    # Artikel administratif dominan
    if keyword_admin and not any(
        keyword in normalisasi_teks(judul)
        for keyword in KEYWORDS_EVENT
    ):

        return (
            False,
            "Artikel terindikasi kegiatan administratif"
        )

    return (
        True,
        "Indikator event ditemukan"
    )


# =========================================================
# 4. VALIDASI SATU BARIS DATA
# =========================================================

def validasi_baris(row):

    masalah = []

    judul = row.get("judul", "")

    ringkasan = row.get("ringkasan", "")

    nama_event = row.get("nama_event", "")

    tanggal_event = row.get(
        "tanggal_event_ekstrak", ""
    )

    lokasi_event = row.get(
        "lokasi_event_ekstrak", ""
    )

    kategori_event = row.get(
        "kategori_event_ekstrak", ""
    )

    deskripsi_event = row.get(
        "deskripsi_event", ""
    )

    url = row.get("url", "")


    # -----------------------------------------------------
    # Pemeriksaan relevansi
    # -----------------------------------------------------

    relevan, alasan_relevansi = cek_relevansi(
        judul,
        ringkasan
    )

    if not relevan:
        masalah.append(alasan_relevansi)


    # -----------------------------------------------------
    # Pemeriksaan nama event
    # -----------------------------------------------------

    if nilai_kosong(nama_event):
        masalah.append("Nama event tidak tersedia")


    # -----------------------------------------------------
    # Pemeriksaan tanggal
    # -----------------------------------------------------

    if nilai_kosong(tanggal_event):
        masalah.append("Tanggal event tidak ditemukan")


    # -----------------------------------------------------
    # Pemeriksaan lokasi
    # -----------------------------------------------------

    if nilai_kosong(lokasi_event):
        masalah.append("Lokasi event tidak ditemukan")


    # -----------------------------------------------------
    # Pemeriksaan kategori
    # -----------------------------------------------------

    if (
        nilai_kosong(kategori_event)
        or str(kategori_event).lower()
        == "belum_teridentifikasi"
    ):
        masalah.append("Kategori event belum teridentifikasi")


    # -----------------------------------------------------
    # Pemeriksaan deskripsi
    # -----------------------------------------------------

    if nilai_kosong(deskripsi_event):
        masalah.append("Deskripsi event tidak tersedia")


    # -----------------------------------------------------
    # Pemeriksaan sumber
    # -----------------------------------------------------

    if not cek_url(url):
        masalah.append("URL sumber tidak valid atau kosong")


    # -----------------------------------------------------
    # Penentuan status
    # -----------------------------------------------------

    if not relevan:

        status = "invalid"

    elif not cek_url(url):

        status = "invalid"

    elif masalah:

        status = "perlu_review"

    else:

        status = "valid"


    return status, "; ".join(masalah)


# =========================================================
# 5. PROSES VALIDASI SELURUH DATA
# =========================================================

def proses_validasi(df):

    hasil = []

    for _, row in df.iterrows():

        status, catatan = validasi_baris(row)

        data = row.to_dict()

        data["status_validasi"] = status

        data["catatan_validasi"] = catatan

        hasil.append(data)

    df_hasil = pd.DataFrame(hasil)

    return df_hasil


# =========================================================
# 6. PEMERIKSAAN DUPLIKASI
# =========================================================

def tandai_duplikasi(df):

    if df.empty:
        return df

    df = df.copy()

    df["judul_normalisasi"] = (
        df["judul"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.strip()
    )

    # Duplikat URL
    if "url" in df.columns:

        df["duplikat_url"] = (
            df["url"]
            .fillna("")
            .astype(str)
            .duplicated(keep="first")
        )

    else:

        df["duplikat_url"] = False


    # Duplikat judul
    df["duplikat_judul"] = (
        df["judul_normalisasi"]
        .duplicated(keep="first")
    )


    # Jika terindikasi duplikat, ubah valid menjadi review
    mask_duplikat = (
        df["duplikat_url"]
        | df["duplikat_judul"]
    )

    mask_valid_duplikat = (
        mask_duplikat
        & (df["status_validasi"] == "valid")
    )

    df.loc[
        mask_valid_duplikat,
        "status_validasi"
    ] = "perlu_review"


    # Tambahkan catatan duplikasi
    for idx in df.index[mask_duplikat]:

        catatan = str(
            df.at[idx, "catatan_validasi"]
        ).strip()

        if catatan in ["", "nan", "None"]:

            catatan = "Terindikasi duplikat"

        else:

            catatan += "; Terindikasi duplikat"

        df.at[idx, "catatan_validasi"] = catatan


    df.drop(
        columns=["judul_normalisasi"],
        inplace=True,
        errors="ignore"
    )

    return df


# =========================================================
# 7. MAIN PROGRAM
# =========================================================

def main():

    print("=" * 60)
    print("VALIDASI EVENT WISATA KULON PROGO")
    print("=" * 60)


    # -----------------------------------------------------
    # Cek input
    # -----------------------------------------------------

    input_path = Path(INPUT_FILE)

    if not input_path.exists():

        print(f"File tidak ditemukan: {INPUT_FILE}")

        print(
            "Jalankan filtering_event.py terlebih dahulu."
        )

        return


    # -----------------------------------------------------
    # Baca dataset kandidat
    # -----------------------------------------------------

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig"
    )

    print(f"Jumlah kandidat input: {len(df)}")


    if df.empty:

        print("Dataset kandidat kosong.")

        return


    # -----------------------------------------------------
    # Proses validasi
    # -----------------------------------------------------

    df_hasil = proses_validasi(df)


    # -----------------------------------------------------
    # Tandai duplikasi
    # -----------------------------------------------------

    df_hasil = tandai_duplikasi(df_hasil)


    # -----------------------------------------------------
    # Pisahkan hasil
    # -----------------------------------------------------

    df_valid = df_hasil[
        df_hasil["status_validasi"] == "valid"
    ].copy()

    df_review = df_hasil[
        df_hasil["status_validasi"] == "perlu_review"
    ].copy()

    df_invalid = df_hasil[
        df_hasil["status_validasi"] == "invalid"
    ].copy()


    # -----------------------------------------------------
    # Buat folder output
    # -----------------------------------------------------

    Path(OUTPUT_VALID).parent.mkdir(
        parents=True,
        exist_ok=True
    )


    # -----------------------------------------------------
    # Simpan hasil
    # -----------------------------------------------------

    df_valid.to_csv(
        OUTPUT_VALID,
        index=False,
        encoding="utf-8-sig"
    )

    df_review.to_csv(
        OUTPUT_REVIEW,
        index=False,
        encoding="utf-8-sig"
    )

    df_invalid.to_csv(
        OUTPUT_INVALID,
        index=False,
        encoding="utf-8-sig"
    )


    # -----------------------------------------------------
    # Ringkasan
    # -----------------------------------------------------

    print("-" * 60)

    print(f"Data valid         : {len(df_valid)}")

    print(f"Perlu review      : {len(df_review)}")

    print(f"Data invalid      : {len(df_invalid)}")

    print("-" * 60)

    print(f"Output valid      : {OUTPUT_VALID}")

    print(f"Output review     : {OUTPUT_REVIEW}")

    print(f"Output invalid    : {OUTPUT_INVALID}")

    print("=" * 60)


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()
