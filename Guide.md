# GeoPulse: Spatial Data Engineering Pipeline

## 🎯 What We Are Trying to Achieve
The goal of this backend pipeline is to process millions of raw, anonymized mobile GPS pings and map them to specific physical retail locations. By calculating spatial intersections at scale, we translate raw coordinate data into actionable business intelligence: identifying high-traffic zones and measuring the cannibalization (customer overlap) between existing and proposed store locations.

This pipeline intentionally separates storage, heavy spatial compute, and business logic using a modern data stack.

---

## 🏗️ Core Technology Stack

1. **Snowflake (Data Lakehouse)**
   * **Role:** Central storage for raw GPS data, store boundary polygons, and finalized analytical tables.
   * **Key Feature:** Native `GEOGRAPHY` data types and decoupled storage/compute.
2. **Apache Sedona on PySpark (Spatial Transformation)**
   * **Role:** Distributed computing engine to execute heavy point-in-polygon spatial joins.
   * **Key Feature:** Bypasses single-machine memory limits (OOM errors) by distributing billions of spatial calculations across a cluster.
3. **dbt (Data Modeling)**
   * **Role:** Orchestrates complex SQL transformations (window functions, set intersections) directly inside Snowflake.
   * **Key Feature:** Modularizes the cannibalization logic and aggregates the raw spatial joins into clean, hourly metrics.

---

## 🛠️ Step-by-Step Implementation Guide

### Step 1: Data Ingestion (Snowflake)
Before any processing happens, the raw mock data must be loaded into the data warehouse.

1. **Provision Snowflake:** Create a database and compute warehouse.
2. **Define Raw Schemas:**
   * Create a `raw_gps_pings` table (`DeviceID` VARCHAR, `Lat` FLOAT, `Long` FLOAT, `Timestamp` TIMESTAMP).
   * Create a `store_boundaries` table (`StoreID` VARCHAR, `StoreType` VARCHAR, `Boundary` GEOGRAPHY).
3. **Load Data:** Ingest the synthesized CSV/Parquet files into these raw tables using Snowflake's `COPY INTO` command or Snowpipe.

### Step 2: Distributed Spatial Joins (PySpark & Apache Sedona)
This is the heavy lifting. We extract the raw data, run the spatial math in Spark, and load the results back.

1. **Environment Setup:** Spin up a PySpark cluster and install the Apache Sedona libraries (`sedona-spark`, `sedona-python`).
2. **Snowflake Connection:** Configure the Spark-Snowflake connector to read `raw_gps_pings` and `store_boundaries` into Spark DataFrames.
3. **Spatial Registration:** 
   * Convert the raw `Lat`/`Long` floats into Sedona `ST_Point` geometry objects.
   * Register Sedona's User Defined Types (UDTs) and functions with the Spark SQL context.
4. **Execute the Spatial Join:**
   * Run a distributed SQL query inside Spark using `ST_Contains` or `ST_Intersects` to check which points fall inside which polygons.
   ```sql
   SELECT p.DeviceID, p.Timestamp, s.StoreID 
   FROM pings p, stores s 
   WHERE ST_Contains(s.Boundary, ST_MakePoint(p.Long, p.Lat))
   ```
5. **Write Back:** Write the resulting matched DataFrame back to a new Snowflake table called `spatial_matches`.

### Step 3: Business Logic & Aggregation (dbt)
With the devices successfully mapped to stores, dbt runs SQL directly against the `spatial_matches` table in Snowflake to calculate our core metrics.

1. **Initialize dbt:** Connect dbt to the Snowflake warehouse and define the `spatial_matches` table as a source.
2. **Model 1: Hourly Footfall (Base Aggregation)**
   * Write a dbt model (SQL file) to group the data by `StoreID` and `DATE_TRUNC('hour', Timestamp)`.
   * Count distinct `DeviceID`s to filter out noise and get true visitor counts.
3. **Model 2: Cannibalization Logic (Complex SQL)**
   * Write a dbt model that isolates devices visiting a 'Proposed' store.
   * Use an `INNER JOIN` or `INTERSECT` against devices visiting 'Existing' stores within a specific time window.
   * Calculate the percentage overlap: `(Shared Visitors / Total Proposed Visitors) * 100`.
4. **Materialization:** Configure dbt to materialize these models as clean, finalized `VIEW`s or `TABLE`s in Snowflake, ready to be queried by the backend API.