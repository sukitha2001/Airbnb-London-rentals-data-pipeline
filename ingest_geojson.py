import os
import json
import requests

# Configuration
GCP_PROJECT_ID = "expernetic-airbnb-pipeline"
DATASET_ID = "airbnb_bronze"
TABLE_ID = "raw_neighbourhoods"
GEOJSON_URL = "https://data.insideairbnb.com/united-kingdom/england/london/2024-12-11/visualisations/neighbourhoods.geojson"
NDJSON_TEMP_PATH = "/tmp/neighbourhoods.ndjson"

def process_and_load_geojson():
    print(f"Downloading GeoJSON from {GEOJSON_URL}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(GEOJSON_URL, headers=headers)
    response.raise_for_status()
    
    # Parse the GeoJSON FeatureCollection
    geojson_data = response.json()
    features = geojson_data.get("features", [])
    
    print(f"Flattening {len(features)} features into Newline Delimited JSON...")
    with open(NDJSON_TEMP_PATH, "w") as f:
        for feature in features:
            row = {
                "neighbourhood": feature["properties"].get("neighbourhood", ""),
                "neighbourhood_group": feature["properties"].get("neighbourhood_group", ""),
                "geometry_json": json.dumps(feature["geometry"])
            }
            f.write(json.dumps(row) + "\n")
            
    print("Done generating NDJSON!")

if __name__ == "__main__":
    process_and_load_geojson()
