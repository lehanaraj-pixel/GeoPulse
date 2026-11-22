import re
from pathlib import Path
import pandas as pd


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

    if batch_size <= 0:
        raise ValueError("Batch size must be greater than zero")

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
