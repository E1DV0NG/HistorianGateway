"""
Test script - posilani jednoho request
"""

import requests
import json

url = "http://localhost:5000/api/ehistorian/gateway/ingest"

data = {
    "gatewayId": "test-gateway",
    "events": [
        {
            "gatewayId": "test-gateway",
            "assetId": 101,
            "source": "opcua",
            "sourceId": "opcua-0:asset-101",
            "tag": "Temperature",
            "value": 24.5,
            "timestamp": "2026-05-26T09:00:00Z",
            "quality": "Good"
        }
    ]
}

print("Posílám request...")
print(json.dumps(data, indent=2))
print()

response = requests.post(url, json=data)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
