# GeoPulse

**Geospatial Retail Mobility & Cannibalization Analytics Platform**

GeoPulse is a retail site-selection and foot-traffic analytics platform built to help retail teams evaluate store performance, map dynamic trade areas, and quantify cannibalization risk before signing a new commercial lease.

Instead of relying on static census rings or drive-time polygons, GeoPulse processes raw mobile GPS telemetry at scale using **PySpark** and **Apache Sedona** to measure real-world human mobility, visitor overlap, and projected financial impact.

---

## Business Problem

Opening a new store too close to an existing location can cannibalize existing sales—splitting the same customer base across two leases and two payrolls. Conversely, moving too far away just to avoid overlap can push a retailer out of high-demand commercial zones.

GeoPulse helps real estate and operations teams:
* **Quantify true customer overlap** using anonymized `DeviceID` trajectories rather than geometric assumptions (capturing real-world barriers like highways, railways, and intersections).
* **Balance capacity relief vs. over-cannibalization** by separating healthy relief zones (10% to 20% erosion) from high-risk overlap (above 20% erosion).
* **Measure location strength vs. storefront appeal** by separating neighborhood foot traffic from confirmed in-store visits.

---

## System Architecture

GeoPulse uses a **decoupled batch-processing architecture**. Heavy spatial computation runs asynchronously on a schedule, writing lightweight aggregated results to the data warehouse/database. The live backend API reads only these precomputed summaries—it never communicates directly with the Spark engine, keeping the frontend fast and resilient even if a batch job is delayed.

```text
Raw GPS Telemetry (CSV / Cloud Storage)
        │
        ▼
  Data Warehouse (Snowflake)
        │
        ▼
  Scheduled Batch Engine (PySpark + Apache Sedona + dbt)
        │  [Spatial joins, sessionization, Huff defection, aggregations]
        ▼
  Aggregated Analytics Tables / JSON Output
        │
        ▼
  Backend REST API (Node.js / Express)
        │
        ▼
  Interactive Dashboard (React + Leaflet)
```

### Local Development vs. Cloud MVP

| Layer | Local Setup (Development & Testing) | Cloud MVP (Hosted 24/7) |
| :--- | :--- | :--- |
| **Raw Data** | Local CSV files / Google Drive | Cloud object storage bucket or Snowflake staging |
| **Spatial Processing** | Local PySpark / Google Colab | Scheduled remote runner (GitHub Actions / Cloud VM) |
| **Storage** | Local database or exported JSON | Snowflake / Managed Cloud DB (Neon / Supabase) |
| **Backend API** | Local Node/Express server | Hosted web service querying the cloud DB |
| **Frontend UI** | Local React + Leaflet dev server | Deployed static/web host fetching from Backend API |

---

## Tech Stack

* **Spatial Processing:** PySpark 4.x, Apache Sedona 1.9.x (with pure Catalyst Haversine fallback)
* **Data Warehouse & Modeling:** Snowflake, dbt (BigQuery GIS is also supported as an alternative)
* **Backend API:** Node.js, Express
* **Frontend Visualization:** React, Leaflet
* **Input Schema:** `DeviceID`, `Latitude`, `Longitude`, `Timestamp`

---

## Core Analytics & Metrics

### 1. Single-Store Mobility Analytics
Uses a **two-tier spatial filter** to separate neighborhood passersby from confirmed shoppers:
* **Broad Catchment Radius** (default $500\text{ m}$): Captures total unique devices active in the surrounding neighborhood.
* **Tight Visit Radius** (default $20\text{ m}$): Isolates devices physically inside or immediately at the storefront.

