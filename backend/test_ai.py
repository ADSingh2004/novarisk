import sys
import os

# Ensure the project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from satellite_processing.client import search_sentinel2
from app.utils.spatial import generate_bbox
from satellite_processing.ai.land_cover_classifier import calculate_land_cover_from_stac_items

def test_ai():
    lat = 35.6762
    lon = 139.6503
    rad = 5.0
    
    print("Fetching items...")
    items = search_sentinel2(lat, lon, rad, days_back=30)
    bbox = generate_bbox(lat, lon, rad)
    
    print(f"Found {len(items)} items. Running AI classification...")
    res = calculate_land_cover_from_stac_items(items, bbox)
    
    if res.get("status") == "failed":
        print(f"FAILED: {res.get('error')}")
    else:
        print("SUCCESS! Percentages:")
        print(res.get("percentages"))

if __name__ == "__main__":
    test_ai()
