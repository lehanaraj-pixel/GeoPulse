# GeoPulse – Synthetic GPS Mobility Data Generator

Data-engineering component of **GeoPulse – Hyper-Local Retail Mobility Analytics**.

## 1. Project overview

GeoPulse helps retailers judge potential store locations by analysing anonymised human movement: footfall patterns,
visitor overlap between two stores, and cannibalisation. The analytics pipeline uses Snowflake (GEOGRAPHY), Apache
Spark / Sedona, dbt and Kepler.gl. This repository contains the **data generation and validation** layer:

- `generate_gps_data.py` – simulates 100K to 10M GPS pings of devices that commute, work, shop and rest over many days
  (24 hours a day, weekday/weekend behaviour, dwell times, GPS noise, visits to Store A, Store B, both or neither).
- `validate_data.py` – streaming data-quality report (integrity, 24-hour coverage, realistic movement, catchment coverage).
- `config.py` – every tunable parameter, including the city bounding box, the Store A / Store B coordinates and the 500 m
  catchment radius.

**No real personal or location-tracking data is used.** Everything is generated from a seeded random model.

> ### ⚠️ Placeholder geography
> The brief did not specify the city bounds or store coordinates. `config.py` therefore ships **illustrative placeholder
> values** (a ~16 km × 16 km box and two fictitious points ~0.7 km apart). They are **not real store locations** and must
> be replaced with your own. Until you set `geography_is_placeholder = False`, the generator and validator print a
> warning, and `Config.validate()` refuses `False` while any placeholder value is still in use.

## 2. Architecture and workflow

```
config.py ─────────────┐
                       ▼
          generate_gps_data.py ──► data/gps_data.csv  (appended chunk by chunk)
          (city layout → devices → daily     data/gps_data.manifest.json (config snapshot, counts)
           itineraries → pings → CSV)                    │
                                                         ▼
                                              validate_data.py ──► console report (+ optional JSON)
                                                         │
                                  (your pipeline)        ▼
                          Snowflake stage → raw table → GEOGRAPHY points → dbt / Sedona / Kepler.gl
```

```
GeoPulse_Data_Engineering/
├── config.py                 # all editable parameters (dataclass Config)
├── generate_gps_data.py      # vectorised, chunked generator → CSV + manifest
├── validate_data.py          # streaming validation report
├── requirements.txt
├── README.md
├── .gitignore
├── docs/
│   ├── data_dictionary.md        # every column / manifest field explained
│   └── simulation_methodology.md # how the mobility model works
└── data/
    ├── .gitkeep
    ├── sample_gps_data.csv             # 50,000 rows, 7 days, seed 7
    └── sample_gps_data.manifest.json
```

Design points: NumPy-vectorised simulation per chunk of devices; chunks are appended to the CSV so the dataset never sits
in RAM; identical seed + configuration gives an identical file; the generator hits the requested record count exactly.
Details are in [docs/simulation_methodology.md](docs/simulation_methodology.md).

## 3. Installation

Requires **Python 3.11 or newer**.

**Windows PowerShell**
```powershell
cd GeoPulse_Data_Engineering
py -3.11 -m venv .venv          # or: python -m venv .venv
.\.venv\Scripts\Activate.ps1     # if blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Linux / macOS**
```bash
cd GeoPulse_Data_Engineering
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Dependencies: NumPy, pandas, and `tzdata` on Windows only (needed by the standard-library `zoneinfo`).

## 4. Execution commands

Run from the project folder (all outputs go to `data/` unless `--output` says otherwise).

```powershell
# Default: 1,000,000 records, 14 days, seed 42  ->  data\gps_data.csv
python generate_gps_data.py

# 100,000 records, 7 days
python generate_gps_data.py --records 100000 --days 7 --output data\gps_100k.csv

# 1,000,000 records, 14 days
python generate_gps_data.py --records 1000000 --days 14 --output data\gps_1m.csv

# 10,000,000 records, 28 days (about 640 MB of CSV)
python generate_gps_data.py --records 10000000 --days 28 --output data\gps_10m.csv

# Validate a file
python validate_data.py --input data\gps_1m.csv
```