**Key Features & Metrics:**
* **Sessionization & Noise Filtering:** Groups storefront pings using either fixed 1-hour windows or gap-based sessionization (new session after $30\text{ min}$ of inactivity) and requires a minimum ping threshold (`min_pings`) to filter out drive-bys.
* **Staff Filtering:** Flags and excludes suspected store employees (devices averaging $\ge 180\text{ min}$ per session) via a `left_anti` join so employee shifts do not skew dwell-time averages.
* **Conversion Funnel:** Catchment Capture Rate (confirmed customers / catchment devices) vs. Storefront Conversion Rate (qualified visits / total storefront sessions including pass-bys).
* **Engagement & Dwell Time:** Average pings per visit, mean and median dwell time in minutes, and dwell-time buckets ($<10\text{ min}$, $10\text{–}30\text{ min}$, $>30\text{ min}$).
* **Loyalty & Temporal Patterns:** Repeat customer rate, visits per customer, peak hour, day-of-week distribution, and weekday vs. weekend split.
* **Observed Trade Area Pull:** Median and 75th-percentile maximum roaming distance of confirmed customers across the dataset.

---

### 2. Two-Store Cannibalization & Expansion Engine
Combines industry frameworks from **Umbrex**, **GrowthFactor**, **PassBy**, **Esri ArcGIS Business Analyst**, **Placer.ai**, and the **Huff Gravity Model**. Supports two execution modes:
* `mode="expansion"`: Compares an existing Store $A$ against a proposed candidate Site $B$.
* `mode="existing_pair"`: Analyzes cross-visitation and portfolio overlap between two already-operating stores.

#### Key Formulas

* **Proximity Overlap (Jaccard Catchment Overlap):**
  $$\text{Proximity Overlap (\%)} = \frac{|C_A \cap C_B|}{|C_A \cup C_B|} \times 100$$

* **Directional Trade Area Overlap (Esri):**
  $$\text{Store } A \text{ within } B = \frac{|C_A \cap C_B|}{|C_A|} \times 100, \qquad \text{Store } B \text{ within } A = \frac{|C_A \cap C_B|}{|C_B|} \times 100$$

