
# ==========================================
# EXPERIMENT - LINEAR SVM BALANCED
# WISATA KP
# ==========================================

from pathlib import Path
import json
import joblib
import pandas as pd

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
EXPERIMENT_DIR = MODEL_DIR / "experiments" / "svm_balanced"

EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# 2. LOAD DATA
# ==========================================

def load_data():

    print("=" * 60)
    print("MEMUAT DATA TF-IDF")
    print("=" * 60)

    X_train = joblib.load(DATA_DIR / "X_train_tfidf.pkl")
    X_test = joblib.load(DATA_DIR / "X_test_tfidf.pkl")

    y_train = pd.read_csv(DATA_DIR / "y_train.csv").squeeze()
    y_test = pd.read_csv(DATA_DIR / "y_test.csv").squeeze()

    print(f"Data training : {X_train.shape[0]}")
    print(f"Data testing : {X_test.shape[0]}")
    print(f"Jumlah fitur : {X_train.shape[1]}")

    return X_train, X_test, y_train, y_test


# ==========================================
# 3. DEFINE EXPERIMENT MODELS
# ==========================================

def get_models():

    models = {

        "Linear SVM Baseline": LinearSVC(
            random_state=42
        ),

        "Linear SVM Balanced": LinearSVC(
            class_weight="balanced",
            random_state=42
        )

    }

    return models


# ==========================================
# 4. TRAIN AND EVALUATE MODELS
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
        print(f"TRAINING: {name}")
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

        model_path = EXPERIMENT_DIR / model_filename

        joblib.dump(model, model_path)

        # ----------------------------------
        # SAVE CONFUSION MATRIX
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
            name.lower().replace(" ", "_")
            + "_confusion_matrix.csv"
        )

        cm_df.to_csv(EXPERIMENT_DIR / cm_filename)

        # ----------------------------------
        # SAVE METRICS
        # ----------------------------------

        results.append({
            "Model": name,
            "Accuracy": accuracy,
            "Precision Macro": precision_macro,
            "Recall Macro": recall_macro,
            "F1 Macro": f1_macro,
            "F1 Weighted": f1_weighted,
            "Negative Recall": report.get("Negative", {}).get("recall", 0),
            "Neutral Recall": report.get("Neutral", {}).get("recall", 0),
            "Positive Recall": report.get("Positive", {}).get("recall", 0)
        })

        # ----------------------------------
        # DISPLAY
        # ----------------------------------

        print(f"\nAccuracy        : {accuracy:.4f}")
        print(f"Precision Macro : {precision_macro:.4f}")
        print(f"Recall Macro    : {recall_macro:.4f}")
        print(f"F1 Macro       : {f1_macro:.4f}")
        print(f"F1 Weighted    : {f1_weighted:.4f}")

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
# 5. SAVE EXPERIMENT RESULTS
# ==========================================

def save_results(results, reports):

    results_df = pd.DataFrame(results)

    results_df = results_df.sort_values(
        by="F1 Macro",
        ascending=False
    )

    # --------------------------------------
    # SAVE COMPARISON
    # --------------------------------------

    comparison_path = (
        EXPERIMENT_DIR / "svm_balanced_comparison.csv"
    )

    results_df.to_csv(
        comparison_path,
        index=False
    )

    # --------------------------------------
    # SAVE REPORT
    # --------------------------------------

    report_path = (
        EXPERIMENT_DIR / "classification_reports.json"
    )

    with open(report_path, "w", encoding="utf-8") as f:

        json.dump(
            reports,
            f,
            indent=4,
            ensure_ascii=False
        )

    # --------------------------------------
    # DISPLAY COMPARISON
    # --------------------------------------

    print("\n" + "=" * 60)
    print("PERBANDINGAN LINEAR SVM")
    print("=" * 60)

    print(
        results_df.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}"
        )
    )

    print("\nHasil eksperimen tersimpan di:")
    print(EXPERIMENT_DIR)


# ==========================================
# 6. MAIN PROGRAM
# ==========================================

def main():

    X_train, X_test, y_train, y_test = load_data()

    results, reports = train_and_evaluate(
        X_train,
        X_test,
        y_train,
        y_test
    )

    save_results(
        results,
        reports
    )


# ==========================================
# 7. EXECUTION
# ==========================================

if __name__ == "__main__":
    main()
