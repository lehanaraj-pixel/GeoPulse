
"""Unit tests for GeoPulse GPS data validation."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from config import Config
from validate_data import REQUIRED, Validator, haversine_m


@pytest.fixture
def config():
    """Create a valid project configuration."""
    cfg = Config()
    cfg.validate()
    return cfg


@pytest.fixture
def validator(config):
    """Create a validator for a small test dataset."""
    return Validator(
        cfg=config,
        start=config.start_date,
        days=config.num_days,
        holidays=()
    )


def make_record(device="DEV_0123456789ABCDEF",
                latitude=12.978973,
                longitude=77.645270,
                timestamp="2026-01-05 10:00:00+05:30"):
    """Build one GPS record using the expected CSV schema."""
    return {
        "DeviceID": device,
        "Latitude": str(latitude),
        "Longitude": str(longitude),
        "Timestamp": timestamp
    }


def make_dataframe(records):
    """Convert records into the validator's expected DataFrame."""
    return pd.DataFrame(records, columns=REQUIRED).astype(str)


def test_haversine_same_coordinates():
    """Distance between identical coordinates must be zero."""
    distance = haversine_m(12.97, 77.64, 12.97, 77.64)

    assert distance == pytest.approx(0.0)


def test_haversine_positive_distance():
    """Different coordinates must produce a positive distance."""
    distance = haversine_m(12.97, 77.64, 12.98, 77.65)

    assert distance > 0


def test_valid_gps_record_is_processed(validator):
    """A valid GPS record must be counted."""
    df = make_dataframe([make_record()])

    validator.process(df)

    assert validator.total == 1
    assert validator.missing["DeviceID"] == 0
    assert validator.missing["Latitude"] == 0
    assert validator.missing["Longitude"] == 0
    assert validator.missing["Timestamp"] == 0


def test_missing_device_id_is_detected(validator):
    """Missing device identifiers must be counted."""
    record = make_record(device="")
    validator.process(make_dataframe([record]))

    assert validator.missing["DeviceID"] == 1


def test_invalid_latitude_is_detected(validator):
    """Latitude outside the valid geographic range must be counted."""
    record = make_record(latitude=95)

    validator.process(make_dataframe([record]))

    assert validator.out_of_range["Latitude"] == 1


def test_invalid_longitude_is_detected(validator):
    """Longitude outside the valid geographic range must be counted."""
    record = make_record(longitude=190)

    validator.process(make_dataframe([record]))

    assert validator.out_of_range["Longitude"] == 1


def test_non_numeric_coordinates_are_detected(validator):
    """Non-numeric coordinates must be identified."""
    record = make_record(latitude="invalid")

    validator.process(make_dataframe([record]))

    assert validator.non_numeric["Latitude"] == 1


def test_invalid_timestamp_is_detected(validator):
    """Unparseable timestamps must be counted."""
    record = make_record(timestamp="not-a-timestamp")

    validator.process(make_dataframe([record]))

    assert validator.ts_unparseable == 1


def test_invalid_device_format_is_detected(validator):
    """Device IDs must follow the configured identifier pattern."""
    record = make_record(device="DEVICE_123")

    validator.process(make_dataframe([record]))

    assert validator.bad_device_format == 1


def test_duplicate_records_are_detected(validator):
    """Identical GPS records must be identified during finalization."""
    record = make_record()
    df = make_dataframe([record, record.copy()])

    validator.process(df)
    validator.finalize()

    assert validator.dup_full == 1
    assert validator.dup_key == 1


def test_total_record_count_is_preserved(validator):
    """The validator must account for every input row."""
    records = [
        make_record(device="DEV_0123456789ABCDEF"),
        make_record(device="DEV_1123456789ABCDEF"),
        make_record(device="DEV_2123456789ABCDEF")
    ]

    validator.process(make_dataframe(records))

    assert validator.total == 3


def test_empty_dataframe_is_supported(validator):
    """An empty DataFrame must not crash the validator."""
    validator.process(make_dataframe([]))
    catchment = validator.finalize()

    assert validator.total == 0
    assert catchment["devices_union"] == 0
