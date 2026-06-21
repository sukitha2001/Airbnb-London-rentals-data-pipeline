"""
bq_helper.py  — shared BigQuery connection used by all analysis scripts.
Every script imports:  from bq_helper import bq, q, PROJECT_ID, DATASET
"""
import os
from google.cloud import bigquery

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "expernetic-airbnb-pipeline")
DATASET    = "airbnb_gold"

bq = bigquery.Client(project=PROJECT_ID)

def q(sql: str):
    """Run SQL in BigQuery, return a pandas DataFrame."""
    return bq.query(sql).to_dataframe()
