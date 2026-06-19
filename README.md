# 🏙️ Airbnb London Rentals — Data Pipeline

> An end-to-end data engineering pipeline for Airbnb listing data in London, UK.  
> Built with **Python**, **Google Cloud Storage**, **BigQuery**, and **dbt** following the **Medallion Architecture** (Bronze → Silver → Gold).

---

## 📐 Architecture

```
Inside Airbnb (Public HTTP)
        │
        │  listings.csv.gz, calendar.csv.gz,
        │  reviews.csv.gz, neighbourhoods.geojson
        ▼
┌─────────────────────────────────┐
│  ingest.py / ingest_geojson.py  │  Python: HTTP streaming, retry logic,
│  (Ingestion Scripts)            │  GeoJSON → NDJSON flattening
└─────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  BRONZE  (GCS + BigQuery: airbnb_bronze)  │
│  raw_listings, raw_calendar,              │
│  raw_reviews, raw_neighbourhoods          │
└───────────────────────────────────────────┘
        │  dbt staging models
        ▼
┌────────────────────────────────────────────┐
│  SILVER  (BigQuery: airbnb_silver)         │
│  stg_listings, stg_calendar,              │
│  stg_reviews, stg_neighbourhoods          │
└────────────────────────────────────────────┘
        │  dbt mart models
        ▼
┌──────────────────────────────────────────────────┐
│  GOLD  (BigQuery: airbnb_gold)                   │
│  dim_listings, dim_hosts, dim_neighbourhoods     │
│  fct_reviews, fct_availability                   │
└──────────────────────────────────────────────────┘
        │
        ▼
  Analytics / BI / Reporting
```

---

## 📦 Tech Stack

| Tool | Purpose |
|---|---|
| **Python 3.x** | Data ingestion scripting |
| **Google Cloud Storage (GCS)** | Raw data lake (Bronze layer) |
| **Google BigQuery** | Cloud data warehouse |
| **dbt Core + BigQuery adapter** | SQL transformation framework |
| **BigQuery `ST_GEOGFROMGEOJSON`** | GeoJSON → GEOGRAPHY type |

---

## 🗂️ Project Structure

```
Airbnb/
├── .gitignore
├── README.md
├── TECHNICAL_DOCUMENTATION.md     # Full technical reference
├── ingest.py                      # CSV/GZ ingestion → GCS
├── ingest_geojson.py              # GeoJSON → NDJSON → BigQuery
│
├── airbnb_local_sandbox/          # Local EDA (not committed)
│   ├── eda_profiling.ipynb
│   └── raw_data/                  # ⚠️ Excluded from git (~373 MB)
│
└── airbnb_pipeline/               # dbt project
    ├── dbt_project.yml
    ├── profiles.yml.template      # Copy to ~/.dbt/profiles.yml
    ├── models/
    │   ├── _sources.yml
    │   ├── staging/               # Silver layer (views)
    │   │   ├── stg_listings.sql
    │   │   ├── stg_calendar.sql
    │   │   ├── stg_reviews.sql
    │   │   └── stg_neighbourhoods.sql
    │   └── marts/                 # Gold layer (tables)
    │       ├── dim_listings.sql
    │       ├── dim_hosts.sql
    │       ├── dim_neighbourhoods.sql
    │       ├── fct_reviews.sql
    │       └── fct_availability.sql
    ├── macros/
    │   └── generate_schema_name.sql   # BigQuery dataset routing
    └── tests/
```

---

## ⚙️ Setup Guide

### Prerequisites

