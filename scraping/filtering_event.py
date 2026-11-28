
import pandas as pd
import re
from pathlib import Path

# =========================================================
# CONFIGURATION
# Jalankan script dari root project WisataKP
# =========================================================

INPUT_FILE = "data/events/event_wisata.csv"

OUTPUT_CANDIDATE = "data/events/event_candidates.csv"
OUTPUT_REJECTED = "data/events/event_rejected.csv"


# =========================================================
# 1. KEYWORD EVENT
# =========================================================

KEYWORDS_EVENT_KUAT = [
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
    "tuk tumuwuh", "gelar karya"
]


# =========================================================
# 2. KEYWORD KONTEKS EVENT
# =========================================================

KEYWORDS_KONTEKS = [
    "diselenggarakan", "dilaksanakan", "berlangsung",
    "digelar", "akan digelar", "akan berlangsung",
    "diadakan", "peserta", "pengunjung", "wisatawan",
    "memeriahkan", "meramaikan", "menampilkan",
    "rangkaian acara", "agenda", "atraksi",
    "pembukaan", "penutupan", "start", "finish",
    "kategori", "hadiah", "pendaftaran",
    "lokasi kegiatan", "panggung", "acara"
]


KEYWORDS_UMUM = [
    "event", "acara", "kegiatan", "perayaan",
    "peringatan", "tradisi", "hiburan", "musik",
    "tari", "budaya", "wisata"
]


# =========================================================
# 3. KEYWORD ADMINISTRATIF
# =========================================================

KEYWORDS_ADMINISTRATIF = [
    "rapat", "rapat koordinasi", "rakor",
    "evaluasi", "monitoring", "pemantauan",
    "pengawasan", "audiensi", "kunjungan kerja",
    "kunjungan dinas", "studi banding", "bimtek",
    "bimbingan teknis", "pelatihan pegawai",
    "orientasi pegawai", "pelantikan",
    "serah terima jabatan", "penyerahan bantuan",
    "penandatanganan", "sosialisasi",
    "administrasi", "koordinasi internal",
    "penyusunan laporan", "penyusunan program",
    "forum perangkat daerah", "forum opd"
]


# =========================================================
# 4. KEYWORD AKTIVITAS WISATA BIASA
# =========================================================

KEYWORDS_AKTIVITAS_BIASA = [
    "memadati", "ramai dikunjungi",
    "jumlah pengunjung", "kunjungan wisatawan",
    "wisatawan meningkat", "pengunjung meningkat",
    "libur panjang", "libur lebaran",
    "libur natal", "libur tahun baru",
    "aktivitas wisata", "berwisata", "berlibur"
]


# =========================================================
# 5. KEYWORD KATEGORI EVENT
# =========================================================

KATEGORI_KEYWORDS = {
    "budaya": [
        "budaya", "tradisi", "adat", "rasulan",
        "merti desa", "grebeg", "kirab", "wayang",
        "karawitan"
    ],

    "seni": [
        "seni", "pentas", "pertunjukan", "pagelaran",
        "tari", "bendrongan", "gamelan"
    ],

    "kuliner": [
        "kuliner", "makanan", "masakan", "kopi",
        "bazar makanan"
    ],

    "olahraga": [
        "maraton", "marathon", "half marathon",
        "fun run", "jalan sehat", "race",
        "turnamen", "kejuaraan", "sport"
    ],

    "alam dan lingkungan": [
        "penanaman", "bibit", "lingkungan",
        "bersih desa", "sedekah bumi"
    ],

    "pameran dan perdagangan": [
        "pameran", "bazar", "bazaar",
        "travel fair", "pasar rakyat"
    ],

    "hiburan": [
        "konser", "musik", "festival", "karnaval",
        "parade", "lomba", "kompetisi",
        "camping", "glamping", "outbound"
    ]
}


# =========================================================
# 6. UTILITAS NORMALISASI TEKS
# =========================================================

def normalisasi_teks(teks):
    if pd.isna(teks):
        return ""

    teks = str(teks).lower()
    teks = re.sub(r"\s+", " ", teks)

    return teks.strip()


def cari_keyword(teks, daftar_keyword):
    ditemukan = []

    for keyword in daftar_keyword:
        pattern = (
            r"(?<!\w)"
            + re.escape(keyword.lower())
            + r"(?!\w)"
        )

        if re.search(pattern, teks):
            ditemukan.append(keyword)

    return ditemukan


