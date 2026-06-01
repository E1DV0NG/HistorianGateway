import asyncio
import json
import urllib.request

async def report_config_status(api_url: str, gateway_id: str, status: str, error: str = None) -> None:
    endpoint = f"{str(api_url).rstrip('/')}/api/ehistorian/gateway/config-status"
    payload_dict = {"gatewayId": gateway_id, "status": status}
    if error:
        payload_dict["error"] = error
    payload = json.dumps(payload_dict).encode('utf-8')
    
    def send():
        req = urllib.request.Request(endpoint, data=payload, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            pass
    await asyncio.to_thread(send)

async def test_buffer_status_reporter(sqlite_queue, api_url: str, gateway_id: str, max_bytes: int, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            if sqlite_queue is not None:
                bytes_size = await sqlite_queue.total_bytes_size()
                pending_count = await sqlite_queue.pending_count()
                url = f"{str(api_url).rstrip('/')}/api/ehistorian/gateway/buffer-status"
                
                payload = {
                    "gatewayId": gateway_id,
                    "bytesSize": bytes_size,
                    "pendingCount": pending_count,
                    "maxBytes": max_bytes
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                def send():
                    try:
                        with urllib.request.urlopen(req, timeout=2) as r:
                            r.read()
                    except Exception:
                        pass
                await asyncio.to_thread(send)
        except Exception:
            pass
        await asyncio.sleep(1.0)
