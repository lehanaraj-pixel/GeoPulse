
import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path


GRID_CELL_SIZE_M = 250
EARTH_RADIUS_M = 6_371_008.8


def distance_m(lat1, lon1, lat2, lon2):
    """Calculate distance between GPS coordinates in metres."""
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    return 2 * EARTH_RADIUS_M * math.atan2(
        math.sqrt(a), math.sqrt(1 - a)
    )


def process_data(input_path, manifest_path, output_path):
    with manifest_path.open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    config = manifest["config"]
    store_a = tuple(config["store_a"])
    store_b = tuple(config["store_b"])
    radius = float(config["catchment_radius_m"])

    # Approximate 250-metre grid using the dataset's central latitude.
    bounds = config.get("bounds", {})
    center_lat = (
        float(bounds["lat_min"]) + float(bounds["lat_max"])
    ) / 2 if "lat_min" in bounds and "lat_max" in bounds else (
        store_a[0] + store_b[0]
    ) / 2

    lat_step = GRID_CELL_SIZE_M / 111_320
    lon_step = GRID_CELL_SIZE_M / (
        111_320 * math.cos(math.radians(center_lat))
    )

    density_cells = defaultdict(int)

    total_pings = 0
    all_devices = set()
    store_a_devices = set()
    store_b_devices = set()

    store_a_pings = 0
    store_b_pings = 0
    overlap_pings = 0

    hourly_pings = [0] * 24
    hourly_devices = defaultdict(set)

    daily = defaultdict(lambda: {
        "pings": 0,
        "devices": set(),
        "store_a_pings": 0,
        "store_b_pings": 0,
        "store_a_devices": set(),
        "store_b_devices": set()
    })

    first_timestamp = None
    last_timestamp = None

    print("Reading GPS data...")

    with input_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        required = {"DeviceID", "Latitude", "Longitude", "Timestamp"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(
                f"CSV must contain these columns: {sorted(required)}"
            )

        for row in reader:
            device = row["DeviceID"]
            lat = float(row["Latitude"])
            lon = float(row["Longitude"])
            timestamp = datetime.fromisoformat(row["Timestamp"])

            date_key = timestamp.date().isoformat()
            hour = timestamp.hour

            total_pings += 1
            all_devices.add(device)

            # Aggregate GPS pings into grid cells.
            grid_x = math.floor(lon / lon_step)
            grid_y = math.floor(lat / lat_step)
            density_cells[(grid_y, grid_x)] += 1

            if first_timestamp is None or timestamp < first_timestamp:
                first_timestamp = timestamp

            if last_timestamp is None or timestamp > last_timestamp:
                last_timestamp = timestamp

            hourly_pings[hour] += 1
            hourly_devices[(date_key, hour)].add(device)

            day = daily[date_key]
            day["pings"] += 1
            day["devices"].add(device)

            in_a = distance_m(
                lat, lon, store_a[0], store_a[1]
            ) <= radius

            in_b = distance_m(
                lat, lon, store_b[0], store_b[1]
            ) <= radius

            if in_a:
                store_a_pings += 1
                store_a_devices.add(device)
                day["store_a_pings"] += 1
                day["store_a_devices"].add(device)

            if in_b:
                store_b_pings += 1
                store_b_devices.add(device)
                day["store_b_pings"] += 1
                day["store_b_devices"].add(device)

            if in_a and in_b:
                overlap_pings += 1

            if total_pings % 100000 == 0:
                print(f"Processed {total_pings:,} pings")

    if total_pings == 0:
        raise ValueError("The CSV contains no GPS records.")

    overlap_count = len(store_a_devices & store_b_devices)
    union_count = len(store_a_devices | store_b_devices)

    def percentage(part, whole):
        return round(part / whole * 100, 2) if whole else 0

    daily_output = []

    for date_key in sorted(daily):
        item = daily[date_key]
        daily_output.append({
            "date": date_key,
            "pings": item["pings"],
            "unique_devices": len(item["devices"]),
            "store_a_pings": item["store_a_pings"],
            "store_b_pings": item["store_b_pings"],
            "store_a_unique_devices": len(item["store_a_devices"]),
            "store_b_unique_devices": len(item["store_b_devices"])
        })

    hourly_output = []
    total_days = len(daily)

    for hour in range(24):
        daily_unique = [
            len(hourly_devices.get((date_key, hour), set()))
            for date_key in daily
        ]

        hourly_output.append({
            "hour": hour,
            "label": f"{hour:02d}:00",
            "total_pings": hourly_pings[hour],
            "average_daily_pings": round(
                hourly_pings[hour] / total_days, 2
            ),
            "average_daily_unique_devices": round(
                sum(daily_unique) / total_days, 2
            ),
            "peak_daily_unique_devices": max(daily_unique)
        })

    # Convert grid indices into geographic cell-centre coordinates.
    density_output = []

    for (grid_y, grid_x), ping_count in sorted(density_cells.items()):
        density_output.append({
            "latitude": round((grid_y + 0.5) * lat_step, 6),
            "longitude": round((grid_x + 0.5) * lon_step, 6),
            "pings": ping_count
        })

    result = {
        "metadata": {
            "dataset_type": "synthetic_simulated_gps",
            "generator_version": manifest.get("generator_version"),
            "generated_at": manifest.get("generated_at"),
            "records_written": manifest.get("records_written"),
            "devices_written": manifest.get("devices_written"),
            "processed_pings": total_pings,
            "unique_devices": len(all_devices),
            "start_timestamp": first_timestamp.isoformat(),
            "end_timestamp": last_timestamp.isoformat(),
            "timezone": config["timezone"],
            "catchment_radius_m": radius,
            "geography_is_placeholder": config.get(
                "geography_is_placeholder", True
            )
        },
        "stores": {
            "store_a": {
                "label": "Store A",
                "latitude": store_a[0],
                "longitude": store_a[1],
                "catchment_pings": store_a_pings,
                "unique_devices": len(store_a_devices)
            },
            "store_b": {
                "label": "Store B",
                "latitude": store_b[0],
                "longitude": store_b[1],
                "catchment_pings": store_b_pings,
                "unique_devices": len(store_b_devices)
            }
        },
        "overlap": {
            "unique_devices_in_both": overlap_count,
            "unique_devices_union": union_count,
            "jaccard_percent": percentage(
                overlap_count, union_count
            ),
            "store_a_devices_also_in_b": percentage(
                overlap_count, len(store_a_devices)
            ),
            "store_b_devices_also_in_a": percentage(
                overlap_count, len(store_b_devices)
            ),
            "pings_inside_both": overlap_pings
        },
        "density_grid": {
            "cell_size_m": GRID_CELL_SIZE_M,
            "cell_count": len(density_output),
            "total_pings": total_pings,
            "cells": density_output
        },
        "hourly": hourly_output,
        "daily": daily_output,
        "disclaimer": (
            "Synthetic simulated GPS pings, not real customer records. "
            "Density cells show aggregated ping counts, not confirmed "
            "customer visits or purchases. Catchment presence does not "
            "confirm a store visit or purchase. Results describe this "
            "simulation and are not real-world retail forecasts."
        )
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)

    print("\nProcessing complete.")
    print(f"Total GPS pings: {total_pings:,}")
    print(f"Unique simulated devices: {len(all_devices)}")
    print(f"Store A catchment devices: {len(store_a_devices)}")
    print(f"Store B catchment devices: {len(store_b_devices)}")
    print(f"Devices in both catchments: {overlap_count}")
    print(f"Density grid cells: {len(density_output):,}")
    print(
        f"Overlap Jaccard: "
        f"{percentage(overlap_count, union_count)}%"
    )
    print(f"Output: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process GeoPulse simulated GPS data."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)

    args = parser.parse_args()
    process_data(args.input, args.manifest, args.output)
