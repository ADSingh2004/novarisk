import requests

def test_pdf_export():
    url = "http://127.0.0.1:8004/api/v1/facility/report/pdf"
    params = {
        "latitude": -3.465,
        "longitude": -62.215
    }
    
    print(f"Testing {url}...")
    try:
        response = requests.get(url, params=params)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"Successfully downloaded PDF, size: len(response.content) bytes")
            print(f"Content-Type: {response.headers.get('Content-Type')}")
        else:
            print("Response text:", response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_pdf_export()
