# Airbnb London Data Pipeline — Technical Documentation

> **Project:** `expernetic-airbnb-pipeline`
> **Data Source:** [Inside Airbnb](https://insideairbnb.com) — London, England (December 2024 snapshot)
> **Author:** Sukitha Rathnayake

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Technologies Used](#3-technologies-used)
4. [Project Structure](#4-project-structure)
5. [Step-by-Step Implementation](#5-step-by-step-implementation)
   - [Step 1: Local Exploration & EDA](#step-1-local-exploration--eda)
   - [Step 2: Data Ingestion — Bronze Layer](#step-2-data-ingestion--bronze-layer)
   - [Step 3: GeoJSON Ingestion](#step-3-geojson-ingestion)
   - [Step 4: dbt Transformation — Staging Layer (Silver)](#step-4-dbt-transformation--staging-layer-silver)
   - [Step 5: dbt Transformation — Marts Layer (Gold)](#step-5-dbt-transformation--marts-layer-gold)
   - [Step 6: Data Quality Tests](#step-6-data-quality-tests)
6. [Data Models](#6-data-models)
7. [Running the Pipeline](#7-running-the-pipeline)

---

## 1. Project Overview

This project builds an **end-to-end data engineering pipeline** for Airbnb listing data in London, UK. It ingests publicly available data from Inside Airbnb, stores it in Google Cloud Storage and BigQuery, and then transforms it into analytics-ready dimensional models using dbt.

The pipeline follows the **Medallion Architecture** pattern (Bronze → Silver → Gold), enabling clean, tested, and reusable data for downstream analytics and BI reporting.

### Key Goals

- Automate the download and ingestion of raw Airbnb data into Google Cloud.
- Handle both tabular (CSV) and geospatial (GeoJSON) data formats.
- Transform raw data into clean, well-documented staging models.
- Build enriched analytics-ready mart models (dimensions + facts).
- Enforce data quality through automated dbt tests.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA PIPELINE FLOW                             │
└─────────────────────────────────────────────────────────────────────────┘

 Inside Airbnb (Public HTTP)
         │
         │  listings.csv.gz, calendar.csv.gz,
         │  reviews.csv.gz, neighbourhoods.geojson
         ▼
┌─────────────────────┐
│   ingest.py /       │   Python scripts with HTTP streaming,
│   ingest_geojson.py │   retry logic & GeoJSON → NDJSON flattening
└─────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│         BRONZE LAYER  (Google Cloud Storage)        │
│   Bucket: sukitha-airbnb-raw-data-london            │
│   - listings.csv.gz                                 │
│   - calendar.csv.gz                                 │
│   - reviews.csv.gz                                  │
│   - neighbourhoods.geojson                          │
└─────────────────────────────────────────────────────┘
         │
         │  BigQuery External/Native tables
         ▼
┌─────────────────────────────────────────────────────┐
│         BRONZE LAYER  (BigQuery Dataset: airbnb_bronze) │
│   - raw_listings                                    │
│   - raw_calendar                                    │
│   - raw_reviews                                     │
│   - raw_neighbourhoods                              │
└─────────────────────────────────────────────────────┘
         │
         │  dbt run (staging models)
         ▼
┌─────────────────────────────────────────────────────┐
│       SILVER LAYER  (dbt Staging Models)            │
│   - stg_listings      (cleaned listings)            │
│   - stg_calendar      (cleaned calendar)            │
│   - stg_reviews       (cleaned reviews)             │
│   - stg_neighbourhoods (geometry as GEOGRAPHY)      │
└─────────────────────────────────────────────────────┘
         │
         │  dbt run (mart models)
         ▼
┌─────────────────────────────────────────────────────┐
│   GOLD LAYER  (BigQuery Dataset: airbnb_gold)       │
│   - dim_listings        (enriched listing dim)      │
│   - dim_hosts           (host-level aggregates)     │
│   - dim_neighbourhoods  (geo-enriched areas)        │
│   - fct_reviews         (reviews with context)      │
│   - fct_availability    (daily calendar fact)       │
└─────────────────────────────────────────────────────┘
         │
         ▼
    Analytics / BI / Reporting
```

---

## 3. Technologies Used

| Technology | Version / Service | Purpose |
|---|---|---|
| **Python** | 3.x | Data ingestion scripting |
| **`requests`** | Latest | HTTP download with streaming & retry |
| **Google Cloud Storage (GCS)** | Cloud Service | Raw data lake (Bronze layer) |
| **`google-cloud-storage`** | Python SDK | GCS client for uploads |
| **Google BigQuery** | Cloud Service | Cloud data warehouse |
| **dbt (data build tool)** | Core | SQL-based transformation framework |
| **BigQuery `ST_GEOGFROMGEOJSON`** | SQL Function | GeoJSON → native GEOGRAPHY type |
| **GeoJSON / NDJSON** | Data Formats | Geospatial neighbourhood data |
| **YAML** | Config Format | dbt sources, schema, and test configs |

---

## 4. Project Structure

```
Airbnb/
├── ingest.py                   # Main ingestion script (CSV/GZ → GCS)
├── ingest_geojson.py           # GeoJSON ingestion + NDJSON flattening
│
├── airbnb_local_sandbox/       # Local EDA environment
│   ├── eda_profiling.ipynb     # Exploratory Data Analysis notebook
│   ├── requirements.txt        # Local Python dependencies
│   └── raw_data/               # Local copy of raw files (~390 MB)
│       ├── Airbnb Listings Data.csv.gz     (~48 MB)
│       ├── Airbnb Calendar Data.csv.gz     (~78 MB)
│       ├── Airbnb Reviews.csv.gz           (~246 MB)
│       └── Neighbourhoods Data.geojson     (~1 MB)
│
└── airbnb_pipeline/            # dbt project root
    ├── dbt_project.yml         # dbt project configuration
    ├── models/
    │   ├── _sources.yml        # Declares BigQuery source tables (Bronze)
    │   ├── staging/            # Silver layer: cleaning & standardisation
    │   │   ├── schema.yml      # Column docs & data quality tests
    │   │   ├── stg_listings.sql
    │   │   ├── stg_calendar.sql
    │   │   ├── stg_reviews.sql
    │   │   └── stg_neighbourhoods.sql
    │   └── marts/              # Gold layer: analytics-ready models
    │       ├── schema.yml      # Column docs & data quality tests
    │       ├── dim_listings.sql
    │       ├── dim_hosts.sql
    │       ├── dim_neighbourhoods.sql
    │       ├── fct_reviews.sql
    │       └── fct_availability.sql
    ├── analyses/
    ├── macros/
    │   └── generate_schema_name.sql  # Custom BigQuery dataset routing
    ├── seeds/
    ├── snapshots/
    └── tests/
```

---

## 5. Step-by-Step Implementation

### Step 1: Local Exploration & EDA

**Directory:** `airbnb_local_sandbox/`

Before building the pipeline, the raw data was downloaded locally and explored using a **Jupyter notebook** (`eda_profiling.ipynb`). This step helped understand:

- Column names, data types, and nullability.
- The shape of each dataset (listings, calendar, reviews, neighbourhoods).
- Anomalies such as price columns stored as strings with `$` prefixes and commas.
- The nested GeoJSON `FeatureCollection` structure of the neighbourhoods file.

**Raw Data Stats:**

| File | Size |
|---|---|
| `Airbnb Listings Data.csv.gz` | ~48 MB |
| `Airbnb Calendar Data.csv.gz` | ~78 MB |
| `Airbnb Reviews.csv.gz` | ~246 MB |
| `Neighbourhoods Data.geojson` | ~1 MB |

---

### Step 2: Data Ingestion — Bronze Layer

**Script:** [`ingest.py`](./ingest.py)

This Python script automates the download of all four raw files from Inside Airbnb and uploads them to **Google Cloud Storage**, forming the **Bronze (raw) layer**.

#### Key Design Decisions

**Streaming download with chunked transfer:**
Files are streamed in 1 MB chunks to avoid loading large compressed files (up to 246 MB) entirely into memory.

```python
response = session.get(url, stream=True, timeout=(10, None))
for chunk in response.iter_content(chunk_size=1024 * 1024):
    if chunk:
        f.write(chunk)
```

**HTTP retry strategy:**
A `requests.adapters.Retry` object is configured to automatically retry on transient HTTP errors (429, 500, 502, 503, 504) with exponential back-off. Status 403 (hard block) is deliberately excluded.

```python
retry = requests.adapters.Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
```

**Browser-like headers:**
A realistic User-Agent and Referer header are used to avoid bot-detection blocks from the source server.

**GCS upload with extended timeouts:**
The upload uses `DEFAULT_RETRY` with a 15-minute deadline to handle large files reliably over the network.

```python
blob.upload_from_filename(
    tmp_path,
    timeout=300,
    retry=DEFAULT_RETRY.with_deadline(900),
)
```

**Temp file cleanup:**
A `try/finally` block ensures the local `/tmp/` file is always deleted, even if an error occurs mid-upload.

---

### Step 3: GeoJSON Ingestion

**Script:** [`ingest_geojson.py`](./ingest_geojson.py)

The neighbourhoods GeoJSON file uses a **nested `FeatureCollection`** format that cannot be directly loaded into BigQuery as a flat table. This script handles the transformation.

#### Process

1. Downloads the GeoJSON from Inside Airbnb.
2. Parses the `FeatureCollection` and iterates over each `Feature`.
3. **Flattens** each feature into a flat row:
   - `neighbourhood` — the neighbourhood name (string)
   - `neighbourhood_group` — the parent borough (string)
   - `geometry_json` — the geometry polygon as a raw JSON string
4. Writes rows in **Newline Delimited JSON (NDJSON)** format, which BigQuery natively supports for loading.

```python
row = {
    "neighbourhood": feature["properties"].get("neighbourhood", ""),
    "neighbourhood_group": feature["properties"].get("neighbourhood_group", ""),
    "geometry_json": json.dumps(feature["geometry"])
}
```

The resulting NDJSON file is then loaded into the BigQuery table `airbnb_bronze.raw_neighbourhoods`. The `geometry_json` string column is later converted to BigQuery's native `GEOGRAPHY` type in the dbt staging layer.

---

### Step 4: dbt Transformation — Staging Layer (Silver)

**Directory:** `airbnb_pipeline/models/staging/`

The staging layer reads from the Bronze BigQuery tables (declared in `_sources.yml`) and applies cleaning, renaming, and type casting to produce standardised, reusable models.

#### `stg_listings.sql`
- Renames `id` → `listing_id`, `name` → `listing_name`.
- Uses `neighbourhood_cleansed` (the standardised neighbourhood field) as `neighbourhood`.
- Casts `price` from string to `FLOAT64`.
- Selects only meaningful analytical columns.

#### `stg_calendar.sql`
- Casts `price` from string to `FLOAT64`.
- Cleans `adjusted_price` by stripping `$` and `,` characters before casting to `FLOAT64`.
- Renames `available` → `is_available` for clarity.

#### `stg_reviews.sql`
- Renames `id` → `review_id` for clarity.
- Selects key review fields: `listing_id`, `date`, `reviewer_id`, `reviewer_name`, `comments`.

#### `stg_neighbourhoods.sql`
- Converts the `geometry_json` string column into a native BigQuery **GEOGRAPHY** type using the `ST_GEOGFROMGEOJSON()` function.
- This enables spatial queries (e.g., point-in-polygon lookups).

```sql
ST_GEOGFROMGEOJSON(geometry_json) AS neighbourhood_boundary
```

---

### Step 5: dbt Transformation — Marts Layer (Gold)

**Directory:** `airbnb_pipeline/models/marts/`

The marts layer joins and aggregates the staging models into analytics-ready **dimension** and **fact** tables, all materialised as **BigQuery tables** in the `airbnb_gold` dataset.

#### `dim_listings.sql` — Listing Dimension (95.1k rows)

The core enriched listing model. Joins `stg_listings` with aggregated metrics from `stg_reviews` and `stg_calendar`:

- **Review metrics** (from `stg_reviews`): `total_reviews`, `first_review_date`, `last_review_date`
- **Calendar metrics** (from `stg_calendar`): `avg_price_next_30_days`, `availability_rate_next_30_days` — computed over a dynamic 30-day window from `CURRENT_DATE()`.

```sql
calendar_metrics AS (
    SELECT
        listing_id,
        AVG(price_usd) AS avg_price_next_30_days,
        COUNTIF(is_available) / COUNT(date) AS availability_rate_next_30_days
    FROM calendar
    WHERE date BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 30 DAY)
    GROUP BY listing_id
)
```

#### `dim_hosts.sql` — Host Dimension (56.1k rows)

Aggregates host-level attributes from `stg_listings`, grouped by `host_id`:

- `total_listings` — number of properties the host manages.
- `neighbourhoods_hosted_in` — array of distinct neighbourhood names.
- `room_types_offered` — array of distinct room types.
- `min_listing_price`, `max_listing_price`, `avg_listing_price` — pricing range.
- `total_reviews_across_listings` — sum of reviews across all their listings.

#### `dim_neighbourhoods.sql` — Neighbourhood Dimension (33 rows)

Joins `stg_neighbourhoods` (with GEOGRAPHY boundaries) with aggregated listing stats per area:

- `neighbourhood_boundary` — native BigQuery GEOGRAPHY polygon for spatial queries.
- `total_listings`, `total_hosts` — supply counts per area.
- `avg_price_usd`, `min_price_usd`, `max_price_usd` — pricing profile per neighbourhood.

#### `fct_reviews.sql` — Reviews Fact Table (1.9M rows)

Enriches individual review records by joining with `dim_listings` to append listing context (name, neighbourhood, room type, host details) to each review.

#### `fct_availability.sql` — Availability Fact Table (34.7M rows)

The highest-volume fact table. Contains one row per listing per calendar day, enriched with listing context from `dim_listings`. Key fields:

- `is_available`, `price_usd`, `adjusted_price_usd`, `minimum_nights`, `maximum_nights` — from `stg_calendar`.
- `listing_name`, `host_id`, `neighbourhood`, `room_type` — from `dim_listings`.
- Derived time fields: `year`, `month`, `month_name`, `day_of_week`, `is_weekend`.

This table is the primary source for pricing trend analysis and occupancy rate calculations.

---

### Step 6: Data Quality Tests

**Files:** `models/staging/schema.yml`, `models/marts/schema.yml`

dbt's built-in testing framework is used to enforce data quality on key columns. Tests are run with `dbt test`.

| Model | Column | Tests Applied |
|---|---|---|
| `stg_listings` | `listing_id` | `unique`, `not_null` |
| `stg_calendar` | `listing_id` | `not_null` |
| `stg_reviews` | `review_id` | `unique`, `not_null` |
| `stg_reviews` | `listing_id` | `not_null` |
| `stg_neighbourhoods` | `neighbourhood` | `unique`, `not_null` |
| `stg_neighbourhoods` | `neighbourhood_boundary` | `not_null` |
| `dim_listings` | `listing_id` | `unique`, `not_null` |
| `fct_reviews` | `review_id` | `unique`, `not_null` |
| `fct_reviews` | `listing_id` | `not_null` |

---

## 6. Data Models

### Source Tables (Bronze — `airbnb_bronze` dataset)

| Table | Description |
|---|---|
| `raw_listings` | Raw property scrape data from London |
| `raw_calendar` | Future availability and pricing time-series |
| `raw_reviews` | Historical guest review log |
| `raw_neighbourhoods` | Flattened GeoJSON neighbourhood boundaries |

### Staging Models (Silver)

| Model | Materialization | Description |
|---|---|---|
| `stg_listings` | View | Cleaned listings with typed columns |
| `stg_calendar` | View | Cleaned calendar with numeric prices |
| `stg_reviews` | View | Cleaned reviews with renamed keys |
| `stg_neighbourhoods` | View | Neighbourhoods with GEOGRAPHY boundaries |

### Mart Models (Gold — `airbnb_gold` dataset)

| Model | Materialization | Rows | Description |
|---|---|---|---|
| `dim_listings` | Table | 95.1k | Listings enriched with review & calendar metrics |
| `dim_hosts` | Table | 56.1k | Host-level aggregates derived from listings |
| `dim_neighbourhoods` | Table | 33 | Neighbourhood boundaries with listing stats |
| `fct_reviews` | Table | 1.9M | Individual reviews enriched with listing context |
| `fct_availability` | Table | 34.7M | Daily calendar fact with pricing & availability |

---

## 6b. dbt Layer Routing Configuration

### `dbt_project.yml` — Schema Assignment

Each model folder is explicitly mapped to a BigQuery dataset via `+schema` in [`dbt_project.yml`](./airbnb_pipeline/dbt_project.yml):

```yaml
models:
  airbnb_pipeline:
    staging:
      +materialized: view
      +schema: silver        # → airbnb_silver
    marts:
      +materialized: table
      +schema: gold          # → airbnb_gold
```

### `macros/generate_schema_name.sql` — Exact Dataset Name Control

By default, dbt constructs dataset names by concatenating the profile's base dataset with the schema suffix (e.g., `airbnb_silver_gold`). A custom macro overrides this behaviour to produce exact dataset names:

```sql
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set schema_map = {
        'silver': 'airbnb_silver',
        'gold':   'airbnb_gold'
    } -%}
    {%- if custom_schema_name is none -%}
        {{ target.dataset }}
    {%- elif custom_schema_name in schema_map -%}
        {{ schema_map[custom_schema_name] }}
    {%- else -%}
        {{ target.dataset }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
```

This ensures:
- `staging/` models → `airbnb_silver` (exact)
- `marts/` models → `airbnb_gold` (exact)

---

## 7. Running the Pipeline

### Prerequisites

- Python 3.x with `google-cloud-storage` and `requests` installed.
- A Google Cloud project with BigQuery and GCS enabled.
- GCP Application Default Credentials configured (`gcloud auth application-default login`).
- dbt Core installed with the BigQuery adapter (`dbt-bigquery`).
- A `~/.dbt/profiles.yml` configured for the `airbnb_pipeline` profile pointing to `expernetic-airbnb-pipeline`.

### Step 1 — Ingest CSV Data to GCS

```bash
python ingest.py
```

Streams all four raw files from Inside Airbnb and uploads them to the GCS bucket `sukitha-airbnb-raw-data-london`.

### Step 2 — Ingest GeoJSON to BigQuery

```bash
python ingest_geojson.py
```

Downloads the GeoJSON, flattens it to NDJSON, and writes it to `/tmp/neighbourhoods.ndjson` (ready for BigQuery load job).

### Step 3 — Load tables into BigQuery

Create the BigQuery tables from GCS (either via the console, `bq load` CLI, or a scheduled job), targeting the `airbnb_bronze` dataset.

### Step 4 — Run dbt Transformations

```bash
cd airbnb_pipeline

# Build all staging and mart models
dbt run

# Run data quality tests
dbt test

# Build and test in one command
dbt build
```

### Step 5 — Explore

Query the gold-layer mart tables in BigQuery for analytics:

```sql
-- Top 10 neighbourhoods by review volume
SELECT neighbourhood, SUM(total_reviews) AS total_reviews
FROM `expernetic-airbnb-pipeline.airbnb_gold.dim_listings`
GROUP BY neighbourhood
ORDER BY total_reviews DESC
LIMIT 10;

-- Weekend vs weekday average pricing per neighbourhood
SELECT
    neighbourhood,
    ROUND(AVG(CASE WHEN is_weekend THEN price_usd END), 2) AS avg_weekend_price,
    ROUND(AVG(CASE WHEN NOT is_weekend THEN price_usd END), 2) AS avg_weekday_price
FROM `expernetic-airbnb-pipeline.airbnb_gold.fct_availability`
WHERE is_available
GROUP BY neighbourhood
ORDER BY avg_weekend_price DESC;

-- Hosts with the most listings
SELECT host_name, total_listings, avg_listing_price
FROM `expernetic-airbnb-pipeline.airbnb_gold.dim_hosts`
ORDER BY total_listings DESC
LIMIT 10;
```

---

*Documentation generated: June 2026*
