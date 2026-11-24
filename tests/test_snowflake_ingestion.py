
import pandas as pd
import pytest

from snowflake_ingestion import (
    read_gps_batches,
    validate_gps_batch,
    prepare_gps_batch
)


@pytest.fixture
def valid_batch():
    return pd.DataFrame({
        "DeviceID": ["DEV_1234567890ABCDEF"],
        "Latitude": [12.978973],
        "Longitude": [77.645270],
        "Timestamp": ["2026-01-05 08:15:32+05:30"]
    })


def test_valid_batch(valid_batch):
    assert validate_gps_batch(valid_batch) is True


def test_missing_columns(valid_batch):
    batch = valid_batch.drop(columns=["Latitude"])

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_gps_batch(batch)


def test_missing_values(valid_batch):
    valid_batch.loc[0, "Latitude"] = None

    with pytest.raises(ValueError, match="missing values"):
        validate_gps_batch(valid_batch)


def test_invalid_latitude(valid_batch):
    valid_batch.loc[0, "Latitude"] = 95

    with pytest.raises(ValueError, match="Invalid latitude"):
        validate_gps_batch(valid_batch)


def test_invalid_longitude(valid_batch):
    valid_batch.loc[0, "Longitude"] = 200

    with pytest.raises(ValueError, match="Invalid longitude"):
        validate_gps_batch(valid_batch)


def test_invalid_timestamp(valid_batch):
    valid_batch.loc[0, "Timestamp"] = "not-a-timestamp"

    with pytest.raises(ValueError, match="Invalid timestamp"):
        validate_gps_batch(valid_batch)


def test_column_mapping(valid_batch):
    prepared = prepare_gps_batch(valid_batch)

    assert list(prepared.columns) == [
        "DEVICE_ID",
        "LATITUDE",
        "LONGITUDE",
        "TS"
    ]


def test_timestamp_preserved(valid_batch):
    prepared = prepare_gps_batch(valid_batch)

    assert (
        prepared.loc[0, "TS"]
        == "2026-01-05 08:15:32+05:30"
    )


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        next(read_gps_batches("missing_file.csv"))


def test_invalid_batch_size():
    with pytest.raises(ValueError, match="Batch size"):
        next(read_gps_batches(
            "data/bengaluru_test_1m.csv",
            batch_size=0
        ))

def test_invalid_device_id(valid_batch):
    valid_batch.loc[0, "DeviceID"] = "INVALID_ID"

    with pytest.raises(ValueError, match="DeviceID"):
        validate_gps_batch(valid_batch)


def test_non_numeric_coordinates(valid_batch):
    valid_batch["Latitude"] = valid_batch["Latitude"].astype("object")
    valid_batch.loc[0, "Latitude"] = "north"

    with pytest.raises(ValueError, match="numeric"):
        validate_gps_batch(valid_batch)


def test_timestamp_without_timezone(valid_batch):
    valid_batch.loc[0, "Timestamp"] = "2026-01-05 08:15:32"

    with pytest.raises(ValueError, match="timezone offset"):
        validate_gps_batch(valid_batch)

@pytest.mark.parametrize("batch_size", [1.5, "100", True, None])
def test_non_integer_batch_size(batch_size):
    with pytest.raises(TypeError, match="must be an integer"):
        next(read_gps_batches(
            "data/bengaluru_test_1m.csv",
            batch_size=batch_size
        ))


@pytest.mark.parametrize("batch_size", [0, -1])
def test_non_positive_batch_size(batch_size):
    with pytest.raises(ValueError, match="greater than zero"):
        next(read_gps_batches(
            "data/bengaluru_test_1m.csv",
            batch_size=batch_size
        ))