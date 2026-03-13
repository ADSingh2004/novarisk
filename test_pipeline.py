import sys
import os
import asyncio
import json

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))
from app.api.endpoints import analyze_facility

async def test_pipeline():
    # Demo Location 1: Amazon Rainforest (Deforestation focus)
    lat1, lon1 = -3.4653, -62.2159

    # Demo Location 2: Aral Sea (Water stress focus)
    lat2, lon2 = 45.1481, 59.5756

    # Demo Location 3: Tokyo (UHI focus)
    lat3, lon3 = 35.6762, 139.6503

    print("--- Testing NovaRisk ESG Pipeline ---")
    
    locations = [
        {"name": "Amazon Rainforest", "lat": lat1, "lon": lon1},
        {"name": "Aral Sea", "lat": lat2, "lon": lon2},
        {"name": "Tokyo", "lat": lat3, "lon": lon3}
    ]

    for loc in locations:
        print(f"\nAnalyzing {loc['name']} ({loc['lat']}, {loc['lon']})...")
        try:
            # We bypass the fastapi router and call the func directly
            result = await analyze_facility(loc["lat"], loc["lon"], radius_km=2.0)
            
            print(f"Result for {loc['name']}:")
            print(f"  Deforestation Risk : {result.deforestation_risk}")
            print(f"  Water Stress Proxy : {result.water_stress_proxy}")
            print(f"  UHI Index          : {result.heat_island_index}")
        except Exception as e:
            print(f"Error analyzing {loc['name']}: {e}")

if __name__ == "__main__":
    # Ensure redis is running or this will throw connection errors
    asyncio.run(test_pipeline())
