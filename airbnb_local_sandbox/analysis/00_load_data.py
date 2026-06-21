"""
00_load_data.py
Pulls all 5 Gold-layer tables from BigQuery once and caches them
as Parquet files. All subsequent analysis scripts read from Parquet.
"""
import os
from pathlib import Path
import pandas as pd
from google.cloud import bigquery

PROJECT_ID   = os.getenv("GCP_PROJECT_ID", "expernetic-airbnb-pipeline")
DATASET      = "airbnb_gold"
CACHE_DIR    = Path(__file__).parent / "parquet_cache"
CACHE_DIR.mkdir(exist_ok=True)

bq = bigquery.Client(project=PROJECT_ID)

def q(sql):
    return bq.query(sql).to_dataframe()

tables = {
    "dim_listings": f"""
        SELECT listing_id, listing_name, host_id, host_name,
               neighbourhood, latitude, longitude, room_type,
               current_price, minimum_nights, total_reviews,
               first_review_date, last_review_date,
               avg_price_next_30_days, availability_rate_next_30_days
        FROM `{PROJECT_ID}.{DATASET}.dim_listings`
    """,
    "dim_hosts": f"""
        SELECT host_id, host_name, total_listings,
               min_listing_price, max_listing_price, avg_listing_price,
               total_reviews_across_listings
        FROM `{PROJECT_ID}.{DATASET}.dim_hosts`
    """,
    "dim_neighbourhoods": f"""
        SELECT neighbourhood, neighbourhood_group,
               total_listings, total_hosts,
               avg_price_usd, min_price_usd, max_price_usd
        FROM `{PROJECT_ID}.{DATASET}.dim_neighbourhoods`
    """,
    "fct_reviews": f"""
        SELECT review_id, listing_id, review_date,
               reviewer_id, reviewer_name, comments,
               listing_name, neighbourhood, room_type, host_id, host_name
        FROM `{PROJECT_ID}.{DATASET}.fct_reviews`
    """,
    # fct_availability has 34.7M rows — sample 3% (~1M rows) for analysis
    "fct_availability": f"""
        SELECT listing_id, date, is_available, price_usd,
               minimum_nights, maximum_nights,
               neighbourhood, room_type, year, month, month_name,
               day_of_week, is_weekend
        FROM `{PROJECT_ID}.{DATASET}.fct_availability`
        TABLESAMPLE SYSTEM (3 PERCENT)
    """,
}

for name, sql in tables.items():
    path = CACHE_DIR / f"{name}.parquet"
    if path.exists():
        print(f"  SKIP  {name} (already cached)")
        continue
    print(f"  LOADING {name} from BigQuery...")
    df = q(sql)
    df.to_parquet(path, index=False)
    print(f"  SAVED  {name} → {path}  ({len(df):,} rows)")

print("\n✅  All tables cached to", CACHE_DIR)
