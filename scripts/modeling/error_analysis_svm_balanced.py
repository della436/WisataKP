
from pathlib import Path
import pandas as pd
import joblib

# =========================================================
# 1. PATH CONFIGURATION
# =========================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT_DIR / "data" / "processed" / "reviews" / "tfidf"
MODEL_DIR = ROOT_DIR / "models" / "experiments" / "svm_balanced"

X_TEST_TEXT_PATH = DATA_DIR / "X_test_text.csv"
Y_TEST_PATH = DATA_DIR / "y_test.csv"
X_TEST_TFIDF_PATH = DATA_DIR / "X_test_tfidf.pkl"

MODEL_PATH = MODEL_DIR / "linear_svm_balanced.pkl"

OUTPUT_ALL_PATH = MODEL_DIR / "error_analysis_all.csv"
OUTPUT_ERROR_PATH = MODEL_DIR / "error_analysis_misclassified.csv"
OUTPUT_SUMMARY_PATH = MODEL_DIR / "error_analysis_summary.csv"


# =========================================================
# 2. LOAD DATA
# =========================================================

print("=" * 60)
print("ERROR ANALYSIS - LINEAR SVM BALANCED")
print("=" * 60)

print("\nMemuat data test...")

X_test_text = pd.read_csv(X_TEST_TEXT_PATH)
y_test = pd.read_csv(Y_TEST_PATH)
X_test_tfidf = joblib.load(X_TEST_TFIDF_PATH)

# Mengambil kolom teks dan label aktual
texts = X_test_text["preprocessed_text"]
actual_labels = y_test["sentiment"]

print(f"Jumlah data test : {len(texts)}")
print(f"Jumlah label    : {len(actual_labels)}")


# =========================================================
# 3. LOAD MODEL
# =========================================================

print("\nMemuat model Linear SVM Balanced...")

model = joblib.load(MODEL_PATH)


# =========================================================
# 4. PREDICTION
# =========================================================

print("\nMelakukan prediksi...")

predicted_labels = model.predict(X_test_tfidf)


# =========================================================
# 5. COMBINE DATA
# =========================================================

print("\nMenggabungkan data...")

results = pd.DataFrame({
    "preprocessed_text": texts,
    "actual_sentiment": actual_labels,
    "predicted_sentiment": predicted_labels
})

# Membandingkan label aktual dan prediksi
results["status"] = results.apply(
    lambda row: "Correct"
    if row["actual_sentiment"] == row["predicted_sentiment"]
    else "Incorrect",
    axis=1
)


# =========================================================
# 6. FILTER MISCLASSIFIED DATA
# =========================================================

misclassified = results[
    results["actual_sentiment"] != results["predicted_sentiment"]
].copy()

# Menentukan jenis kesalahan
misclassified["error_type"] = (
    misclassified["actual_sentiment"]
    + " -> "
    + misclassified["predicted_sentiment"]
)


# =========================================================
# 7. ERROR SUMMARY
# =========================================================

error_summary = (
    misclassified.groupby("error_type")
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)


# =========================================================
# 8. SAVE RESULTS
# =========================================================

MODEL_DIR.mkdir(parents=True, exist_ok=True)

results.to_csv(OUTPUT_ALL_PATH, index=False)
misclassified.to_csv(OUTPUT_ERROR_PATH, index=False)
error_summary.to_csv(OUTPUT_SUMMARY_PATH, index=False)


# =========================================================
# 9. DISPLAY RESULTS
# =========================================================

total_data = len(results)
total_correct = (results["status"] == "Correct").sum()
total_errors = len(misclassified)

accuracy = total_correct / total_data if total_data > 0 else 0

print("\n" + "=" * 60)
print("HASIL ERROR ANALYSIS")
print("=" * 60)

print(f"Total data test       : {total_data}")
print(f"Prediksi benar       : {total_correct}")
print(f"Prediksi salah       : {total_errors}")
print(f"Accuracy             : {accuracy:.4f} ({accuracy * 100:.2f}%)")

print("\nJenis kesalahan prediksi:")
print(error_summary.to_string(index=False))

print("\n" + "=" * 60)
print("FILE BERHASIL DISIMPAN")
print("=" * 60)

print(f"\nSemua hasil     : {OUTPUT_ALL_PATH}")
print(f"Data kesalahan  : {OUTPUT_ERROR_PATH}")
print(f"Ringkasan error : {OUTPUT_SUMMARY_PATH}")

print("\nError Analysis selesai!")
