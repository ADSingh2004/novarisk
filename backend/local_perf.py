import sys
import os
import asyncio
import time
from statistics import median

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from app.api.endpoints import analyze_facility

LOCATIONS = [
    {"lat": -3.4653, "lon": -62.2159}
]

async def run_perf():
    print("--- NovaRisk Performance Benchmarks ---")
    print("Seeding Cache (Uncached Cold Reads)...")
    cold_latencies = []
    
    for loc in LOCATIONS:
        start = time.perf_counter()
        # Ensure we call to endpoints directly
        result = await analyze_facility(loc["lat"], loc["lon"], 5.0)
        end = time.perf_counter()
        ms = (end - start) * 1000
        cold_latencies.append(ms)
        print(f"  [Cold] {loc['lat']}, {loc['lon']} -> {ms:.2f} ms")

    print(f"\n-> Average Cold Read Latency: {sum(cold_latencies)/len(cold_latencies):.2f} ms")

    print("\nStarting Cached Load Test (100 Iterations)...")
    latencies = []
    
    for i in range(100):
        loc = LOCATIONS[i % len(LOCATIONS)]
        start = time.perf_counter()
        await analyze_facility(loc["lat"], loc["lon"], 5.0)
        end = time.perf_counter()
        latencies.append((end - start) * 1000)
        
    p50 = median(latencies)
    p90 = sorted(latencies)[int(len(latencies) * 0.9)]
    avg = sum(latencies) / len(latencies)
    
    print(f"\n--- Cached Load Test Results ---")
    print(f"Total Requests  : 100")
    print(f"Average Latency : {avg:.2f} ms")
    print(f"p50 Latency     : {p50:.2f} ms")
    print(f"p90 Latency     : {p90:.2f} ms")

if __name__ == "__main__":
    asyncio.run(run_perf())
