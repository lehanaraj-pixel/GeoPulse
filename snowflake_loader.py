from snowflake_ingestion import read_gps_batches, prepare_gps_batch


class MockSnowflakeLoader:
    def __init__(self):
        self.total_rows_loaded = 0
        self.total_batches_loaded = 0

    def load_batch(self, batch):
        if batch.empty:
            raise ValueError("Cannot load an empty batch")
        required_columns = {"DEVICE_ID", "LATITUDE", "LONGITUDE", "TS"}

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

    
def run_mock_ingestion(file_path, batch_size=100_000):
    loader = MockSnowflakeLoader()

    for batch in read_gps_batches(file_path, batch_size):
        prepared_batch = prepare_gps_batch(batch)
        loader.load_batch(prepared_batch)

    return {
        "total_rows_loaded": loader.total_rows_loaded,
        "total_batches_loaded": loader.total_batches_loaded
    }