"""
Gold Layer Missing Data Audit
Queries every column of every Gold table in BigQuery and reports:
  - Total rows
  - Null count per column
  - Null % per column
  - Summary of completely empty columns
"""
import os
from google.cloud import bigquery
import pandas as pd

pd.set_option("display.max_rows", 200)
pd.set_option("display.width", 120)

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "expernetic-airbnb-pipeline")
DATASET    = "airbnb_gold"

bq = bigquery.Client(project=PROJECT_ID)

# ── Gold table schemas (from dbt SQL files) ──────────────────────────────────
GOLD_TABLES = {
    "dim_listings": [
        "listing_id", "listing_name", "host_id", "host_name",
        "neighbourhood", "latitude", "longitude", "room_type",
        "current_price", "minimum_nights", "total_reviews",
        "first_review_date", "last_review_date",
        "avg_price_next_30_days", "availability_rate_next_30_days",
    ],
    "dim_hosts": [
        "host_id", "host_name", "total_listings",
        "neighbourhoods_hosted_in", "room_types_offered",
        "min_listing_price", "max_listing_price", "avg_listing_price",
        "total_reviews_across_listings",
    ],
    "dim_neighbourhoods": [
        "neighbourhood", "neighbourhood_group", "neighbourhood_boundary",
        "total_listings", "total_hosts",
        "avg_price_usd", "min_price_usd", "max_price_usd",
    ],
    "fct_reviews": [
        "review_id", "listing_id", "review_date",
        "reviewer_id", "reviewer_name", "comments",
        "listing_name", "neighbourhood", "room_type", "host_id", "host_name",
    ],
    "fct_availability": [
        "listing_id", "date", "is_available", "price_usd", "adjusted_price_usd",
        "minimum_nights", "maximum_nights",
        "listing_name", "host_id", "host_name", "neighbourhood", "room_type",
        "year", "month", "month_name", "day_of_week", "is_weekend",
    ],
}

# fct_availability has 34M+ rows — use a 1M sample for speed
SAMPLE_CLAUSES = {
    "fct_reviews":     "TABLESAMPLE SYSTEM (5 PERCENT)",
    "fct_availability": "TABLESAMPLE SYSTEM (3 PERCENT)",
}

SEPARATOR = "=" * 72

def audit_table(table_name, columns):
    full_table = f"`{PROJECT_ID}.{DATASET}.{table_name}`"
    sample     = SAMPLE_CLAUSES.get(table_name, "")

    # COUNT(*) + COUNTIF(col IS NULL) for each column in one pass
    null_exprs = ",\n    ".join(
        f"COUNTIF({col} IS NULL) AS null_{col}" for col in columns
    )
    sql = f"""
        SELECT
            COUNT(*) AS total_rows,
            {null_exprs}
        FROM {full_table} {sample}
    """
    row = bq.query(sql).to_dataframe().iloc[0]
    total = int(row["total_rows"])

    results = []
    for col in columns:
        null_count = int(row[f"null_{col}"])
        null_pct   = (null_count / total * 100) if total > 0 else 0
        results.append({
            "column":      col,
            "total_rows":  total,
            "null_count":  null_count,
            "null_%":      round(null_pct, 2),
            "status":      "✅ OK" if null_count == 0 else ("⚠️  PARTIAL" if null_pct < 50 else "❌  MAJOR"),
        })
    return pd.DataFrame(results), total

print(SEPARATOR)
print(f"  GOLD LAYER MISSING DATA AUDIT")
print(f"  Project : {PROJECT_ID}")
print(f"  Dataset : {DATASET}")
print(SEPARATOR)

all_issues = []

for table, cols in GOLD_TABLES.items():
    print(f"\n{'─'*72}")
    print(f"  TABLE: {table}")
    print(f"{'─'*72}")

    df, total = audit_table(table, cols)
    sample_note = " (SAMPLED)" if table in SAMPLE_CLAUSES else ""
    print(f"  Total rows{sample_note}: {total:,}\n")

    print(df.to_string(index=False))

    issues = df[df["null_count"] > 0]
    if not issues.empty:
        all_issues.append((table, issues))
        print(f"\n  ⚠️  {len(issues)} column(s) with missing values in {table}")
    else:
        print(f"\n  ✅  No missing values found in {table}")

print(f"\n{SEPARATOR}")
print("  OVERALL SUMMARY — COLUMNS WITH MISSING VALUES")
print(SEPARATOR)

if all_issues:
    for table, issues in all_issues:
        print(f"\n  [{table}]")
        for _, row in issues.iterrows():
            print(f"    {row['status']}  {row['column']:<40}  "
                  f"{row['null_count']:>10,} nulls  ({row['null_%']:.2f}%)")
else:
    print("\n  ✅  Gold layer is COMPLETE — no missing values detected across all tables.")

print(f"\n{SEPARATOR}")
