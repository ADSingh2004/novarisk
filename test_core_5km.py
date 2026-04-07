import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from satellite_processing.metrics.deforestation_risk import calculate_deforestation_risk
from satellite_processing.metrics.water_stress_proxy import calculate_water_stress_proxy
from satellite_processing.metrics.urban_heat_island import calculate_urban_heat_island

async def run():
    locs = [
        ("Amazon Rainforest", -3.4653, -62.2159),
        ("Aral Sea", 45.1481, 59.5756),
        ("Tokyo", 35.6762, 139.6503)
    ]
    
    print("--- Running 5km Tests for Core Demo Locations ---")
    
    for name, lat, lon in locs:
        print(f"\nAnalyzing {name} ({lat}, {lon}) with 5km radius...")
        try:
            # Deforestation Risk
            defo = calculate_deforestation_risk(lat, lon, 5.0)
            defo_score = defo.get("score", 0.0)
            
            # Water Stress Proxy
            water = calculate_water_stress_proxy(lat, lon, 5.0)
            water_score = water.get("score", 0.0)
            
            # UHI
            uhi = calculate_urban_heat_island(lat, lon, facility_radius_km=1.0, rural_radius_km=10.0)
            uhi_score = uhi.get("score", 0.0)
            
            print(f"  Result for {name}:")
            print(f"    Deforestation : {defo_score:.2f}")
            print(f"    Water Stress  : {water_score:.2f}")
            print(f"    UHI Index     : {uhi_score:.2f}")
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")

if __name__ == "__main__":
    asyncio.run(run())
