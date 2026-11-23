import json
from pathlib import Path
from snowflake_ingestion import read_gps_batches, prepare_gps_batch


class MockSnowflakeLoader:
    def __init__(self):
        self.total_rows_loaded = 0
        self.total_batches_loaded = 0

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

        self.total_rows_loaded += rows
        self.total_batches_loaded += 1

        return {
            "rows_loaded": rows,
            "total_rows_loaded": self.total_rows_loaded,
            "total_batches_loaded": self.total_batches_loaded
        }



def run_mock_ingestion(file_path, batch_size=100_000,
                       report_path="data/ingestion_summary.json"):
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
    return report


def save_ingestion_report(report, output_path="data/ingestion_summary.json"):
    output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    return output_path