* **Huff Gravity Defection Probability** (for each Store $A$ customer $i$ exposed to Site $B$'s catchment, using their activity centroid distance $D$ and decay exponent $\beta$):
  $$P_{iB} = \frac{A_B D_{iB}^{-\beta}}{A_A D_{iA}^{-\beta} + A_B D_{iB}^{-\beta}}$$

* **Dual Cannibalization Rates** (reported side-by-side to avoid denominator ambiguity):
  $$\text{Existing Store Erosion Rate (Umbrex)} = \frac{\text{Est. Transferred Visits from } A}{\text{Baseline Visits at } A} \times 100$$
  $$\text{New Store Cannibalization Rate (GrowthFactor / PassBy)} = \frac{\text{Est. Transferred Visits from } A}{\text{Projected Visits at } B} \times 100$$

* **Net Incremental Sales & Profit Impact** (corrected to avoid double-counting cannibalized revenue):
  $$\text{Incremental Sales} = \text{Projected Store } B \text{ Sales} - \text{Cannibalized Sales from } A$$
  $$\text{Net Profit Impact} = (\text{Incremental Sales} \times \text{Profit Margin}) - \text{New Store Fixed Cost}$$

#### Automated Risk Tiers
* **`LOW_RISK_STRONG_EXPANSION`**: Existing store erosion $< 10\%$ and directional overlap $\le 40\%$.
* **`MODERATE_RISK_CAPACITY_RELIEF_ZONE`**: Existing store erosion between $10\%$ and $20\%$ (viable for relieving overcrowded stores or blocking competitors).
* **`HIGH_RISK`**: Existing store erosion $> 20\%$ or Store $B$'s catchment overlap with Store $A$ $> 40\%$.

---

## Running the Analytics Engine

### Prerequisites
* **Java:** OpenJDK 17 or 21 (required for PySpark 4.x)
* **PySpark:** `4.0.x` (tested on `4.0.5` with `SPARK_HOME` unset)
* **Apache Sedona:** `apache-sedona==1.9.1`

> **Environment Note:** Always match the Sedona Spark JAR major/minor version to your installed PySpark version (e.g., `sedona-spark-4.0_2.13:1.9.1` + `geotools-wrapper:1.9.1-33.5` for PySpark 4.0.x). Avoid reinstalling `pyspark` inside an active notebook kernel without restarting the runtime, as mismatched JVM/Python bytecode will trigger Py4J `JavaPackage` errors. For environments where Maven JAR downloads are blocked, use the native PySpark Catalyst Haversine mode (`use_sedona=False`).

### Quick Start in Google Colab

1. Install Apache Sedona (do not overwrite Colab's pre-installed PySpark 4.0.x) and mount Google Drive:

```python
!pip install -q apache-sedona==1.9.1

from google.colab import drive
drive.mount("/content/drive")
```

2. Run the two-store cannibalization analysis and export the JSON report:

```python
import json
from pathlib import Path

report = analyze_two_store_cannibalization(
    csv_path="/content/drive/MyDrive/Colab Notebooks/Data/Geopulse_Infotact_Internship/bengaluru_test_1m.csv",
    store_a={"name": "Store A (Existing)", "lat": 12.978973, "lon": 77.64527},
    store_b={"name": "Store B (Candidate)", "lat": 12.973500, "lon": 77.64120},
    mode="expansion",
    catchment_radius=500,
    visit_radius=20,
    min_pings=3,
    avg_spend_per_visit=300.0,
    profit_margin_pct=0.35,
    new_store_fixed_cost=150000.0,
)

output_path = Path(
    "/content/drive/MyDrive/Colab Notebooks/Data/Geopulse_Infotact_Internship/cannibalization_report.json"
)
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, default=str)
```

### Running via CLI (Single-Store Extended Script)

```bash
python analyze_store.py \
  --input bengaluru_test_1m.csv \
  --lat 12.978973 \
  --lon 77.64527 \
  --catchment-radius 500 \
  --visit-radius 20 \
  --min-pings 3 \
  --session-gap 30 \
  --output reports/store_metrics.json
```

---

## Sample Output Schema (Cannibalization Report)

```json
{
  "stores": {
    "mode": "expansion",
    "store_separation_m": 750.2,
    "catchment_radius_m": 500
  },
  "trade_area_overlap": {
    "store_a_catchment_devices": 4210,
    "store_b_catchment_devices": 3890,
    "shared_catchment_devices": 612,
    "net_new_catchment_devices_for_b": 3278,
    "umbrex_proximity_overlap_pct": 8.17,
    "esri_store_a_within_b_pct": 14.54,
    "esri_store_b_within_a_pct": 15.73
  },
  "huff_gravity_defection": {
    "store_a_baseline_customers": 640,
    "store_a_customers_exposed_to_b": 92,
    "avg_defection_probability_pct": 41.3,
    "expected_transferred_visits": 68.4
  },
  "cannibalization_metrics": {
    "projected_or_actual_store_b_visits": 945.2,
    "net_incremental_visits": 876.8,
    "umbrex_existing_store_erosion_pct": 7.12,
    "growthfactor_new_store_cannibalization_pct": 7.24,
    "risk_verdict": "LOW_RISK_STRONG_EXPANSION"
  },
  "financial_impact_estimate": {
    "projected_store_b_sales": 283560.0,
    "cannibalized_sales_from_a": 20520.0,
    "umbrex_incremental_sales": 263040.0,
    "net_profit_impact": -57936.0
  }
}
```

---

## Roadmap

* [ ] Replace circular visit radii with exact building footprints using Sedona `ST_Contains` polygon joins.
* [ ] Multi-candidate batch scoring to rank 5+ proposed store locations by net incremental visits and profit.
* [ ] Automate nightly PySpark runs via GitHub Actions pushing summaries into Snowflake/PostgreSQL.
* [ ] Connect the React + Leaflet frontend directly to the Express API serving live cannibalization overlays.