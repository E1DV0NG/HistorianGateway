import urllib.request
import json
import time

def test_api():
    print("Enabling simulate outage...")
    req = urllib.request.Request(
        'http://127.0.0.1:5000/api/simulate-outage', 
        data=json.dumps({"simulate": True}).encode(), 
        headers={'Content-Type': 'application/json'}, 
        method='POST'
    )
    res = urllib.request.urlopen(req)
    print("Response:", res.read().decode())
    
    print("Testing ingest endpoint...")
    ingest_req = urllib.request.Request(
        'http://127.0.0.1:5000/api/ehistorian/gateway/ingest',
        data=json.dumps({"gatewayId": "test", "events": []}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        urllib.request.urlopen(ingest_req)
        print("Ingest SUCCEEDED (This means simulate outage FAILED)")
    except urllib.error.HTTPError as e:
        print(f"Ingest FAILED with {e.code} (This means simulate outage WORKED!)")

if __name__ == "__main__":
    test_api()
