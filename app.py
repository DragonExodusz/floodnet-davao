import json
from pathlib import Path

import geopandas as gpd
import pyogrio
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


PROJECT_DIR = Path(__file__).resolve().parent
WEB_DIR = PROJECT_DIR / "web"
PREDICTIONS = PROJECT_DIR / "data" / "processed" / "davao_predictions.gpkg"
MAX_FEATURES = 50_000
MIN_ZOOM = 13
SCENARIO_COLUMNS = {
    "5yr": "risk_5yr",
    "25yr": "risk_25yr",
    "100yr": "risk_100yr",
}

app = FastAPI(title="FloodNet Davao", docs_url=None, redoc_url=None)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    if not PREDICTIONS.is_file():
        return {"status": "needs_predictions"}
    return {"status": "ok"}


@app.get("/api/roads")
def roads(
    bbox: str = Query(description="west,south,east,north in WGS 84"),
    scenario: str = Query(pattern="^(5yr|25yr|100yr)$"),
    zoom: int = Query(ge=0, le=22),
) -> dict:
    if zoom < MIN_ZOOM:
        raise HTTPException(
            status_code=400,
            detail=f"Zoom in to level {MIN_ZOOM} or closer to load road segments.",
        )
    if not PREDICTIONS.is_file():
        raise HTTPException(
            status_code=503,
            detail="Predictions are not ready. Run scripts/predict_map.py first.",
        )

    try:
        west, south, east, north = (float(value) for value in bbox.split(","))
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="bbox must contain four comma-separated numbers.",
        ) from error

    if (
        not all(map(lambda value: -180 <= value <= 180, (west, east)))
        or not all(map(lambda value: -90 <= value <= 90, (south, north)))
        or west >= east
        or south >= north
    ):
        raise HTTPException(
            status_code=400,
            detail="bbox must be a valid west,south,east,north WGS 84 extent.",
        )

    try:
        features = pyogrio.read_dataframe(
            PREDICTIONS,
            layer="road_predictions",
            bbox=(west, south, east, north),
            columns=["u", "v", "key", "highway", "length_m", *SCENARIO_COLUMNS.values()],
        )
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read the prediction map data: {error}",
        ) from error

    if len(features) > MAX_FEATURES:
        raise HTTPException(
            status_code=413,
            detail="Too many roads in this view. Zoom in closer to see the predictions.",
        )

    risk_column = SCENARIO_COLUMNS[scenario]
    features["risk"] = features[risk_column].astype(float)
    features["segment_id"] = (
        features["u"].astype(str)
        + "-"
        + features["v"].astype(str)
        + "-"
        + features["key"].astype(str)
    )
    features = features[["segment_id", "highway", "length_m", "risk", "geometry"]]
    collection = json.loads(features.to_json(drop_id=True, na="null"))
    return {
        "type": "FeatureCollection",
        "scenario": scenario,
        "count": len(collection["features"]),
        "features": collection["features"],
    }


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
