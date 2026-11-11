# GeoPulse – Data Dictionary

All data is **synthetic**. No real person, device or location-tracking record was used.
The bounding box and the Store A / Store B coordinates come from `config.py`; the values shipped
with the project are **illustrative placeholders, not real store locations**.

## 1. GPS pings file (`gps_data.csv`, `sample_gps_data.csv`)

Plain CSV, UTF-8, comma-delimited, one header row, `\n` line endings, no quoting needed.
One row = one GPS ping emitted by one anonymous device.

| # | Column | CSV representation | Recommended Snowflake type | Nullable | Meaning |
|---|--------|--------------------|----------------------------|----------|---------|
| 1 | `DeviceID` | `DEV_` followed by 16 upper-case hexadecimal characters, e.g. `DEV_5A0B773D67ACEAF6` (regex `^DEV_[0-9A-F]{16}$`) | `VARCHAR(20)` | No | Anonymous, persistent identifier of one simulated device. The same device always has the same ID in every row and every day of a file. It is the output of a bijective 64-bit hash of a device counter and the seed, so it cannot be traced back to a person and two devices never share an ID. |
| 2 | `Latitude` | Decimal degrees, 6 decimals, WGS-84, e.g. `13.085890` | `FLOAT` (or `NUMBER(9,6)`) | No | North/south position of the ping. Always within `lat_min..lat_max` from `config.py` and within -90..90. Includes simulated GPS error (normally ~10 m, rare ~60 m outliers). |
| 3 | `Longitude` | Decimal degrees, 6 decimals, WGS-84, e.g. `80.184513` | `FLOAT` (or `NUMBER(9,6)`) | No | East/west position of the ping. Always within `lon_min..lon_max` from `config.py` and within -180..180. Note: GEOGRAPHY constructors take **longitude first**. |
| 4 | `Timestamp` | `YYYY-MM-DD HH:MM:SS+05:30`, e.g. `2026-01-05 08:15:32+05:30` | `TIMESTAMP_TZ(0)` | No | Moment of the ping in **Asia/Kolkata** local time with an explicit UTC offset (+05:30; India has no daylight saving). Resolution is one second. Timestamps cover the full 24 hours of every simulated day (00:00:00 – 23:59:59). |

### Guarantees (checked by `validate_data.py`)

- No missing values in any column; no duplicate rows; no duplicate (`DeviceID`, `Timestamp`) pairs.
- Rows are grouped by device (all rows of one device are contiguous) and are in strictly increasing time order
  within each device.
- The implied speed between consecutive pings of a device is plausible (default limit 150 km/h; the generator's
  fastest legs are ~40 km/h plus GPS noise), i.e. devices do not teleport.
- Every ping lies inside the configured city bounding box.
- The date range equals `start_date` .. `start_date + num_days - 1`.

### Not in the file

The simulator knows each device's home, workplace, persona and store segment, but **none of this ground truth is
written to the CSV** – the file contains only the four mandatory columns, as downstream analytics would receive them.

## 2. Manifest file (`<output>.manifest.json`)

Written next to every generated CSV. It records exactly how the file was produced so it can be reproduced.

| Field | Type | Meaning |
|-------|------|---------|
| `generator_version` | string | Version of `generate_gps_data.py` that produced the file. |
| `generated_at` | string (ISO 8601) | Wall-clock time of generation, with the machine's UTC offset. Differs between runs; the CSV does not. |
| `records_written` | integer | Exact number of data rows in the CSV (header excluded). |
| `devices_written` | integer | Number of distinct `DeviceID` values in the CSV. |
| `chunks` | integer | Number of device chunks simulated. |
| `elapsed_seconds` | number | Generation time. |
| `config` | object | Complete snapshot of every `Config` field used (seed, dates, geography, store coordinates, catchment radius, behaviour and ping parameters, `geography_is_placeholder`, ...). `output_path` is stored relative to the project folder. |

`validate_data.py` reads `records_written` (expected row count), `start_date`, `num_days` and `holidays` from the manifest
when it is present.

## 3. Validation report (`validate_data.py` output)

| Item | Meaning |
|------|---------|
| Total records / Unique devices | Row count and number of distinct `DeviceID` values found in the file. |
| Records/device, Records/day | Minimum / median (or mean) / maximum. |
| Pings inside | Number of pings within `catchment_radius_m` (default 500 m, haversine distance) of Store A, Store B, and of both (overlap zone). |
| Unique devices A / B / both | Distinct devices with at least one ping inside Store A's catchment, Store B's catchment, or both. "A only"/"B only" are the remainders. |
| Overlap | Share of Store A's visitors who also appear in Store B's catchment (and vice versa); Jaccard similarity of the two visitor sets. |
| Repeat visitors | Devices seen in a catchment on at least two distinct days. |
| Both stores on different days | Devices seen in both catchments with at least one A-day that differs from a B-day. |
| Daily / hourly unique visitors | Mean distinct devices per day (weekday vs weekend) and per hour of day in each catchment, plus the busiest hour of day. |
| Hourly profile | Per local hour 00–23: record count and share, share of consecutive ping pairs that show movement (> 150 m within 30 min) on weekdays and weekends, and pings inside the store catchments. |
| Checks | `PASS`, `WARN` or `FAIL` for each rule; the process exit code is 1 if any check fails. |

Terminology: a *ping in a catchment* is not necessarily a *store visit* – devices passing through also emit pings.
Visit definitions (minimum dwell time, minimum ping count) are an analytic decision for the downstream dbt models.
