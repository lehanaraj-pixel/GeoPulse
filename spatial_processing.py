
"""Spatial processing for GeoPulse GPS mobility data."""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from config import Config

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "bengaluru_test_1m.csv"
OUTPUT_DIR = BASE_DIR / "data" / "processed"


def load_gps_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load and validate the required GPS columns."""
    if not path.exists():
        raise FileNotFoundError(f"GPS dataset not found: {path}")

    df = pd.read_csv(path)

    required = {"DeviceID", "Latitude", "Longitude", "Timestamp"}
    missing = required.difference(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True)

    return df


def create_spatial_data(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Convert GPS coordinates into geographic point geometries."""
    geometry = [
        Point(lon, lat)
        for lon, lat in zip(df["Longitude"], df["Latitude"])
    ]

    return gpd.GeoDataFrame(
        df.copy(),
        geometry=geometry,
        crs="EPSG:4326",
    )


def main() -> None:
    cfg = Config()
    cfg.validate()

    df = load_gps_data()
    gdf = create_spatial_data(df)

    print(f"GPS records loaded: {len(gdf):,}")
    print(f"Unique devices: {gdf['DeviceID'].nunique():,}")
    print(f"Coordinate system: {gdf.crs}")
    print(f"Store A: {cfg.store_a}")
    print(f"Store B: {cfg.store_b}")
    print(f"Catchment radius: {cfg.catchment_radius_m} metres")


if __name__ == "__main__":
    main()
