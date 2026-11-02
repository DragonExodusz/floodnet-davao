from pathlib import Path

import numpy as np
import pyogrio
from joblib import load

from train_models import FEATURES, MODEL_DIR, SOURCE_FEATURES, TARGETS


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_DIR / "data" / "processed" / "davao_training.gpkg"
OUTPUT = PROJECT_DIR / "data" / "processed" / "davao_predictions.gpkg"


def main() -> None:
    if not DEFAULT_DATASET.is_file():
        raise FileNotFoundError(
            f"Training data not found: {DEFAULT_DATASET}. "
            "Run scripts/build_training_data.py first."
        )

    missing_models = [MODEL_DIR / f"{target}.joblib" for target in TARGETS]
    missing_models = [path for path in missing_models if not path.is_file()]
    if missing_models:
        raise FileNotFoundError(
            "Train models before generating map predictions. Missing: "
            + ", ".join(str(path) for path in missing_models)
        )

    data = pyogrio.read_dataframe(
        DEFAULT_DATASET,
        layer="road_segments",
        columns=["u", "v", "key", *SOURCE_FEATURES, "length_m", *TARGETS],
    )
    data["log_length_m"] = np.log1p(data["length_m"].clip(lower=0))
    features = data[FEATURES]
    for target in TARGETS:
        model = load(MODEL_DIR / f"{target}.joblib")
        risk = model.predict_proba(features)[:, 1]
        data[f"risk_{target.removeprefix('flood_')}"] = risk.astype("float32")

    output_columns = [
        "u",
        "v",
        "key",
        "highway",
        "length_m",
        *[f"risk_{target.removeprefix('flood_')}" for target in TARGETS],
        "geometry",
    ]
    output = data[output_columns].copy()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()
    pyogrio.write_dataframe(
        output,
        OUTPUT,
        layer="road_predictions",
        driver="GPKG",
    )

    print(f"Saved predictions for {len(output):,} road segments to {OUTPUT}")
    print("Predicted risk columns: risk_5yr, risk_25yr, risk_100yr")


if __name__ == "__main__":
    main()
