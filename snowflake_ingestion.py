import re
import json
from pathlib import Path
import pandas as pd
from pandas.errors import EmptyDataError


REQUIRED_COLUMNS = [
    "DeviceID",
    "Latitude",
    "Longitude",
    "Timestamp"
]

SNOWFLAKE_COLUMN_MAPPING = {
    "DeviceID": "DEVICE_ID",
    "Latitude": "LATITUDE",
    "Longitude": "LONGITUDE",
    "Timestamp": "TS"
}

DEVICE_ID_PATTERN = re.compile(r"^DEV_[0-9A-F]{16}$")

def read_gps_batches(file_path, batch_size=100_000):
    """
    Read GPS data in batches instead of loading the
    entire CSV into memory.
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    if not isinstance(batch_size, int) or isinstance(batch_size, bool):
        raise TypeError("Batch size must be an integer")

    if batch_size <= 0:
        raise ValueError("Batch size must be greater than zero")

    try:
        for batch in pd.read_csv(
            file_path,
            chunksize=batch_size,
            dtype={
                "DeviceID": "string",
                "Latitude": "float64",
                "Longitude": "float64",
                "Timestamp": "string"
            }
        ):
            yield batch

    except EmptyDataError as error:
        raise ValueError(
            f"GPS CSV file is empty: {file_path}"
        ) from error


def validate_gps_batch(batch):
    """
    Validate the structure and values of one GPS batch.
    """

    # 1. Check required columns
    missing_columns = set(REQUIRED_COLUMNS) - set(batch.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    # 2. Check missing values
    if batch[REQUIRED_COLUMNS].isnull().any().any():
        raise ValueError("GPS batch contains missing values")

    # 3. Validate DeviceID format
    valid_ids = batch["DeviceID"].astype("string").str.match(
        DEVICE_ID_PATTERN
    )

    if not valid_ids.all():
        raise ValueError("Invalid DeviceID format")

    # 4. Validate numeric coordinates
    latitude = pd.to_numeric(batch["Latitude"], errors="coerce")
    longitude = pd.to_numeric(batch["Longitude"], errors="coerce")

    if latitude.isnull().any() or longitude.isnull().any():
        raise ValueError("Coordinates must be numeric")

    # 5. Validate coordinate ranges
    if not latitude.between(-90, 90).all():
        raise ValueError("Invalid latitude values")

    if not longitude.between(-180, 180).all():
        raise ValueError("Invalid longitude values")

    # 6. Validate timestamp parsing
    timestamps = batch["Timestamp"].astype("string")

    parsed_timestamps = pd.to_datetime(
        timestamps,
        errors="coerce",
        utc=True
    )

    if parsed_timestamps.isnull().any():
        raise ValueError("Invalid timestamp values")

    # 7. Check explicit timezone offset
    has_timezone = timestamps.str.contains(
        r"(?:Z|[+-]\d{2}:\d{2})$",
        regex=True
    )

    if not has_timezone.all():
        raise ValueError(
            "Timestamps must include a timezone offset"
        )
    return True
def prepare_gps_batch(batch):
    """
    Validate and prepare a batch for Snowflake.
    """

    validate_gps_batch(batch)

    prepared = batch.rename(
        columns=SNOWFLAKE_COLUMN_MAPPING
    ).copy()

    return prepared
def generate_ingestion_diagnostics(
    file_path,
    batch_size=100_000,
    output_path=None
):
    """Generate a JSON diagnostics report for GPS data ingestion."""

    total_records = 0
    total_batches = 0
    valid_batches = 0
    invalid_batches = 0

    failure_reasons = {}
    unique_devices = set()

    min_latitude = float("inf")
    max_latitude = float("-inf")
    min_longitude = float("inf")
    max_longitude = float("-inf")

    earliest_timestamp = None
    latest_timestamp = None

    for batch in read_gps_batches(file_path, batch_size):
        total_batches += 1
        total_records += len(batch)

        try:
            validate_gps_batch(batch)
        except ValueError as error:
            invalid_batches += 1
            reason = str(error)
            failure_reasons[reason] = (
                failure_reasons.get(reason, 0) + 1
            )
            continue

        valid_batches += 1

        unique_devices.update(
            batch["DeviceID"].astype(str).unique()
        )

        latitude = pd.to_numeric(batch["Latitude"])
        longitude = pd.to_numeric(batch["Longitude"])

        min_latitude = min(min_latitude, latitude.min())
        max_latitude = max(max_latitude, latitude.max())
        min_longitude = min(min_longitude, longitude.min())
        max_longitude = max(max_longitude, longitude.max())

        timestamps = pd.to_datetime(
            batch["Timestamp"], utc=True
        )

        batch_start = timestamps.min()
        batch_end = timestamps.max()

        if earliest_timestamp is None or batch_start < earliest_timestamp:
            earliest_timestamp = batch_start

        if latest_timestamp is None or batch_end > latest_timestamp:
            latest_timestamp = batch_end

    has_valid_data = valid_batches > 0

    diagnostics = {
        "source_file": str(file_path),
        "batch_size": batch_size,
        "total_records_processed": total_records,
        "total_batches_processed": total_batches,
        "valid_batches": valid_batches,
        "invalid_batches": invalid_batches,
        "unique_devices": len(unique_devices),
        "geographic_bounds": {
            "min_latitude": min_latitude if has_valid_data else None,
            "max_latitude": max_latitude if has_valid_data else None,
            "min_longitude": min_longitude if has_valid_data else None,
            "max_longitude": max_longitude if has_valid_data else None
        },
        "timestamp_coverage": {
            "start": str(earliest_timestamp) if has_valid_data else None,
            "end": str(latest_timestamp) if has_valid_data else None
        },
        "validation_failures": failure_reasons,
        "status": (
            "NO_DATA" if total_records == 0
            else "SUCCESS" if invalid_batches == 0
            else "COMPLETED_WITH_ERRORS"
        )
    }

    if output_path is not None:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(diagnostics, file, indent=4)

    return diagnostics
