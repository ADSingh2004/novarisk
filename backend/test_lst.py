import sys
import os
sys.path.append(os.path.abspath(".."))

from satellite_processing.client import search_landsat
from satellite_processing.indices.land_surface_temperature import calculate_lst_from_stac_items
from app.utils.spatial import generate_bbox

lat, lon = 35.6762, 139.6503 # Tokyo

print("Searching Landsat items...")
items = search_landsat(lat, lon, radius_km=1.0, days_back=60)
print(f"Found {len(items)} items.")

if items:
    print(f"Item 0 assets: {list(items[0].assets.keys())}")
    for item in items:
        print(f"Item {item.id} bbox: {item.bbox}")
        
    bbox = generate_bbox(lat, lon, 1.0)
    print("BBox:", bbox)
    res = calculate_lst_from_stac_items(items, bbox)
    print("Result:", res)
