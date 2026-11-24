
from pathlib import Path
import shutil
import joblib

# =========================================================
# 1. PATH CONFIGURATION
# =========================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

EXPERIMENT_DIR = ROOT_DIR / "models" / "experiments" / "svm_balanced"
FINAL_DIR = ROOT_DIR / "models" / "final"

MODEL_SOURCE = EXPERIMENT_DIR / "linear_svm_balanced.pkl"

VECTORIZER_SOURCE = (
    ROOT_DIR
    / "data"
    / "processed"
    / "reviews"
    / "tfidf"
    / "tfidf_vectorizer.pkl"
)

MODEL_DEST = FINAL_DIR / "sentiment_model.pkl"
VECTORIZER_DEST = FINAL_DIR / "tfidf_vectorizer.pkl"


# =========================================================
# 2. CHECK FILE
# =========================================================

print("=" * 60)
print("FINAL MODEL SAVING")
print("=" * 60)

if not MODEL_SOURCE.exists():
    raise FileNotFoundError(f"Model tidak ditemukan: {MODEL_SOURCE}")

if not VECTORIZER_SOURCE.exists():
    raise FileNotFoundError(
        f"TF-IDF Vectorizer tidak ditemukan: {VECTORIZER_SOURCE}"
    )

print("\nFile sumber ditemukan.")


# =========================================================
# 3. LOAD AND VALIDATE
# =========================================================

print("\nMemvalidasi model dan vectorizer...")

model = joblib.load(MODEL_SOURCE)
vectorizer = joblib.load(VECTORIZER_SOURCE)

print(f"Model        : {type(model).__name__}")
print(f"Vectorizer   : {type(vectorizer).__name__}")


# =========================================================
# 4. CREATE FINAL DIRECTORY
# =========================================================

FINAL_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# 5. COPY MODEL AND VECTORIZER
# =========================================================

shutil.copy2(MODEL_SOURCE, MODEL_DEST)
shutil.copy2(VECTORIZER_SOURCE, VECTORIZER_DEST)


# =========================================================
# 6. VERIFY SAVED FILES
# =========================================================

saved_model = joblib.load(MODEL_DEST)
saved_vectorizer = joblib.load(VECTORIZER_DEST)

print("\nVerifikasi file final:")
print(f"Model tersimpan      : {MODEL_DEST.exists()}")
print(f"Vectorizer tersimpan : {VECTORIZER_DEST.exists()}")

print("\n" + "=" * 60)
print("MODEL FINAL BERHASIL DISIMPAN")
print("=" * 60)

print(f"\nModel      : {MODEL_DEST}")
print(f"Vectorizer : {VECTORIZER_DEST}")
