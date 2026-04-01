import sys
import os

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_tests():
    lat = 35.6762
    lon = 139.6503
    rad = 5.0
    
    print("Testing /facility/analyze...")
    resp = client.get(f"/api/v1/facility/analyze?latitude={lat}&longitude={lon}&radius_km={rad}&recalculate=true")
    if resp.status_code != 200:
        print(f"Analyze failed: {resp.text}")
        sys.exit(1)
        
    data = resp.json()
    print("Analyze response:")
    print("Forest %: ", data.get("forest_percentage"))
    print("Water %: ", data.get("water_percentage"))
    print("Urban %: ", data.get("urban_percentage"))
    print("Agriculture %: ", data.get("agriculture_percentage"))
    print("Barren %: ", data.get("barren_percentage"))
    print("Analyzed data fully:", data)
    print("-" * 40)
    
    print("Testing /facility/explain...")
    resp_exp = client.get(f"/api/v1/facility/explain?latitude={lat}&longitude={lon}&radius_km={rad}")
    if resp_exp.status_code != 200:
        print(f"Explain failed: {resp_exp.text}")
        sys.exit(1)
        
    data_exp = resp_exp.json()
    print("Explain successfully retrieved! Keys:", data_exp.keys())
    print("Formulas used count:", len(data_exp.get("formulas_used", [])))
    print("Input band values keys:", data_exp.get("input_band_values", {}).keys())
    
    # Check properties
    cmap = data_exp.get("classification_map")
    num_rows_cmap = len(cmap) if cmap else 0
    print("Classification Map shape (rows):", num_rows_cmap)
    
    ndvi_array = data_exp.get("input_band_values", {}).get("ndvi_array")
    num_rows_ndvi = len(ndvi_array) if ndvi_array else 0
    print("NDVI array shape (rows):", num_rows_ndvi)
    
    if num_rows_cmap > 0 and num_rows_ndvi > 0:
        print("ALL TESTS PASSED: Explainability metrics and AI Land Cover Classification exist.")
    else:
        print("TEST FAILED: Missing matrices.")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
