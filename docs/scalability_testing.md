# Scalability Testing

## 1. Test Overview

GeoPulse was tested using a synthetic Bengaluru GPS mobility dataset containing 1 million records.

| Parameter | Value |
|---|---|
| Dataset | Bengaluru GPS Mobility |
| Total GPS records | 1,000,000 |
| Unique devices | 737 |
| Observation period | 30 days |
| Start date | 2026-01-05 |
| End date | 2026-02-03 |
| Random seed | 42 |

## 2. Processing Performed

The dataset was processed locally using Python, Pandas, GeoPandas, and Shapely.

The pipeline performed:

- GPS data loading and timestamp conversion.
- Coordinate-to-geometry conversion.
- Spatial catchment analysis for two retail locations.
- Device-level catchment membership analysis.
- Daily and hourly footfall aggregation.
- Weekday versus weekend activity comparison.

## 3. Spatial Analysis Results

| Metric | Store A | Store B |
|---|---:|---:|
| Unique devices in catchment | 441 | 440 |
| GPS pings in catchment | 11,681 | 8,905 |

Shared devices: 425

Jaccard similarity: 93.20%

## 4. Footfall Analysis Results

- Both stores recorded their highest hourly GPS ping count at 17:00 (5 PM).
- Store A recorded 1,159 GPS pings at its peak hour.
- Store B recorded 1,035 GPS pings at its peak hour.
- The analysis generated daily and hourly activity reports for both stores.
- Overall weekday activity: 733,775 GPS pings.
- Overall weekend activity: 266,225 GPS pings.

## 5. Generated Outputs

The pipeline generated the following reports under `data/processed/`:

- `hourly_footfall.csv`
- `daily_footfall.csv`
- `weekday_weekend_footfall.csv`
- `store_catchment_summary.csv`
- `device_catchment_membership.csv`
- `store_hourly_footfall.csv`
- `store_daily_footfall.csv`

## 6. Limitations

The dataset contains synthetic GPS observations. Catchment presence indicates simulated geographic proximity, not verified store visits, transactions, or actual customer behaviour.

Execution time and peak memory consumption were not benchmarked in this test.