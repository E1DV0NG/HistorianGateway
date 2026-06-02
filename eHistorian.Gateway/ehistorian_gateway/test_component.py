import asyncio
import json
import urllib.request

async def report_config_status(endpoint_url: str, gateway_id: str, status: str, error: str = None) -> None:
    payload_dict = {"gatewayId": gateway_id, "status": status}
    if error:
        payload_dict["error"] = error
    payload = json.dumps(payload_dict).encode('utf-8')
    
    def send():
        req = urllib.request.Request(endpoint_url, data=payload, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            pass
    await asyncio.to_thread(send)

