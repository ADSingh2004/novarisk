import subprocess
import json
import os
import sys

locations = [
    "sao_paulo", "new_delhi", "jakarta", "los_angeles", 
    "cerrado", "shenyang", "kumasi", "bangalore"
]

results = []

print(f"Running Multi-Location Validation Suite (One-by-One)...")
print("-" * 50)

for loc in locations:
    print(f"Analyzing {loc}...")
    try:
        # Run the quick test script for this location
        # Setting PYTHONPATH to include the root directory
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.abspath(os.path.join(os.getcwd(), ".."))
        env["PYTHONIOENCODING"] = "utf-8"
        
        cmd = [sys.executable, "quick_test_metrics.py", "--location", loc, "--export", f"tmp_{loc}.json"]
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
        
        # Read the exported JSON
        with open(f"tmp_{loc}.json", "r") as f:
            data = json.load(f)
            results.extend(data)
            
        # Clean up
        os.remove(f"tmp_{loc}.json")
        print(f"  ✓ Done.")
    except Exception as e:
        print(f"  ✗ Failed for {loc}: {e}")

# Save final combined results
with open("test_metrics_results.json", "w") as f:
    json.dump({"results": results, "timestamp": "2026-04-07T02:15:00"}, f, indent=2)

print("-" * 50)
print(f"Full suite complete. Results saved to test_metrics_results.json")
