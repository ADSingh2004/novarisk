import requests
import json

url = "http://127.0.0.1:8000/api/v1/facility/analyze?latitude=35.6762&longitude=139.6503&radius_km=5.0&recalculate=true"
print("Fetching...")
try:
    response = requests.get(url, timeout=120)
    print("Status code:", response.status_code)
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
