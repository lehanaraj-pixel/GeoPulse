
"""GeoPulse spatial processing and store catchment analysis."""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from config import Config

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "bengaluru_test_1m.csv"
OUTPUT_DIR = BASE_DIR / "data" / "processed"

METRIC_CRS = "EPSG:32643"


def load_gps_data(path=DATA_PATH):
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)

    required = {"DeviceID", "Latitude", "Longitude", "Timestamp"}
    missing = required.difference(df.columns)

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True)
    return df


def create_spatial_data(df):
    geometry = [
        Point(lon, lat)
        for lon, lat in zip(df["Longitude"], df["Latitude"])
    ]

    return gpd.GeoDataFrame(
        df.copy(),
        geometry=geometry,
        crs="EPSG:4326"
    )


def analyze_catchments(gdf, cfg):
    # Project GPS points into metres.
    projected = gdf.to_crs(METRIC_CRS)

    # Convert configured store coordinates into projected points.
    store_a = gpd.GeoSeries(
        [Point(cfg.store_a[1], cfg.store_a[0])],
        crs="EPSG:4326"
    ).to_crs(METRIC_CRS).iloc[0]

    store_b = gpd.GeoSeries(
        [Point(cfg.store_b[1], cfg.store_b[0])],
        crs="EPSG:4326"
    ).to_crs(METRIC_CRS).iloc[0]

    radius = cfg.catchment_radius_m

    # Identify GPS pings inside each catchment.
    projected["store_a_inside"] = (
        projected.geometry.distance(store_a) <= radius
    )

    projected["store_b_inside"] = (
        projected.geometry.distance(store_b) <= radius
    )

    # Aggregate to device level: a device is a visitor if
    # at least one GPS ping falls inside the catchment.
    devices = projected.groupby("DeviceID").agg(
        store_a_visitor=("store_a_inside", "any"),
        store_b_visitor=("store_b_inside", "any")
    )

    a_visitors = set(devices.index[devices["store_a_visitor"]])
    b_visitors = set(devices.index[devices["store_b_visitor"]])

    shared = a_visitors & b_visitors
    union = a_visitors | b_visitors

    jaccard = len(shared) / len(union) if union else 0

    summary = pd.DataFrame([
        {
            "store": "Store A",
            "gps_pings": int(projected["store_a_inside"].sum()),
            "unique_devices": len(a_visitors)
        },
        {
            "store": "Store B",
            "gps_pings": int(projected["store_b_inside"].sum()),
            "unique_devices": len(b_visitors)
        }
    ])

    membership = devices.reset_index()

    return summary, membership, len(shared), jaccard


def main():
    cfg = Config()
    cfg.validate()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_gps_data()
    gdf = create_spatial_data(df)

    summary, membership, shared, jaccard = analyze_catchments(
        gdf, cfg
    )

    summary.to_csv(
        OUTPUT_DIR / "store_catchment_summary.csv",
        index=False
    )

    membership.to_csv(
        OUTPUT_DIR / "device_catchment_membership.csv",
        index=False
    )

    print("\n--- GEOPULSE CATCHMENT ANALYSIS ---")
    print(summary.to_string(index=False))
    print(f"\nShared visitors: {shared:,}")
    print(f"Jaccard similarity: {jaccard:.4f}")
    print(f"Jaccard percentage: {jaccard * 100:.2f}%")
    print(f"\nResults saved in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
