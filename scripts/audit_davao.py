from pathlib import Path

import pyogrio
import rasterio


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR.parent / "floodnetData" / "data"

VECTOR_FILES = [
    DATA_DIR / "boundaries" / "davao.shp",
    DATA_DIR / "network" / "davao.gpkg",
    DATA_DIR / "flood" / "year_5" / "davao.shp",
    DATA_DIR / "flood" / "year_25" / "davao.shp",
    DATA_DIR / "flood" / "year_100" / "davao.shp",
]
RASTER_FILE = DATA_DIR / "elevation" / "davao.tif"


def report_vector(path: Path) -> None:
    if path.suffix.lower() == ".gpkg":
        layers = pyogrio.list_layers(path)
        for layer_name, geometry_type in layers:
            layer = str(layer_name)
            info = pyogrio.read_info(path, layer=layer)
            print(f"\n{path.relative_to(DATA_DIR)} | layer={layer}")
            print(f"  features: {info['features']}")
            print(f"  geometry: {geometry_type}")
            print(f"  CRS: {info['crs']}")
            print(f"  bounds: {info['total_bounds']}")
            print(f"  fields: {list(info['fields'])}")
        return

    info = pyogrio.read_info(path)
    print(f"\n{path.relative_to(DATA_DIR)}")
    print(f"  features: {info['features']}")
    print(f"  geometry: {info['geometry_type']}")
    print(f"  CRS: {info['crs']}")
    print(f"  bounds: {info['total_bounds']}")
    print(f"  fields: {list(info['fields'])}")


def report_raster(path: Path) -> None:
    with rasterio.open(path) as raster:
        print(f"\n{path.relative_to(DATA_DIR)}")
        print(f"  CRS: {raster.crs}")
        print(f"  dimensions: {raster.width} x {raster.height}")
        print(f"  bounds: {raster.bounds}")
        print(f"  pixel size: {raster.res}")
        print(f"  dtype: {raster.dtypes[0]}")
        print(f"  nodata: {raster.nodata}")


def report_training_labels() -> None:
    network = DATA_DIR / "network" / "davao.gpkg"
    targets = ["flood_5yr", "flood_25yr", "flood_100yr"]
    edges = pyogrio.read_dataframe(
        network,
        layer="edges",
        columns=["in_metro", *targets],
        read_geometry=False,
    )
    metro_edges = edges.loc[edges["in_metro"].fillna(False)]
    print("\nMetro Davao training-label coverage")
    print(f"  network edges: {len(edges)}")
    print(f"  edges in study area: {len(metro_edges)}")
    for target in targets:
        counts = metro_edges[target].value_counts(dropna=False).to_dict()
        print(f"  {target}: {counts}")

    nodes = pyogrio.read_dataframe(
        network,
        layer="nodes",
        columns=["in_metro", "elevation"],
        read_geometry=False,
    )
    metro_nodes = nodes.loc[nodes["in_metro"].fillna(False)]
    missing_elevation = int(metro_nodes["elevation"].isna().sum())
    print(
        f"  study-area nodes without elevation: "
        f"{missing_elevation} / {len(metro_nodes)}"
    )


def main() -> None:
    missing = [path for path in [*VECTOR_FILES, RASTER_FILE] if not path.is_file()]
    if missing:
        missing_paths = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"Required Davao data files are missing:\n{missing_paths}")

    print("Davao geospatial data audit")
    for path in VECTOR_FILES:
        report_vector(path)
    report_raster(RASTER_FILE)
    report_training_labels()


if __name__ == "__main__":
    main()