- Python 3.x
- A [Google Cloud](https://console.cloud.google.com) project with **BigQuery** and **Cloud Storage** enabled
- [`gcloud` CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated
- `dbt-bigquery` installed

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/sukitha2001/Airbnb-London-rentals-data-pipeline.git
cd Airbnb-London-rentals-data-pipeline
```

---

### Step 2 — Install Python Dependencies

```bash
pip install requests google-cloud-storage
```

---

### Step 3 — Authenticate with Google Cloud

```bash
gcloud auth application-default login
```

This uses **OAuth Application Default Credentials** — no service account key file needed.

---

### Step 4 — Configure GCS Bucket

Create a GCS bucket for the raw data lake, or update the bucket name in `ingest.py`:

```python
BUCKET_NAME = "your-gcs-bucket-name"
```

---

### Step 5 — Ingest Raw Data to GCS (Bronze Layer)

```bash
# Ingest CSV files (listings, calendar, reviews)
python ingest.py

# Ingest GeoJSON neighbourhoods
python ingest_geojson.py
```

This streams all four raw files from Inside Airbnb and uploads them to GCS.

---

### Step 6 — Load Raw Tables into BigQuery

Load the GCS files into BigQuery under the `airbnb_bronze` dataset. You can do this via:

- **BigQuery Console** → Create table from GCS
- **`bq load` CLI:**

```bash
bq load \
  --source_format=CSV \
  --autodetect \
  airbnb_bronze.raw_listings \
  gs://your-bucket/listings.csv.gz

# Repeat for calendar, reviews, and neighbourhoods (NEWLINE_DELIMITED_JSON)
```

---

### Step 7 — Configure dbt Profile

Copy the template to your dbt profiles directory and fill in your project details:

```bash
cp airbnb_pipeline/profiles.yml.template ~/.dbt/profiles.yml
```

Then edit `~/.dbt/profiles.yml`:

```yaml
airbnb_pipeline:
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: your-gcp-project-id      # ← your GCP project
      dataset: airbnb_silver
      location: your-bq-region          # e.g. EU, US, asia-southeast1
      threads: 4
      job_execution_timeout_seconds: 300
      job_retries: 1
      priority: interactive
  target: dev
```

---

### Step 8 — Install dbt BigQuery Adapter

```bash
pip install dbt-bigquery
```

Verify the installation:

```bash
dbt --version
```

---

### Step 9 — Run dbt Transformations

```bash
cd airbnb_pipeline

# Check connection to BigQuery
dbt debug

# Build all Silver + Gold layer models
dbt run

# Run all data quality tests
dbt test

# Or do both in one command
dbt build
```

Expected output:
```
PASS=9 WARN=0 ERROR=0 SKIP=0 TOTAL=9
```

---

### Step 10 — Explore the Gold Layer in BigQuery

Your analytics-ready tables are now available in the `airbnb_gold` dataset:

| Table | Rows | Description |
|---|---|---|
| `dim_listings` | ~95k | Listings with review & calendar metrics |
| `dim_hosts` | ~56k | Host-level aggregates |
| `dim_neighbourhoods` | 33 | Areas with geo boundaries & listing stats |
| `fct_reviews` | ~1.9M | Individual reviews with listing context |
| `fct_availability` | ~34.7M | Daily pricing & availability per listing |

**Example queries:**

```sql
-- Top neighbourhoods by review volume
SELECT neighbourhood, SUM(total_reviews) AS total_reviews
FROM `your-project.airbnb_gold.dim_listings`
GROUP BY neighbourhood
ORDER BY total_reviews DESC
LIMIT 10;

-- Weekend vs weekday pricing
SELECT
    neighbourhood,
    ROUND(AVG(CASE WHEN is_weekend THEN price_usd END), 2) AS avg_weekend_price,
    ROUND(AVG(CASE WHEN NOT is_weekend THEN price_usd END), 2) AS avg_weekday_price
FROM `your-project.airbnb_gold.fct_availability`
WHERE is_available
GROUP BY neighbourhood
ORDER BY avg_weekend_price DESC;
```

---

## 📖 Documentation

For full technical details including design decisions, ingestion logic, and model descriptions, see [TECHNICAL_DOCUMENTATION.md](./TECHNICAL_DOCUMENTATION.md).

---

## 📄 Data Source

Data sourced from [Inside Airbnb](https://insideairbnb.com) — London, England (December 2024 snapshot).  
Available under the [Creative Commons CC0 1.0 License](https://creativecommons.org/publicdomain/zero/1.0/).

---

*Built by [Sukitha Rathnayake](https://github.com/sukitha2001)*
