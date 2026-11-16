
"""GeoPulse: Hourly and daily mobility activity analysis."""

from pathlib import Path

import pandas as pd
from spatial_processing import create_spatial_data
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "bengaluru_test_1m.csv"
OUTPUT_DIR = BASE_DIR / "data" / "processed"


def load_data():
    df = pd.read_csv(DATA_PATH)

    df["Timestamp"] = pd.to_datetime(
        df["Timestamp"], utc=True
    ).dt.tz_convert("Asia/Kolkata")

    return df


def analyze_footfall(df):
    df["date"] = df["Timestamp"].dt.date
    df["hour"] = df["Timestamp"].dt.hour
    df["day_name"] = df["Timestamp"].dt.day_name()
    df["day_type"] = df["Timestamp"].dt.day_of_week.map(
        lambda day: "Weekend" if day >= 5 else "Weekday"
    )

    hourly = (
        df.groupby("hour")
        .agg(
            gps_pings=("DeviceID", "size"),
            unique_devices=("DeviceID", "nunique")
        )
        .reset_index()
    )

    daily = (
        df.groupby("date")
        .agg(
            gps_pings=("DeviceID", "size"),
            unique_devices=("DeviceID", "nunique")
        )
        .reset_index()
    )

    weekday_weekend = (
        df.groupby("day_type")
        .agg(
            gps_pings=("DeviceID", "size"),
            unique_devices=("DeviceID", "nunique")
        )
        .reset_index()
    )

    return hourly, daily, weekday_weekend


def analyze_store_footfall(df):
    """Calculate hourly GPS activity inside each store catchment."""

    from spatial_processing import (
        load_gps_data,
        create_spatial_data,
        analyze_catchments,
    )
    from config import Config

    cfg = Config()

    # Reuse the existing spatial logic.
    gdf = create_spatial_data(df)
    projected = gdf.to_crs("EPSG:32643")

    from shapely.geometry import Point
    import geopandas as gpd

    store_a = gpd.GeoSeries(
        [Point(cfg.store_a[1], cfg.store_a[0])],
        crs="EPSG:4326"
    ).to_crs("EPSG:32643").iloc[0]

    store_b = gpd.GeoSeries(
        [Point(cfg.store_b[1], cfg.store_b[0])],
        crs="EPSG:4326"
    ).to_crs("EPSG:32643").iloc[0]

    radius = cfg.catchment_radius_m

    projected["store_a_inside"] = (
        projected.geometry.distance(store_a) <= radius
    )
    projected["store_b_inside"] = (
        projected.geometry.distance(store_b) <= radius
    )

    projected["hour"] = projected["Timestamp"].dt.hour

    results = []

    for store, column in [
        ("Store A", "store_a_inside"),
        ("Store B", "store_b_inside"),
    ]:
        subset = projected[projected[column]]

        hourly = (
            subset.groupby("hour")
            .agg(
                gps_pings=("DeviceID", "size"),
                unique_devices=("DeviceID", "nunique")
            )
            .reset_index()
        )

        hourly["store"] = store
        results.append(hourly)

    return pd.concat(results, ignore_index=True)


def analyze_store_daily_footfall(df):
    """Calculate daily device activity inside each store catchment."""

    from config import Config
    from shapely.geometry import Point
    import geopandas as gpd

    cfg = Config()
    gdf = create_spatial_data(df).to_crs("EPSG:32643")

    store_coordinates = {
        "Store A": cfg.store_a,
        "Store B": cfg.store_b,
    }

    results = []

    for store, (lat, lon) in store_coordinates.items():
        store_point = gpd.GeoSeries(
            [Point(lon, lat)],
            crs="EPSG:4326"
        ).to_crs("EPSG:32643").iloc[0]

        inside = gdf.geometry.distance(store_point) <= cfg.catchment_radius_m

        subset = gdf.loc[inside].copy()
        subset["date"] = subset["Timestamp"].dt.date

        daily = (
            subset.groupby("date")
            .agg(
                gps_pings=("DeviceID", "size"),
                unique_devices=("DeviceID", "nunique")
            )
            .reset_index()
        )

        daily["store"] = store
        results.append(daily)

    return pd.concat(results, ignore_index=True)

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_data()

    hourly, daily, weekday_weekend = analyze_footfall(df)

    hourly.to_csv(OUTPUT_DIR / "hourly_footfall.csv", index=False)
    daily.to_csv(OUTPUT_DIR / "daily_footfall.csv", index=False)
    weekday_weekend.to_csv(
        OUTPUT_DIR / "weekday_weekend_footfall.csv",
        index=False
    )

    store_hourly = analyze_store_footfall(df)

    store_hourly.to_csv(
        OUTPUT_DIR / "store_hourly_footfall.csv",
        index=False
    )

    store_daily = analyze_store_daily_footfall(df)

    store_daily.to_csv(
        OUTPUT_DIR / "store_daily_footfall.csv",
        index=False
    )

    print("\n--- STORE-WISE DAILY ACTIVITY ---")
    print(store_daily.to_string(index=False))

    print("\n--- STORE-WISE HOURLY ACTIVITY ---")
    print(store_hourly.to_string(index=False))

    print("\n--- HOURLY ACTIVITY ---")
    print(hourly.to_string(index=False))

    print("\n--- DAILY ACTIVITY ---")
    print(daily.to_string(index=False))

    print("\n--- WEEKDAY VS WEEKEND ---")
    print(weekday_weekend.to_string(index=False))

    print("\nAll reports exported successfully.")


if __name__ == "__main__":
    main()

