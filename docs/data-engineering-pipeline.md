# GeoPulse – Data Engineering Pipeline

## 1. Overview

The Data Engineering component of GeoPulse is responsible for generating, validating, preparing, and processing synthetic GPS mobility data.

The pipeline prepares structured GPS data for downstream analytics and spatial processing.

## 2. Dataset Information

- City: Bengaluru
- Total records: 1,000,000
- Unique devices: 737
- Data duration: 30 days
- File: `data/bengaluru_test_1m.csv`

### Dataset Columns

| Column | Description |
|---|---|
| DeviceID | Anonymized device identifier |
| Latitude | GPS latitude |
| Longitude | GPS longitude |
| Timestamp | GPS ping timestamp with timezone |

## 3. Data Validation

The validation pipeline checks:

- Required column availability.
- Missing and null values.
- DeviceID format.
- Latitude and longitude data types and valid ranges.
- Timestamp parsing and timezone information.

Invalid data is rejected before batch preparation.

## 4. Batch Ingestion

The ingestion pipeline reads the GPS CSV using Pandas chunk-based processing.

- Default batch size: 100,000 records.
- Each batch is validated and prepared.
- Column names are standardized for downstream processing.
- The mock loader tracks processed records and batch-level metadata.

## 5. Ingestion Reporting

The pipeline generates two JSON reports:

### ingestion_summary.json

Contains the overall ingestion status, source file, batch size, total records processed, and total batches.

### batch_audit.json

Contains batch-level information, including row counts, unique devices, geographic boundaries, timestamp ranges, and processing status.

## 6. Execution

Run the mock ingestion pipeline:

```bash
python -c "from snowflake_loader import run_mock_ingestion; print(run_mock_ingestion('data/bengaluru_test_1m.csv'))"
```

Run automated tests:

```bash
python -m pytest -q
```

## 7. Current Implementation Status

The GPS generation, validation, batch preparation, mock ingestion, and audit reporting components have been implemented and tested.

The current loader simulates Snowflake ingestion locally. A live Snowflake connection and actual data upload have not been performed.

## 8. Downstream Data Flow

The expected project architecture is:

Raw GPS CSV → Validation and Ingestion → PySpark and Apache Sedona Analytics → summary.json → Dashboard

The analytics output must preserve the dashboard's agreed JSON integration contract.

## 9. Data Privacy

The project uses synthetic GPS mobility records and anonymized device identifiers. It does not use real customer GPS tracking data.