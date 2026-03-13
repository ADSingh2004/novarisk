import asyncio
import time
import httpx
from statistics import median

# Assuming the backend is running locally on port 8000
API_BASE_URL = "http://127.0.0.1:8000/api/v1"

# Demo Coordinates
LOCATIONS = [
    {"lat": -3.4653, "lon": -62.2159}, # Amazon
    {"lat": 45.1481, "lon": 59.5756},  # Aral Sea 
    {"lat": 35.6762, "lon": 139.6503}  # Tokyo
]

async def seed_cache():
    """Hits the endpoints once to ensure they are cached in Redis."""
    print("Seeding Cache...")
    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    async with httpx.AsyncClient(timeout=120.0, limits=limits) as client:
        for loc in LOCATIONS:
            try:
                # This first request might take a while if it hits Planetary Computer
                resp = await client.get(f"{API_BASE_URL}/facility/analyze?latitude={loc['lat']}&longitude={loc['lon']}&radius_km=5.0")
                if resp.status_code == 200:
                    print(f"Successfully seeded: {loc}")
                else:
                    print(f"Warning: Seed request returned {resp.status_code}")
            except Exception as e:
                print(f"Warning: Seed request for {loc} failed: {e}")
    print("Cache seeding complete.")

async def perform_load_test(num_requests: int = 50):
    """
    Sends multiple concurrent requests to the analyze API to measure cached p50 latency.
    """
    print(f"\nStarting Load Test: {num_requests} concurrent requests (Simulating cached reads)")
    latencies = []
    
    async with httpx.AsyncClient() as client:
        async def fetch(loc):
            start_time = time.perf_counter()
            try:
                resp = await client.get(f"{API_BASE_URL}/facility/analyze?latitude={loc['lat']}&longitude={loc['lon']}&radius_km=5.0")
                resp.raise_for_status()
            except Exception as e:
                pass
            end_time = time.perf_counter()
            return (end_time - start_time) * 1000 # Convert to ms
            
        # Create a mix of requests across the 3 cached demo locations
        tasks = []
        for i in range(num_requests):
            loc = LOCATIONS[i % len(LOCATIONS)]
            tasks.append(fetch(loc))
            
        results = await asyncio.gather(*tasks)
        latencies.extend(results)
        
    p50 = median(latencies)
    p90 = sorted(latencies)[int(len(latencies) * 0.9)]
    avg = sum(latencies) / len(latencies)
    
    print("\n--- Load Test Results ---")
    print(f"Total Requests  : {num_requests}")
    print(f"Average Latency : {avg:.2f} ms")
    print(f"p50 Latency     : {p50:.2f} ms")
    print(f"p90 Latency     : {p90:.2f} ms")
    
    return p50

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--seed':
        asyncio.run(seed_cache())
    asyncio.run(perform_load_test(100))