def bersihkan_judul(judul):
    """
    Menggunakan judul artikel sebagai nama sementara.
    Tidak membuat nama event baru.
    """

    if pd.isna(judul):
        return ""

    hasil = str(judul).strip()

    hasil = hasil.replace("&ndash;", "–")
    hasil = hasil.replace("&mdash;", "—")
    hasil = hasil.replace("&nbsp;", " ")
    hasil = hasil.replace("&amp;", "&")
    hasil = hasil.replace("&quot;", '"')
    hasil = hasil.replace("&#39;", "'")

    hasil = re.sub(r"\s+", " ", hasil).strip()

    hasil = re.sub(
        r"^(kulon\s+progo\s*[-–:]\s*)",
        "",
        hasil,
        flags=re.I
    )

    return hasil


# =========================================================
# 7. EKSTRAKSI TANGGAL EVENT
# Tidak menggunakan tanggal publikasi artikel
# =========================================================

MONTH_PATTERN = (
    r"januari|jan|februari|feb|maret|mar|"
    r"april|apr|mei|juni|jun|juli|jul|"
    r"agustus|agu|agust|september|sep|"
    r"oktober|okt|november|nov|desember|des"
)

DATE_PATTERNS = [
    rf"\b\d{{1,2}}\s+(?:{MONTH_PATTERN})\s+\d{{4}}\b",

    rf"\b(?:{MONTH_PATTERN})\s+\d{{1,2}},?\s+\d{{4}}\b",

    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b",

    rf"\b\d{{1,2}}\s+(?:{MONTH_PATTERN})\b"
]


def ekstrak_tanggal_event(teks):
    """
    Mengambil tanggal yang tertulis secara eksplisit
    dalam judul atau ringkasan.

    Jika tidak ditemukan, hasil dikosongkan.
    """

    for pattern in DATE_PATTERNS:
        match = re.search(pattern, teks, flags=re.I)

        if match:
            return match.group(0).strip()

    return ""


# =========================================================
# 8. EKSTRAKSI LOKASI EVENT
# =========================================================

LOCATION_PATTERNS = [
    r"(?:bertempat\s+di|berlokasi\s+di|"
    r"lokasi(?:\s+acara|\s+kegiatan)?\s*[:=]\s*|"
    r"digelar\s+di|diselenggarakan\s+di|"
    r"dilaksanakan\s+di|berlangsung\s+di)\s+"
    r"([^.;\n]{3,100})",

    r"\bdi\s+((?:Pantai|Waduk|Lapangan|Alun[- ]Alun|"
    r"Gua|Goa|Hutan|Taman|Desa|Kalurahan|Kecamatan|"
    r"Kawasan|Amphitheatre|Amphiteater|Gedung|Stadion|"
    r"Pasar|Embung|Bukit|Puncak|Boro|Wates|Nanggulan)"
    r"[^.;\n]{0,80})"
]


def ekstrak_lokasi_event(teks):
    """
    Mengambil lokasi berdasarkan pola penyebutan
    tempat dalam artikel.

    Lokasi hasil ekstraksi belum dianggap valid
    sebelum pemeriksaan.
    """

    for pattern in LOCATION_PATTERNS:
        match = re.search(pattern, teks, flags=re.I)

        if match:
            lokasi = match.group(1).strip(" ,:-")

            lokasi = re.split(
                r"\b(?:yang|dengan|serta|dan|pada|sebagai|untuk)\b",
                lokasi,
                maxsplit=1,
                flags=re.I
            )[0]

            lokasi = re.sub(
                r"\s+",
                " ",
                lokasi
            ).strip(" ,:-")

            if lokasi:
                return lokasi

    return ""


# =========================================================
# 9. EKSTRAKSI KATEGORI EVENT
# =========================================================

def ekstrak_kategori(teks):
    teks_norm = normalisasi_teks(teks)

    kategori_ditemukan = []

    for kategori, keywords in KATEGORI_KEYWORDS.items():
        if cari_keyword(teks_norm, keywords):
            kategori_ditemukan.append(kategori)

    if kategori_ditemukan:
        return ", ".join(kategori_ditemukan)

    return "belum_teridentifikasi"


# =========================================================
# 10. FILTERING EVENT
# =========================================================

