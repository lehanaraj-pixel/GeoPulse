
import json
from pathlib import Path

from snowflake_ingestion import read_gps_batches, prepare_gps_batch


class MockSnowflakeLoader:
    def __init__(self):
        self.total_rows_loaded = 0
        self.total_batches_loaded = 0
        self.batch_audit = []

    def load_batch(self, batch):
        if batch.empty:
            raise ValueError("Cannot load an empty batch")

        required_columns = {
            "DEVICE_ID",
            "LATITUDE",
            "LONGITUDE",
            "TS"
        }

        if not required_columns.issubset(batch.columns):
            raise ValueError("Batch contains missing required columns")

        rows = len(batch)
        batch_number = self.total_batches_loaded + 1

        unique_devices = batch["DEVICE_ID"].nunique()

        min_latitude = batch["LATITUDE"].min()
        max_latitude = batch["LATITUDE"].max()

        min_longitude = batch["LONGITUDE"].min()
        max_longitude = batch["LONGITUDE"].max()

        start_timestamp = batch["TS"].min()
        end_timestamp = batch["TS"].max()

        audit_record = {
            "batch_number": int(batch_number),
            "rows_processed": int(rows),
            "unique_devices": int(unique_devices),
            "min_latitude": float(min_latitude),
            "max_latitude": float(max_latitude),
            "min_longitude": float(min_longitude),
            "max_longitude": float(max_longitude),
            "start_timestamp": str(start_timestamp),
            "end_timestamp": str(end_timestamp),
            "status": "SUCCESS"
        }

        self.batch_audit.append(audit_record)

        self.total_rows_loaded += rows
        self.total_batches_loaded += 1

        return {
            "rows_loaded": rows,
            "total_rows_loaded": self.total_rows_loaded,
            "total_batches_loaded": self.total_batches_loaded
        }


def run_mock_ingestion(
    file_path,
    batch_size=100_000,
    report_path="data/ingestion_summary.json",
    audit_path="data/batch_audit.json"
):
    loader = MockSnowflakeLoader()

    for batch in read_gps_batches(file_path, batch_size):
        prepared_batch = prepare_gps_batch(batch)
        loader.load_batch(prepared_batch)

    report = {
        "source_file": str(file_path),
        "batch_size": batch_size,
        "total_rows_loaded": loader.total_rows_loaded,
        "total_batches_loaded": loader.total_batches_loaded,
        "status": "SUCCESS"
    }

    save_ingestion_report(report, report_path)
    save_batch_audit(loader.batch_audit, audit_path)

    return {
        **report,
        "batch_audit": loader.batch_audit
    }


def save_ingestion_report(
    report,
    output_path="data/ingestion_summary.json"
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    return output_path


def save_batch_audit(
    audit_records,
    output_path="data/batch_audit.json"
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(audit_records, file, indent=4)

    return output_path
