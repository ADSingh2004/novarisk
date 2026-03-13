import sys
import os
import asyncio
import logging

# Configure logging so INFO messages from the pipeline are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

# Also add project root so satellite_processing imports resolve
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.api.endpoints import analyze_facility

async def test_pipeline():
    # Demo Location 1: Amazon Rainforest (Deforestation focus)
    lat1, lon1 = -3.4653, -62.2159

    # Demo Location 2: Aral Sea (Water stress focus)
    lat2, lon2 = 45.1481, 59.5756

    # Demo Location 3: Tokyo (UHI focus)
    lat3, lon3 = 35.6762, 139.6503

    print("\n--- Testing NovaRisk ESG Pipeline ---")
    
    locations = [
        {"name": "Amazon Rainforest", "lat": lat1, "lon": lon1},
        {"name": "Aral Sea",          "lat": lat2, "lon": lon2},
        {"name": "Tokyo",             "lat": lat3, "lon": lon3}
    ]

    for loc in locations:
        print(f"\n{'='*60}")
        print(f"Analyzing {loc['name']} ({loc['lat']}, {loc['lon']})...")
        print('='*60)
        try:
            # Bypass the FastAPI router and call the function directly
            result = await analyze_facility(loc["lat"], loc["lon"], radius_km=2.0)
            
            print(f"\nResult for {loc['name']}:")
            print(f"  Deforestation Risk : {result.deforestation_risk}")
            print(f"  SAR Confidence     : {getattr(result, 'deforestation_confidence', 'Not Evaluated')}")
            print(f"  Water Stress Proxy : {result.water_stress_proxy}")
            print(f"  UHI Index          : {result.heat_island_index}")
        except Exception as e:
            print(f"[ERROR] analyzing {loc['name']}: {e}")
            import traceback
            traceback.print_exc()

    print("\n--- Done ---")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