def proses_filtering(judul, ringkasan):

    judul_norm = normalisasi_teks(judul)
    ringkasan_norm = normalisasi_teks(ringkasan)

    teks = f"{judul_norm} {ringkasan_norm}".strip()

    kw_judul = cari_keyword(
        judul_norm,
        KEYWORDS_EVENT_KUAT
    )

    kw_event = cari_keyword(
        teks,
        KEYWORDS_EVENT_KUAT
    )

    kw_konteks = cari_keyword(
        teks,
        KEYWORDS_KONTEKS
    )

    kw_umum = cari_keyword(
        teks,
        KEYWORDS_UMUM
    )

    kw_admin_judul = cari_keyword(
        judul_norm,
        KEYWORDS_ADMINISTRATIF
    )

    kw_admin_artikel = cari_keyword(
        teks,
        KEYWORDS_ADMINISTRATIF
    )

    kw_aktivitas = cari_keyword(
        teks,
        KEYWORDS_AKTIVITAS_BIASA
    )

    # -----------------------------------------------------
    # Aturan dasar filtering
    # -----------------------------------------------------

    lolos = (
        bool(kw_judul)
        or (
            bool(kw_event)
            and len(kw_konteks) >= 2
        )
    )

    if kw_judul:
        alasan = "Keyword event kuat ditemukan pada judul"

    elif lolos:
        alasan = "Keyword event dan konteks kegiatan ditemukan"

    else:
        alasan = "Tidak memenuhi indikator event"


    # -----------------------------------------------------
    # Pengecualian berita administratif
    # -----------------------------------------------------

    if lolos and kw_admin_judul and not kw_judul:

        lolos = False

        alasan = "Dikecualikan karena dominan administratif"


    # -----------------------------------------------------
    # Pengecualian aktivitas wisata biasa
    # -----------------------------------------------------

    if lolos and kw_aktivitas and not kw_judul:

        lolos = False

        alasan = (
            "Dikecualikan karena membahas aktivitas "
            "atau keramaian kunjungan biasa"
        )


    # -----------------------------------------------------
    # Hasil filtering
    # -----------------------------------------------------

    hasil = {
        "keyword_judul": ", ".join(kw_judul),

        "keyword_event_ditemukan": ", ".join(kw_event),

        "keyword_konteks": ", ".join(kw_konteks),

        "keyword_umum": ", ".join(kw_umum),

        "keyword_administratif": ", ".join(kw_admin_artikel),

        "keyword_aktivitas_biasa": ", ".join(kw_aktivitas),

        "jumlah_keyword_event": len(kw_event),

        "alasan_filtering": alasan,

        "status_filtering": (
            "kandidat_event"
            if lolos
            else "ditolak"
        )
    }

    return lolos, hasil, teks


# =========================================================
# 11. EKSTRAKSI INFORMASI EVENT
# =========================================================

def proses_ekstraksi(judul, ringkasan, teks):

    nama_event = bersihkan_judul(judul)

    tanggal_event = ekstrak_tanggal_event(teks)

    lokasi_event = ekstrak_lokasi_event(
        f"{judul} {ringkasan}"
    )

    kategori_event = ekstrak_kategori(teks)

    deskripsi_event = (
        str(ringkasan).strip()
        if not pd.isna(ringkasan)
        else ""
    )

    # -----------------------------------------------------
    # Pemeriksaan kelengkapan ekstraksi
    # -----------------------------------------------------

    catatan = []

    if not tanggal_event:
        catatan.append("tanggal_event_tidak_ditemukan")

    if not lokasi_event:
        catatan.append("lokasi_event_tidak_ditemukan")

    if kategori_event == "belum_teridentifikasi":
        catatan.append("kategori_perlu_verifikasi")

    if "..." in nama_event or "…" in nama_event:
        catatan.append("judul_event_mungkin_terpotong")

    if not deskripsi_event:
        catatan.append("deskripsi_tidak_tersedia")


    if catatan:
        status_ekstraksi = "perlu_verifikasi"
        catatan_ekstraksi = "; ".join(catatan)

    else:
        # Data tetap perlu pemeriksaan manusia,
        # walaupun field ekstraksi berhasil ditemukan.
        status_ekstraksi = "perlu_verifikasi"
        catatan_ekstraksi = "hasil_rule_based_perlu_diperiksa"


    return {
        "nama_event": nama_event,

        "tanggal_event_ekstrak": tanggal_event,

        "lokasi_event_ekstrak": lokasi_event,

        "kategori_event_ekstrak": kategori_event,

        "deskripsi_event": deskripsi_event,

        "status_ekstraksi": status_ekstraksi,

        "catatan_ekstraksi": catatan_ekstraksi
    }


