import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
from joblib import dump
from pyproj import Transformer
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_DIR / "data" / "processed" / "davao_training.gpkg"
MODEL_DIR = PROJECT_DIR / "models"
REPORT_PATH = PROJECT_DIR / "reports" / "davao_model_metrics.json"

TARGETS = ["flood_5yr", "flood_25yr", "flood_100yr"]
CATEGORICAL_FEATURES = ["highway"]
NUMERIC_FEATURES = [
    "log_length_m",
    "base_speed_kmh",
    "min_elevation",
    "midpoint_lon",
    "midpoint_lat",
    "elevation_range_m",
    "slope_percent",
]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
SOURCE_FEATURES = [feature for feature in FEATURES if feature != "log_length_m"]
SPATIAL_BLOCK_SIZE_M = 5_000
TEST_SIZE = 0.2
RANDOM_STATE = 42


def build_spatial_groups(data: pd.DataFrame) -> np.ndarray:
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32651", always_xy=True)
    x, y = to_utm.transform(data["midpoint_lon"].to_numpy(), data["midpoint_lat"].to_numpy())
    x_blocks = np.floor(np.asarray(x) / SPATIAL_BLOCK_SIZE_M).astype(np.int32)
    y_blocks = np.floor(np.asarray(y) / SPATIAL_BLOCK_SIZE_M).astype(np.int32)
    _, groups = np.unique(
        np.column_stack((x_blocks, y_blocks)),
        axis=0,
        return_inverse=True,
    )
    return groups


def make_model() -> Pipeline:
    preprocessing = ColumnTransformer(
        transformers=[
            ("numeric", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
            (
                "highway",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )
    classifier = RandomForestClassifier(
        n_estimators=120,
        max_depth=18,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=RANDOM_STATE,
    )
    return Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("classifier", classifier),
        ]
    )


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, y_probability: np.ndarray) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_probability)),
        "confusion_matrix_labels_0_1": confusion_matrix(
            y_true, y_pred, labels=[0, 1]
        ).tolist(),
    }


def main() -> None:
    data = pyogrio.read_dataframe(
        DEFAULT_DATASET,
        layer="road_segments",
        columns=[*SOURCE_FEATURES, "length_m", *TARGETS],
        read_geometry=False,
    )
    data["log_length_m"] = np.log1p(data.pop("length_m").clip(lower=0))
    features = data[FEATURES]
    groups = build_spatial_groups(data)

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )
    train_indices, test_indices = next(
        splitter.split(features, groups=groups)
    )
    test_groups = set(groups[test_indices])
    if test_groups.intersection(groups[train_indices]):
        raise RuntimeError("Spatial blocks were shared between train and test splits.")

    results = {
        "dataset": str(DEFAULT_DATASET),
        "rows": int(len(data)),
        "validation": {
            "method": "GroupShuffleSplit by 5 km UTM spatial blocks",
            "test_size_target": TEST_SIZE,
            "train_rows": int(len(train_indices)),
            "test_rows": int(len(test_indices)),
            "train_blocks": int(len(set(groups[train_indices]))),
            "test_blocks": int(len(test_groups)),
            "random_state": RANDOM_STATE,
        },
        "features": FEATURES,
        "scenarios": {},
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    for target in TARGETS:
        labels = data[target].to_numpy(dtype=np.int8)
        y_train = labels[train_indices]
        y_test = labels[test_indices]
        if np.unique(y_train).size != 2 or np.unique(y_test).size != 2:
            raise ValueError(
                f"{target} must have both classes in train and test partitions."
            )

        baseline = DummyClassifier(strategy="most_frequent")
        baseline.fit(features.iloc[train_indices], y_train)
        baseline_prediction = baseline.predict(features.iloc[test_indices])
        positive_class_index = int(np.flatnonzero(baseline.classes_ == 1)[0])
        baseline_probability = baseline.predict_proba(
            features.iloc[test_indices]
        )[:, positive_class_index]
        baseline_metrics = evaluate(y_test, baseline_prediction, baseline_probability)

        model = make_model()
        model.fit(features.iloc[train_indices], y_train)
        prediction = model.predict(features.iloc[test_indices])
        probability = model.predict_proba(features.iloc[test_indices])[:, 1]
        forest_metrics = evaluate(y_test, prediction, probability)
        forest_metrics["train_positive_rate"] = float(y_train.mean())
        forest_metrics["test_positive_rate"] = float(y_test.mean())
        results["scenarios"][target] = {
            "baseline_most_frequent": baseline_metrics,
            "random_forest": forest_metrics,
        }

        model.fit(features, labels)
        model_path = MODEL_DIR / f"{target}.joblib"
        dump(model, model_path)
        print(
            f"{target}: RF F1={forest_metrics['f1']:.3f} "
            f"(baseline={baseline_metrics['f1']:.3f}), "
            f"recall={forest_metrics['recall']:.3f}, "
            f"precision={forest_metrics['precision']:.3f}, "
            f"ROC-AUC={forest_metrics['roc_auc']:.3f}"
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Metrics saved to {REPORT_PATH}")
    print(f"Trained models saved to {MODEL_DIR}")


if __name__ == "__main__":
    main()
