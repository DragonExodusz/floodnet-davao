import argparse
from pathlib import Path

import numpy as np
import pyogrio


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_DIR.parent / "floodnetData" / "data"
DEFAULT_OUTPUT = PROJECT_DIR / "data" / "processed" / "davao_training.gpkg"
TARGETS = ["flood_5yr", "flood_25yr", "flood_100yr"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Metro Davao road-segment classification dataset."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing the source boundaries, network, flood, and elevation data.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output GeoPackage path.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the output file if it already exists.",
    )
    return parser.parse_args()


def build_training_data(data_dir: Path):
    network = data_dir / "network" / "davao.gpkg"
    edges = pyogrio.read_dataframe(network, layer="edges")
    edges = edges.loc[edges["in_metro"].fillna(False)].copy()

    nodes = pyogrio.read_dataframe(
        network,
        layer="nodes",
        columns=["osmid", "elevation"],
        read_geometry=False,
    ).set_index("osmid")
    node_elevation = nodes["elevation"]
    elevation_u = edges["u"].map(node_elevation)
    elevation_v = edges["v"].map(node_elevation)

    projected_geometry = edges.geometry.to_crs(edges.estimate_utm_crs())
    midpoint = projected_geometry.interpolate(0.5, normalized=True).to_crs(edges.crs)
    elevation_range = (elevation_v - elevation_u).abs()
    features = edges[
        [
            "u",
            "v",
            "key",
            "highway",
            "length_m",
            "base_speed_kmh",
            "min_elevation",
            *TARGETS,
        ]
    ].copy()
    features["midpoint_lon"] = midpoint.x
    features["midpoint_lat"] = midpoint.y
    features["elevation_range_m"] = elevation_range
    features["slope_percent"] = (
        100 * elevation_range / edges["length_m"].replace(0, np.nan)
    )

    for target in TARGETS:
        if features[target].isna().any():
            raise ValueError(f"Target column {target} contains missing labels.")
        features[target] = features[target].astype("int8")

    features = features.set_geometry(edges.geometry)
    features = features.set_crs(edges.crs, allow_override=True)
    return features


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    output = args.output.resolve()
    if output.exists() and not args.overwrite:
        raise FileExistsError(
            f"{output} already exists. Pass --overwrite to replace this generated file."
        )

    data = build_training_data(data_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    pyogrio.write_dataframe(
        data,
        output,
        layer="road_segments",
        driver="GPKG",
    )

    print(f"Saved {len(data):,} road segments to {output}")
    print("Features: highway, length_m, base_speed_kmh, min_elevation,")
    print("          midpoint_lon, midpoint_lat, elevation_range_m, slope_percent")
    for target in TARGETS:
        positives = int(data[target].sum())
        print(f"{target}: {positives:,} exposed / {len(data) - positives:,} not exposed")
    print(
        "Missing min_elevation values: "
        f"{int(data['min_elevation'].isna().sum()):,}"
    )


if __name__ == "__main__":
    main()
