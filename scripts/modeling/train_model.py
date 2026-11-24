
# ==========================================
# TRAIN MODEL SENTIMENT - WISATA KP
# ==========================================

from pathlib import Path
import json
import joblib

import pandas as pd

from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)

# ==========================================
# 1. PATH CONFIGURATION
# ==========================================

ROOT_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT_DIR / "data" / "processed" / "reviews" / "tfidf"
MODEL_DIR = ROOT_DIR / "models"

MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# 2. LOAD DATA
# ==========================================

def load_data():

    print("=" * 60)
    print("MEMUAT DATA TF-IDF")
    print("=" * 60)

    required_files = [
        "X_train_tfidf.pkl",
        "X_test_tfidf.pkl",
        "y_train.csv",
        "y_test.csv"
    ]

    # Periksa ketersediaan file
    for filename in required_files:
        file_path = DATA_DIR / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"File tidak ditemukan: {file_path}"
            )

    # Load matriks TF-IDF menggunakan joblib
    X_train = joblib.load(DATA_DIR / "X_train_tfidf.pkl")
    X_test = joblib.load(DATA_DIR / "X_test_tfidf.pkl")

    # Load label
    y_train = pd.read_csv(DATA_DIR / "y_train.csv").squeeze()
    y_test = pd.read_csv(DATA_DIR / "y_test.csv").squeeze()

    # Informasi dataset
    print(f"Jumlah data training : {X_train.shape[0]}")
    print(f"Jumlah data testing  : {X_test.shape[0]}")
    print(f"Jumlah fitur        : {X_train.shape[1]}")

    print("\nDistribusi label training:")
    print(y_train.value_counts())

    print("\nDistribusi label testing:")
    print(y_test.value_counts())

    return X_train, X_test, y_train, y_test


# ==========================================
# 3. DEFINE MODELS
# ==========================================

def get_models():

    models = {
        "Naive Bayes": MultinomialNB(),

        "Logistic Regression": LogisticRegression(
            max_iter=1000,
            random_state=42
        ),

        "Linear SVM": LinearSVC(
            random_state=42
        )
    }

    return models


# ==========================================
# 4. TRAIN AND EVALUATE
# ==========================================

def train_and_evaluate(
    X_train,
    X_test,
    y_train,
    y_test
):

    models = get_models()

    results = []
    reports = {}

    for name, model in models.items():

        print("\n" + "=" * 60)
        print(f"TRAINING MODEL: {name}")
        print("=" * 60)

        # ----------------------------------
        # TRAINING
        # ----------------------------------

        model.fit(X_train, y_train)

        # ----------------------------------
        # PREDICTION
        # ----------------------------------

        y_pred = model.predict(X_test)

        # ----------------------------------
        # EVALUATION
        # ----------------------------------

        accuracy = accuracy_score(y_test, y_pred)

        precision_macro = precision_score(
            y_test,
            y_pred,
            average="macro",
            zero_division=0
        )

        recall_macro = recall_score(
            y_test,
            y_pred,
            average="macro",
            zero_division=0
        )

        f1_macro = f1_score(
            y_test,
            y_pred,
            average="macro",
            zero_division=0
        )

        f1_weighted = f1_score(
            y_test,
            y_pred,
            average="weighted",
            zero_division=0
        )

        # ----------------------------------
        # SAVE METRICS
        # ----------------------------------

        results.append({
            "Model": name,
            "Accuracy": accuracy,
            "Precision Macro": precision_macro,
            "Recall Macro": recall_macro,
            "F1 Macro": f1_macro,
            "F1 Weighted": f1_weighted
        })

        # ----------------------------------
        # CLASSIFICATION REPORT
        # ----------------------------------

        report = classification_report(
            y_test,
            y_pred,
            zero_division=0,
            output_dict=True
        )

        reports[name] = report

        # ----------------------------------
        # SAVE MODEL
        # ----------------------------------

        model_filename = (
            name.lower().replace(" ", "_") + ".pkl"
        )

        model_path = MODEL_DIR / model_filename

        joblib.dump(model, model_path)

        # ----------------------------------
        # CONFUSION MATRIX
        # ----------------------------------

        cm = confusion_matrix(
            y_test,
            y_pred,
            labels=model.classes_
        )

        cm_df = pd.DataFrame(
            cm,
            index=model.classes_,
            columns=model.classes_
        )

        cm_filename = (
            f"confusion_matrix_"
            f"{name.lower().replace(' ', '_')}.csv"
        )

        cm_df.to_csv(MODEL_DIR / cm_filename)

        # ----------------------------------
        # DISPLAY RESULTS
        # ----------------------------------

        print(f"\nAccuracy       : {accuracy:.4f}")
        print(f"Precision Macro: {precision_macro:.4f}")
        print(f"Recall Macro   : {recall_macro:.4f}")
        print(f"F1 Macro      : {f1_macro:.4f}")
        print(f"F1 Weighted   : {f1_weighted:.4f}")

        print("\nClassification Report:")
        print(
            classification_report(
                y_test,
                y_pred,
                zero_division=0
            )
        )

        print(f"Model tersimpan: {model_path}")

    return results, reports


# ==========================================
# 5. SAVE COMPARISON RESULTS
# ==========================================

def save_results(results, reports):

    results_df = pd.DataFrame(results)

    # Ranking berdasarkan Macro F1-Score
    results_df = results_df.sort_values(
        by="F1 Macro",
        ascending=False
    )

    # Simpan perbandingan model
    comparison_path = MODEL_DIR / "model_comparison.csv"

    results_df.to_csv(
        comparison_path,
        index=False
    )

    # Simpan classification report
    report_path = MODEL_DIR / "classification_reports.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            reports,
            f,
            indent=4,
            ensure_ascii=False
        )

    # --------------------------------------
    # DISPLAY FINAL COMPARISON
    # --------------------------------------

    print("\n" + "=" * 60)
    print("PERBANDINGAN PERFORMA MODEL")
    print("=" * 60)

    print(
        results_df.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}"
        )
    )

    # Model terbaik berdasarkan Macro F1
    best_model = results_df.iloc[0]

    print("\n" + "=" * 60)
    print("MODEL TERBAIK")
    print("=" * 60)

    print(f"Model      : {best_model['Model']}")
    print(f"Accuracy   : {best_model['Accuracy']:.4f}")
    print(f"Macro F1  : {best_model['F1 Macro']:.4f}")

    print("\nHasil evaluasi tersimpan di:")
    print(MODEL_DIR)


# ==========================================
# 6. MAIN PROGRAM
# ==========================================

def main():

    # Load dataset
    X_train, X_test, y_train, y_test = load_data()

    # Training dan evaluasi model
    results, reports = train_and_evaluate(
        X_train,
        X_test,
        y_train,
        y_test
    )

    # Simpan hasil evaluasi
    save_results(
        results,
        reports
    )


# ==========================================
# 7. EXECUTION
# ==========================================

if __name__ == "__main__":
    main()
