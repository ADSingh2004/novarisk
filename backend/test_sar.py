import requests
import time

def test_api():
    url = "http://127.0.0.1:8000/api/v1/facility/analyze"
    params = {
        "latitude": -3.465,
        "longitude": -62.215,
        "radius_km": 5.0
    }
    
    print(f"Testing {url} with params {params}")
    
    start_time = time.time()
    try:
        response = requests.get(url, params=params)
        end_time = time.time()
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {end_time - start_time:.2f} seconds")
        print("Response JSON:")
        import json
        print(json.dumps(response.json(), indent=2))
        
    except Exception as e:
        print(f"Error testing API: {e}")

if __name__ == "__main__":
    test_api()
