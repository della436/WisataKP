
import pandas as pd
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer

# =========================
# PATH DATA
# =========================
DATA_PATH = "crawler_destinasi/data/processed/reviews/wisata_kp_reviews_labeled.csv"

OUTPUT_DIR = Path("crawler_destinasi/data/processed/reviews/tfidf")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# LOAD DATA
# =========================
df = pd.read_csv(DATA_PATH)

# Menggunakan teks hasil preprocessing
df = df.dropna(subset=["preprocessed_text", "sentiment"])
df = df[df["preprocessed_text"].astype(str).str.strip() != ""]

X = df["preprocessed_text"].astype(str)
y = df["sentiment"].astype(str)

print("Jumlah data:", len(df))
print("\nDistribusi sentimen:")
print(y.value_counts())

# =========================
# SPLIT DATA
# =========================
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

print("\nJumlah data training:", len(X_train))
print("Jumlah data testing:", len(X_test))

# =========================
# TF-IDF
# =========================
tfidf = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1, 2)
)

X_train_tfidf = tfidf.fit_transform(X_train)
X_test_tfidf = tfidf.transform(X_test)

print("\n===== HASIL TF-IDF =====")
print("Shape training:", X_train_tfidf.shape)
print("Shape testing:", X_test_tfidf.shape)
print("Jumlah fitur:", len(tfidf.get_feature_names_out()))

# =========================
# SIMPAN HASIL
# =========================
joblib.dump(tfidf, OUTPUT_DIR / "tfidf_vectorizer.pkl")
joblib.dump(X_train_tfidf, OUTPUT_DIR / "X_train_tfidf.pkl")
joblib.dump(X_test_tfidf, OUTPUT_DIR / "X_test_tfidf.pkl")

y_train.to_csv(OUTPUT_DIR / "y_train.csv", index=False)
y_test.to_csv(OUTPUT_DIR / "y_test.csv", index=False)

X_train.to_csv(OUTPUT_DIR / "X_train_text.csv", index=False)
X_test.to_csv(OUTPUT_DIR / "X_test_text.csv", index=False)

print("\nSemua hasil TF-IDF berhasil disimpan.")
print("Lokasi:", OUTPUT_DIR)
