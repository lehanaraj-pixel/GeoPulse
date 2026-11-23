
import json

import pandas as pd
import pytest

from snowflake_loader import (
    MockSnowflakeLoader,
    run_mock_ingestion,
    save_ingestion_report,
    save_batch_audit
)


def create_valid_batch(rows=2):
    return pd.DataFrame({
        "DEVICE_ID": ["DEV_0123456789ABCDEF"] * rows,
        "LATITUDE": [12.9716] * rows,
        "LONGITUDE": [77.5946] * rows,
        "TS": ["2026-01-05T10:00:00+05:30"] * rows
    })


def test_load_valid_batch():
    loader = MockSnowflakeLoader()

    result = loader.load_batch(create_valid_batch(2))

    assert result == {
        "rows_loaded": 2,
        "total_rows_loaded": 2,
        "total_batches_loaded": 1
    }


def test_cumulative_batch_counts():
    loader = MockSnowflakeLoader()

    loader.load_batch(create_valid_batch(2))
    result = loader.load_batch(create_valid_batch(3))

    assert result["total_rows_loaded"] == 5
    assert result["total_batches_loaded"] == 2


def test_empty_batch_rejected():
    loader = MockSnowflakeLoader()

    with pytest.raises(ValueError, match="empty batch"):
        loader.load_batch(pd.DataFrame())


def test_missing_columns_rejected():
    loader = MockSnowflakeLoader()

    invalid_batch = pd.DataFrame({
        "DEVICE_ID": ["DEV_0123456789ABCDEF"],
        "LATITUDE": [12.9716]
    })

    with pytest.raises(ValueError, match="missing required columns"):
        loader.load_batch(invalid_batch)



def test_run_mock_ingestion(tmp_path):
    csv_path = tmp_path / "gps_test.csv"

    source_data = pd.DataFrame({
        "DeviceID": ["DEV_0123456789ABCDEF"] * 5,
        "Latitude": [12.9716] * 5,
        "Longitude": [77.5946] * 5,
        "Timestamp": ["2026-01-05T10:00:00+05:30"] * 5
    })

    source_data.to_csv(csv_path, index=False)

    result = run_mock_ingestion(
        csv_path,
        batch_size=2,
        report_path=tmp_path / "ingestion_summary.json",
        audit_path=tmp_path / "batch_audit.json"
    )

    assert result["source_file"] == str(csv_path)
    assert result["batch_size"] == 2
    assert result["total_rows_loaded"] == 5
    assert result["total_batches_loaded"] == 3
    assert result["status"] == "SUCCESS"

    assert len(result["batch_audit"]) == 3

    assert result["batch_audit"][0]["batch_number"] == 1
    assert result["batch_audit"][1]["batch_number"] == 2
    assert result["batch_audit"][2]["batch_number"] == 3

    assert all(
        record["status"] == "SUCCESS"
        for record in result["batch_audit"]
    )

    assert (tmp_path / "ingestion_summary.json").exists()
    assert (tmp_path / "batch_audit.json").exists()

def test_save_ingestion_report(tmp_path):
    report = {
        "source_file": "gps_test.csv",
        "batch_size": 100,
        "total_rows_loaded": 500,
        "total_batches_loaded": 5,
        "status": "SUCCESS"
    }

    output_path = tmp_path / "ingestion_summary.json"

    saved_path = save_ingestion_report(report, output_path)

    assert saved_path == output_path
    assert output_path.exists()

    with output_path.open("r", encoding="utf-8") as file:
        saved_report = json.load(file)

    assert saved_report == report


def test_failed_ingestion_does_not_overwrite_report(tmp_path):
    csv_path = tmp_path / "invalid_gps.csv"
    report_path = tmp_path / "ingestion_summary.json"

    invalid_data = pd.DataFrame({
        "DeviceID": ["INVALID_DEVICE_ID"],
        "Latitude": [12.9716],
        "Longitude": [77.5946],
        "Timestamp": ["2026-01-05T10:00:00+05:30"]
    })

    invalid_data.to_csv(csv_path, index=False)

    previous_report = {
        "total_rows_loaded": 1000000,
        "total_batches_loaded": 10,
        "status": "SUCCESS"
    }

    save_ingestion_report(previous_report, report_path)

    with pytest.raises(ValueError, match="Invalid DeviceID format"):
        run_mock_ingestion(
            csv_path,
            batch_size=100,
            report_path=report_path
        )

    with report_path.open("r", encoding="utf-8") as file:
        saved_report = json.load(file)

    assert saved_report == previous_report


def test_batch_audit_metadata():
    loader = MockSnowflakeLoader()

    batch = create_valid_batch(3)
    loader.load_batch(batch)

    audit = loader.batch_audit[0]

    assert audit["batch_number"] == 1
    assert audit["rows_processed"] == 3
    assert audit["unique_devices"] == 1
    assert audit["min_latitude"] == 12.9716
    assert audit["max_latitude"] == 12.9716
    assert audit["min_longitude"] == 77.5946
    assert audit["max_longitude"] == 77.5946
    assert audit["status"] == "SUCCESS"


def test_sequential_batch_audit_numbering():
    loader = MockSnowflakeLoader()

    loader.load_batch(create_valid_batch(2))
    loader.load_batch(create_valid_batch(3))

    assert len(loader.batch_audit) == 2
    assert loader.batch_audit[0]["batch_number"] == 1
    assert loader.batch_audit[1]["batch_number"] == 2


def test_save_batch_audit(tmp_path):
    audit_records = [
        {
            "batch_number": 1,
            "rows_processed": 100,
            "unique_devices": 10,
            "status": "SUCCESS"
        }
    ]

    output_path = tmp_path / "batch_audit.json"

    saved_path = save_batch_audit(
        audit_records,
        output_path
    )

    assert saved_path == output_path
    assert output_path.exists()

    with output_path.open("r", encoding="utf-8") as file:
        saved_records = json.load(file)

    assert saved_records == audit_records
