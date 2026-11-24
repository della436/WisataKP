import sys
from pathlib import Path
import joblib

# ==================================================
# 1. PATH CONFIGURATION
# ==================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

MODEL_DIR = ROOT_DIR / "models" / "final"

MODEL_PATH = MODEL_DIR / "sentiment_model.pkl"
VECTORIZER_PATH = MODEL_DIR / "tfidf_vectorizer.pkl"

# Memastikan root project dapat diakses saat import
sys.path.insert(0, str(ROOT_DIR))


# ==================================================
# 2. IMPORT PREPROCESSING
# ==================================================

from scripts.preprocessing.preprocessing import preprocessing


# ==================================================
# 3. LOAD MODEL & VECTORIZER
# ==================================================

def load_model():

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model tidak ditemukan: {MODEL_PATH}"
        )

    if not VECTORIZER_PATH.exists():
        raise FileNotFoundError(
            f"Vectorizer tidak ditemukan: {VECTORIZER_PATH}"
        )

    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)

    print("Model berhasil dimuat.")
    print("Vectorizer berhasil dimuat.")

    return model, vectorizer


# ==================================================
# 4. PREDICTION FUNCTION
# ==================================================

def predict_sentiment(text, model, vectorizer):

    # Preprocessing menggunakan pipeline yang sama
    cleaned_text = preprocessing(text)

    if not cleaned_text.strip():
        return "Tidak dapat diprediksi (teks kosong)"

    # Transformasi TF-IDF
    text_tfidf = vectorizer.transform([cleaned_text])

    # Prediksi sentimen
    prediction = model.predict(text_tfidf)

    return prediction[0]


# ==================================================
# 5. MAIN PROGRAM
# ==================================================

def main():

    print("=" * 60)
    print("WISATA KP - TESTING FINAL SENTIMENT MODEL")
    print("=" * 60)

    model, vectorizer = load_model()

    print("\nModel siap digunakan.")
    print("Masukkan ulasan wisata untuk memprediksi sentimen.")
    print("Ketik 'exit' untuk mengakhiri program.")

    while True:

        print("\n" + "-" * 60)

        review = input("Masukkan ulasan: ").strip()

        if review.lower() == "exit":
            print("\nProgram testing selesai.")
            break

        if not review:
            print("Ulasan tidak boleh kosong.")
            continue

        sentiment = predict_sentiment(
            review,
            model,
            vectorizer
        )

        print("\nHASIL PREDIKSI")
        print(f"Ulasan   : {review}")
        print(f"Sentimen : {sentiment}")


# ==================================================
# 6. RUN PROGRAM
# ==================================================

if __name__ == "__main__":
    main()