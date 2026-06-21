import os
import requests
from google.cloud import storage
from google.cloud.storage.retry import DEFAULT_RETRY
import logging

# Set up professional logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIGURATION ---
BUCKET_NAME = "sukitha-airbnb-raw-data-london" 
GCP_PROJECT_ID = "expernetic-airbnb-pipeline"  

# URLs for London
DATA_URLS = {
    "listings.csv.gz": "https://data.insideairbnb.com/united-kingdom/england/london/2024-12-11/data/listings.csv.gz",
    "calendar.csv.gz": "https://data.insideairbnb.com/united-kingdom/england/london/2024-12-11/data/calendar.csv.gz",
    "reviews.csv.gz": "https://data.insideairbnb.com/united-kingdom/england/london/2024-12-11/data/reviews.csv.gz",
    "neighbourhoods.geojson": "https://data.insideairbnb.com/united-kingdom/england/london/2024-12-11/visualisations/neighbourhoods.geojson"
}

def download_and_upload_to_gcs():
    """Downloads files from URLs and streams them directly into Google Cloud Storage."""
    storage_client = storage.Client(project=GCP_PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)

    # Set up a requests session with retry strategy and comprehensive headers
    session = requests.Session()
    retry = requests.adapters.Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504], 
        allowed_methods=["GET"]
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    # Define default headers for requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://insideairbnb.com",
        "Accept-Language": "en-US,en;q=0.9"
    }
    # Configure session headers globally
    session.headers.update(headers)

    for file_name, url in DATA_URLS.items():
        tmp_path = f"/tmp/{file_name}"
        try:
            # --- Phase 1: Download to temp file ---
            # timeout=(10, None): 10s to connect, unlimited read time for large files
            logging.info(f"Starting pipeline for: {file_name}")
            logging.info(f"Downloading from {url}...")
            response = session.get(url, stream=True, timeout=(10, None))
            response.raise_for_status()

            with open(tmp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1 MB chunks
                    if chunk:
                        f.write(chunk)
            logging.info(f"Download complete: {file_name}")

            # --- Phase 2: Upload from temp file to GCS ---
            logging.info(f"Uploading {file_name} to GCS bucket: {BUCKET_NAME}...")
            blob = bucket.blob(file_name)
            # timeout=300: per-chunk socket timeout (5 min)
            # retry deadline=900: overall retry window (15 min) — overrides api_core default of 120s
            blob.upload_from_filename(
                tmp_path,
                timeout=300,
                retry=DEFAULT_RETRY.with_deadline(900),
            )
            logging.info(f"Successfully loaded {file_name} to Bronze layer.\n")

        finally:
            # Always clean up the temp file, even on error
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == "__main__":
    logging.info("Initializing Expernetic Data Ingestion Pipeline...")
    download_and_upload_to_gcs()
    logging.info("Pipeline execution complete.")