| Option | Meaning |
|--------|---------|
| `--records N` | Exact number of records (default from `config.py`: 1,000,000) |
| `--devices N` | Fix the number of devices instead (record count then follows from the simulation) |
| `--days N` | Number of simulated days (default 14; use ≥ 7 for weekday/weekend and weekly trends) |
| `--start-date YYYY-MM-DD` | First simulated day (default 2026-01-05, a Monday) |
| `--seed N` | Random seed (default 42) |
| `--ping-interval-min M` | Nominal ping interval in minutes (default 15) |
| `--output PATH` | Output CSV path |
| `--quiet` | No progress output |

More days at a fixed record count means more devices (roughly 45 pings per device per day with the defaults).
Each run writes `<output>.manifest.json` next to the CSV.

## 5. Dataset schema

| Column | Example | Type | Description |
|--------|---------|------|-------------|
| `DeviceID` | `DEV_5A0B773D67ACEAF6` | string | Anonymous, persistent device identifier |
| `Latitude` | `13.085890` | float (6 decimals) | WGS-84 latitude |
| `Longitude` | `80.184513` | float (6 decimals) | WGS-84 longitude |
| `Timestamp` | `2026-01-05 08:15:32+05:30` | string | Asia/Kolkata local time with explicit offset |

Rows are grouped by device and chronologically ordered within each device. Full definitions, guarantees and the manifest
fields are in [docs/data_dictionary.md](docs/data_dictionary.md).

## 6. Configuration

All settings are fields of the `Config` dataclass in `config.py`; edit the defaults or override a few on the command line.

**Geography – required input**

```python
lat_min, lat_max = ..., ...          # city bounding box (degrees)
lon_min, lon_max = ..., ...
store_a = (lat, lon)                 # Store A
store_b = (lat, lon)                 # Store B
catchment_radius_m = 500.0           # catchment radius used by the validator and for analysis
geography_is_placeholder = False     # set to False once real values are entered
```

Both stores must lie inside the bounding box. Choose a box of at least a few kilometres across (the generator needs room
for zones). The further apart the stores are, the smaller the catchment overlap.

**Other useful settings**

| Setting | Default | Purpose |
|---------|---------|---------|
| `seed` | 42 | Reproducibility |
| `target_records`, `num_days`, `start_date` | 1,000,000 / 14 / 2026-01-05 | Volume and time span (`timezone` is `Asia/Kolkata`) |
| `holidays` | none | Dates that behave like weekends |
| `zone_share_near_stores` | 0.35 | Share of homes/workplaces placed near the stores (traffic into the catchments) |
| `store_customer_base_prob`, `store_customer_proximity_boost`, `store_loyalty` | 0.12 / 0.50 / 0.85 | How many devices are store customers and how loyal they are |
| `ping_interval_seconds`, `device_keep_prob_mean`, `hourly_ping_activity` | 900 / 0.65 / 24-hour profile | Ping density and its daily rhythm |
| `gps_noise_sigma_m` | 10 | GPS error |
| `chunk_device_days` | 15,000 | Memory per chunk |
| `min_devices_per_store`, `min_devices_in_both`, `overnight_hours`, ... | see file | Validation thresholds |

A short walkthrough of how these parameters drive the simulation is in
[docs/simulation_methodology.md](docs/simulation_methodology.md).

## 7. Validation

```powershell
python validate_data.py --input data\gps_1m.csv
```

The file is streamed in chunks (`validation_chunk_rows`, default 250,000). Nothing is removed or repaired; every problem is
counted and reported, and the exit code is 1 if any check fails (0 otherwise).

Checks: record count (vs. manifest or `--expected-records`), missing values, duplicate rows and duplicate (DeviceID,
Timestamp) keys, invalid/non-numeric/out-of-range coordinates, invalid timestamps (format, `+05:30` offset, date range),
DeviceID format and contiguity, chronological order per device, implied-speed plausibility, records outside the city bounds,
minimum devices in the Store A / Store B / both catchments, **24-hour coverage** (all hours populated, overnight records,
sleeping hours vs daytime) and **daily-pattern sanity** (commute-hour movement vs overnight and midday, weekday vs weekend
mornings, evening vs overnight catchment activity).