# =========================================================
# 12. PROSES SELURUH ARTIKEL
# FILTERING + EKSTRAKSI
# =========================================================

def proses_artikel(df):

    kandidat = []
    ditolak = []

    for _, row in df.iterrows():

        judul_asli = row.get("judul", "")

        ringkasan_asli = row.get("ringkasan", "")


        # =================================================
        # FILTERING
        # =================================================

        lolos, hasil_filtering, teks = proses_filtering(
            judul_asli,
            ringkasan_asli
        )


        # Data artikel asli dipertahankan
        data = row.to_dict()

        data.update(hasil_filtering)


        # =================================================
        # EKSTRAKSI HANYA UNTUK ARTIKEL KANDIDAT
        # =================================================

        if lolos:

            hasil_ekstraksi = proses_ekstraksi(
                judul_asli,
                ringkasan_asli,
                teks
            )

            data.update(hasil_ekstraksi)

            kandidat.append(data)

        else:

            ditolak.append(data)


    df_kandidat = pd.DataFrame(kandidat)

    df_ditolak = pd.DataFrame(ditolak)

    return df_kandidat, df_ditolak


# =========================================================
# 13. MAIN PROGRAM
# =========================================================

def main():

    print("=" * 65)

    print("FILTERING & EKSTRAKSI EVENT WISATA KULON PROGO")

    print("=" * 65)


    # -----------------------------------------------------
    # Periksa file input
    # -----------------------------------------------------

    input_path = Path(INPUT_FILE)

    if not input_path.exists():

        print(f"File input tidak ditemukan: {INPUT_FILE}")

        print("Pastikan script dijalankan dari root project WisataKP.")

        return


    # -----------------------------------------------------
    # Baca dataset
    # -----------------------------------------------------

    df = pd.read_csv(
        input_path,
        encoding="utf-8-sig"
    )

    print(f"Jumlah artikel awal : {len(df)}")


    if df.empty:

        print("Data input kosong.")

        return


    # -----------------------------------------------------
    # Proses filtering dan ekstraksi
    # -----------------------------------------------------

    df_kandidat, df_ditolak = proses_artikel(df)


    # -----------------------------------------------------
    # Hapus duplikat berdasarkan URL
    # -----------------------------------------------------

    if "url" in df_kandidat.columns and not df_kandidat.empty:

        df_kandidat = df_kandidat.drop_duplicates(
            subset="url"
        )


    if "url" in df_ditolak.columns and not df_ditolak.empty:

        df_ditolak = df_ditolak.drop_duplicates(
            subset="url"
        )


    # -----------------------------------------------------
    # Siapkan folder output
    # -----------------------------------------------------

    Path(OUTPUT_CANDIDATE).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    Path(OUTPUT_REJECTED).parent.mkdir(
        parents=True,
        exist_ok=True
    )


    # -----------------------------------------------------
    # Simpan hasil
    # -----------------------------------------------------

    df_kandidat.to_csv(
        OUTPUT_CANDIDATE,
        index=False,
        encoding="utf-8-sig"
    )

    df_ditolak.to_csv(
        OUTPUT_REJECTED,
        index=False,
        encoding="utf-8-sig"
    )


    # -----------------------------------------------------
    # Ringkasan hasil
    # -----------------------------------------------------

    print("-" * 65)

    print(f"Artikel kandidat event : {len(df_kandidat)}")

    print(f"Artikel ditolak       : {len(df_ditolak)}")

    print(f"Output kandidat       : {OUTPUT_CANDIDATE}")

    print(f"Output ditolak        : {OUTPUT_REJECTED}")

    print("=" * 65)


    # -----------------------------------------------------
    # Preview hasil kandidat
    # -----------------------------------------------------

    if not df_kandidat.empty:

        preview_cols = [
            "judul",
            "nama_event",
            "tanggal_event_ekstrak",
            "lokasi_event_ekstrak",
            "kategori_event_ekstrak",
            "status_ekstraksi"
        ]

        preview_cols = [
            col for col in preview_cols
            if col in df_kandidat.columns
        ]

        print("\nContoh hasil kandidat:\n")

        print(
            df_kandidat[preview_cols]
            .head(10)
            .to_string(index=False)
        )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    main()