The report also lists unique devices per store, both-store overlap, repeat visitors, daily/hourly unique visitors and an
hourly profile table. Options: `--expected-records N`, `--chunk-rows N`, `--json-report FILE`, and `--hourly-warn-only`
(downgrades the 24-hour checks to warnings, for files generated before 24-hour pinging existed).

## 8. Snowflake ingestion preparation

The CSV is ready for Snowflake without transformation. The statements below are a starting point; they were **not executed
against a Snowflake account** in this project, so adapt names and the stage to your environment.

```sql
-- 1) File format and stage
CREATE OR REPLACE FILE FORMAT geopulse_csv
  TYPE = CSV FIELD_DELIMITER = ',' SKIP_HEADER = 1;
CREATE OR REPLACE STAGE geopulse_stage FILE_FORMAT = geopulse_csv;

-- 2) Upload from SnowSQL (Windows path example), then load into a raw table
PUT file://C:/path/to/GeoPulse_Data_Engineering/data/gps_1m.csv @geopulse_stage AUTO_COMPRESS=TRUE;

CREATE OR REPLACE TABLE raw_gps_pings (
  device_id VARCHAR(20), latitude FLOAT, longitude FLOAT, ts_text VARCHAR(32));
COPY INTO raw_gps_pings FROM @geopulse_stage/gps_1m.csv.gz;

-- 3) Typed table with GEOGRAPHY points (note: longitude first)
CREATE OR REPLACE TABLE gps_pings AS
SELECT device_id,
       latitude, longitude,
       TO_TIMESTAMP_TZ(ts_text, 'YYYY-MM-DD HH24:MI:SSTZH:TZM') AS ts,
       ST_MAKEPOINT(longitude, latitude)                         AS geo_point
FROM raw_gps_pings;

-- 4) 500 m catchment test (replace the placeholders with YOUR store coordinates)
SELECT COUNT(DISTINCT device_id)
FROM gps_pings
WHERE ST_DWITHIN(geo_point, ST_MAKEPOINT(<STORE_A_LON>, <STORE_A_LAT>), 500);
```

Preparation tips: validate the file with `validate_data.py` first; the file is sorted by device then time, so it can be loaded
in any order; for 10M rows split the CSV or load it directly (Snowflake compresses and parallelises staged files); keep the
manifest with the data for lineage; because timestamps carry the +05:30 offset, `TIMESTAMP_TZ` keeps the local time, and
`CONVERT_TIMEZONE('UTC', ts)` gives UTC when needed.

## 9. Known assumptions and limitations

- The city bounds and store coordinates are **placeholders** until you replace them (see the warning at the top).
- The behavioural parameters are plausible defaults, **not calibrated** to any real city or retailer (see
  [docs/simulation_methodology.md](docs/simulation_methodology.md)).
- Pings are sparse and device-dependent; short store visits can be missed. Devices passing through a catchment also emit pings,
  so "ping in catchment" is not "visit" – define visits (dwell, ping count) downstream.
- Catchment overlap is strongly shaped by the geometry: with stores ~0.7 km apart, a large share of devices appears in both
  catchments. Move the stores apart or lower `zone_share_near_stores` for less overlap.
- Movement follows L-shaped street-grid paths, not a real road network; everyone is at home overnight (low ping rate, no movement).
- Timestamps use a fixed UTC offset; date ranges spanning a DST change are rejected (Asia/Kolkata has none).
- Reproducibility requires the same seed **and** configuration (including `chunk_device_days`) and the same NumPy major version.
- For an exact record count the tail of the last device may be trimmed.
- Validating 10M records needs about 1 GB of memory because the duplicate check keeps one 64-bit hash per record.
- The weekday/weekend check treats the dates in `holidays` as weekends; other national holidays are not modelled.
