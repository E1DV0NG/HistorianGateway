import sys
import os
import asyncio
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Add eHistorian.Gateway to python search path
sys.path.insert(0, str(Path(__file__).parent / "eHistorian.Gateway"))

from ehistorian_gateway.models.event import PersistedBatch, UnifiedEvent
from ehistorian_gateway.storage.sqlite_queue import SQLiteQueue
from ehistorian_gateway.sender.retry import RetryPolicy
from ehistorian_gateway.main import GatewayApplication

# Colors for nice console output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

def log_info(msg: str):
    print(f"{BLUE}[INFO]{RESET} {msg}")

def log_success(msg: str):
    print(f"{GREEN}[OK]{RESET} {msg}")

def log_warn(msg: str):
    print(f"{YELLOW}[WARN]{RESET} {msg}")

def log_error(msg: str):
    print(f"{RED}[ERROR]{RESET} {msg}")

# --- Background Mock Server ---
mock_server_received = []
mock_server_should_fail = False

class MockServerRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging of incoming requests to keep console clean
        pass

    def do_POST(self):
        global mock_server_should_fail
        print(f"[MOCK SERVER] POST {self.path}")
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8'))
        
        mock_server_received.append({
            "path": self.path,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        if mock_server_should_fail:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "Internal Server Error"}).encode('utf-8'))
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "gatewayId": payload.get("gatewayId", "unknown"),
                "acceptedCount": len(payload.get("events", [])),
                "rejectedCount": 0,
                "status": "Accepted"
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))

    def do_GET(self):
        print(f"[MOCK SERVER] GET {self.path}")
        # Health check or config requests
        if self.path.startswith("/api/ehistorian/gateway/config/"):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            config = {
                "gatewayId": "test-resilience-gw",
                "apiUrl": "http://localhost:5099",
                "sqlitePath": "test_integration.db",
                "requestTimeoutSeconds": 2,
                "retryBaseSeconds": 1.0,
                "retryMaxSeconds": 4.0,
                "queueMaxsize": 100,
                "healthHost": "127.0.0.1",
                "healthPort": 8089,
                "opcua": [],
                "sql": []
            }
            self.wfile.write(json.dumps(config).encode('utf-8'))
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))


def start_mock_server():
    server = HTTPServer(('127.0.0.1', 5099), MockServerRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

# --- UNIT TESTS ---
async def test_queue_and_retry_unit():
    log_info("Spouštím unit test pro SQLiteQueue a RetryPolicy...")
    
    db_path = "test_queue.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    queue = SQLiteQueue(db_path)
    await queue.initialize()
    
    # 1. Enqueue batch
    ev = UnifiedEvent(
        gateway_id="test-gw",
        asset_id=101,
        source="unit_test",
        source_id="test-0",
        tag="Temperature",
        value=23.4,
        timestamp=datetime.now(timezone.utc)
    )
    batch = PersistedBatch.from_events("test-gw", [ev])
    await queue.enqueue_batch(batch)
    
    count = await queue.pending_count()
    assert count == 1, f"Očekáván 1 záznam v databázi, nalezeno: {count}"
    log_success("Zápis dávky do SQLite fronty funguje správně.")

    # 2. Lease batch
    leased = await queue.lease_next_batch()
    assert leased is not None, "Dávka nebyla úspěšně zapůjčena (leased)."
    assert leased.batch_id == batch.batch_id, "ID zapůjčené dávky se neshoduje."
    
    # Když je dávka zapůjčená (status 'sending'), lease_next_batch by měl vrátit None
    second_lease = await queue.lease_next_batch()
    assert second_lease is None, "Zapůjčená dávka byla znovu zapůjčena před vypršením zámku."
    log_success("Zamykání dávek (leasing) při odesílání funguje správně.")

    # 3. Simulate failure & Retry delay
    policy = RetryPolicy(base_delay_seconds=1.0, max_delay_seconds=5.0)
    delay = policy.compute_delay(leased.attempts + 1)
    log_info(f"Simuluji selhání odeslání s vypočteným zpožděním: {delay:.2f} s")
    
    await queue.mark_retry(leased.batch_id, "Simulovaná chyba sítě", delay)
    
    # Ihned po mark_retry by nemělo být možné dávku zapůjčit (musí se čekat)
    immediate_lease = await queue.lease_next_batch()
    assert immediate_lease is None, "Dávka byla zapůjčena okamžitě bez respektování retry zpoždění."
    log_success("Retry politika blokuje okamžité opětovné zapůjčení.")

    # Počkáme, až zpoždění vyprší
    log_info(f"Čekám {delay + 0.5:.2f} s na vypršení retry zpoždění...")
    await asyncio.sleep(delay + 0.5)

    re_leased = await queue.lease_next_batch()
    assert re_leased is not None, "Dávka nebyla po vypršení zpoždění opět dostupná."
    assert re_leased.attempts == 1, f"Očekáván počet pokusů: 1, nalezeno: {re_leased.attempts}"
    log_success("Dávka se po vypršení zpoždění správně uvolnila k novému pokusu.")

    # 4. Mark sent (Success)
    await queue.mark_sent(re_leased.batch_id)
    final_count = await queue.pending_count()
    assert final_count == 0, f"Očekáváno 0 záznamů po úspěšném odeslání, nalezeno: {final_count}"
    log_success("Smazání dávky po úspěšném odeslání (mark_sent) funguje.")

    if os.path.exists(db_path):
        os.remove(db_path)
    log_success("Unit test proběhl úspěšně.\n")


async def test_queue_prunes_oldest_batches_when_buffer_limit_exceeded():
    log_info("Spouštím unit test pro offline buffer limit podle velikosti...")

    db_path = "test_queue_limit.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    queue = SQLiteQueue(db_path, max_bytes=180)
    await queue.initialize()

    batch_ids = []
    for index in range(3):
        ev = UnifiedEvent(
            gateway_id="test-gw",
            asset_id=101 + index,
            source="unit_test",
            source_id=f"test-{index}",
            tag="Temperature",
            value=23.4 + index,
            timestamp=datetime.now(timezone.utc)
        )
        batch = PersistedBatch.from_events("test-gw", [ev])
        batch_ids.append(batch.batch_id)
        await queue.enqueue_batch(batch)

    count = await queue.pending_count()
    assert count == 1, f"Očekáván 1 záznam po oříznutí starých dávků, nalezeno: {count}"
    log_success("Offline buffer ořezává nejstarší dávky po překročení velikostního limitu.")

    if os.path.exists(db_path):
        os.remove(db_path)


# --- INTEGRATION TESTS ---
async def test_gateway_resilience_integration():
    global mock_server_received, mock_server_should_fail
    log_info("Spouštím integrační test s běžícím Gateway a mock serverem...")

    # 1. Setup temporary config & clean databases
    config_path = "test_config_temp.json"
    integration_db = "test_integration.db"
    
    for f in [config_path, integration_db]:
        if os.path.exists(f):
            os.remove(f)

    config_data = {
        "gatewayId": "test-resilience-gw",
        "apiUrl": "http://localhost:5099",
        "sqlitePath": integration_db,
        "requestTimeoutSeconds": 2,
        "retryBaseSeconds": 1.0,  # Short base delay for testing
        "retryMaxSeconds": 3.0,
        "queueMaxsize": 100,
        "healthHost": "127.0.0.1",
        "healthPort": 8089,
        "opcua": [],
        "sql": []
    }
    
    with open(config_path, "w") as f:
        json.dump(config_data, f)

    # Start Mock Server
    server = start_mock_server()
    log_info("Mock server nastartován na http://localhost:5099")

    # Start Gateway Application
    app = GatewayApplication(config_path)
    gateway_task = asyncio.create_task(app.run())
    
    # Wait for gateway initialization
    await asyncio.sleep(1.0)
    if gateway_task.done():
        exc = gateway_task.exception()
        if exc:
            log_error(f"Gateway task has ended with an exception: {exc}")
            import traceback
            traceback.print_exception(type(exc), exc, exc.__traceback__)
        else:
            log_error("Gateway task has ended successfully but prematurely!")
    else:
        log_success("Gateway aplikace běží v pozadí.")

    # Create a separate client queue object to enqueue mock data into the gateway's database
    client_queue = SQLiteQueue(integration_db)
    await client_queue.initialize()
    
    # --- PHASE 1: Normal Delivery (Server Online) ---
    log_info("FÁZE 1: Testování odesílání za běžného stavu (server je online)...")
    mock_server_received.clear()
    mock_server_should_fail = False

    ev1 = UnifiedEvent(
        gateway_id="test-resilience-gw",
        asset_id=1,
        source="opcua",
        source_id="opcua-0",
        tag="Power",
        value=150.2,
        timestamp=datetime.now(timezone.utc)
    )
    batch1 = PersistedBatch.from_events("test-resilience-gw", [ev1])
    
    await client_queue.enqueue_batch(batch1)
    log_info("Vložena 1. dávka do lokální databáze.")

    # Wait for gateway sender to pick up and deliver the batch using a dynamic polling loop
    for _ in range(50):
        if len(mock_server_received) == 1:
            break
        await asyncio.sleep(0.1)
    
    assert len(mock_server_received) == 1, "Mock server neobdržel dávku, ačkoliv byl online."
    assert await client_queue.pending_count() == 0, "Dávka nebyla po odeslání vymazána z SQLite."
    log_success("Fáze 1 splněna. Data byla okamžitě odeslána a smazána z lokální fronty.")

    # --- PHASE 2: Server Outage (Offline Buffer) ---
    log_info("FÁZE 2: Testování výpadku sítě (server začne vracet chybu 500)...")
    mock_server_should_fail = True
    mock_server_received.clear()

    ev2 = UnifiedEvent(
        gateway_id="test-resilience-gw",
        asset_id=2,
        source="sql",
        source_id="sql-0",
        tag="Pressure",
        value=5.4,
        timestamp=datetime.now(timezone.utc)
    )
    batch2 = PersistedBatch.from_events("test-resilience-gw", [ev2])
    
    await client_queue.enqueue_batch(batch2)
    log_info("Vložena 2. dávka do lokální databáze (při nefunkčním serveru).")

    # Wait for the gateway sender to attempt delivery (which will fail and return 500)
    for _ in range(50):
        if len(mock_server_received) >= 1:
            break
        await asyncio.sleep(0.1)
    
    pending_count = await client_queue.pending_count()
    assert pending_count == 1, f"Očekávána 1 pending dávka v SQLite, nalezeno: {pending_count}"
    assert len(mock_server_received) >= 1, "Nebyl zaznamenán žádný pokus o odeslání."
    log_success("Fáze 2 splněna. Při výpadku sítě zůstala data bezpečně uložena v SQLite a byl spuštěn retry mechanismus.")

    # --- PHASE 3: Connection Restored (Automatic Recovery) ---
    log_info("FÁZE 3: Testování obnovení spojení (server je opět online)...")
    mock_server_should_fail = False
    mock_server_received.clear()

    log_info("Čekám na dokončení automatického retry pokusu...")
    # Wait for mock server to receive the retry batch
    for _ in range(60):
        if len(mock_server_received) >= 1:
            break
        await asyncio.sleep(0.1)

    assert len(mock_server_received) >= 1, "Po obnovení serveru se brána nepokusila data znovu odeslat."
    
    # Wait a bit for DB cleanup to finish
    for _ in range(20):
        if await client_queue.pending_count() == 0:
            break
        await asyncio.sleep(0.1)

    final_pending = await client_queue.pending_count()
    assert final_pending == 0, f"Lokální fronta nebyla po obnovení vyčištěna. Zbývá: {final_pending} dávek"
    log_success("Fáze 3 splněna. Po obnovení sítě brána automaticky odeslala backlog a vyčistila lokální SQLite.")

    # --- CLEANUP ---
    log_info("Ukončuji Gateway aplikaci a čistím soubory...")
    app._stop_event.set()
    
    try:
        await asyncio.wait_for(gateway_task, timeout=3.0)
    except asyncio.TimeoutError:
        gateway_task.cancel()

    server.shutdown()
    server.server_close()

    for f in [config_path, integration_db]:
        if os.path.exists(f):
            os.remove(f)
            
    # Clean up test_queue if unit test leftovers exist
    if os.path.exists("test_queue.db"):
        os.remove("test_queue.db")

    log_success("Integrační test proběhl úspěšně.\n")


async def main():
    print("==================================================")
    print("  eHistorian Gateway — Testy odolnosti vůči chybám")
    print("==================================================")
    print()
    
    try:
        await test_queue_and_retry_unit()
        await test_gateway_resilience_integration()
        
        print(f"{GREEN}Všechny testy proběhly úspěšně a bez chyb.{RESET}")
        sys.exit(0)
    except AssertionError as e:
        log_error(f"Test selhal na podmínce: {e}")
        sys.exit(1)
    except Exception as e:
        log_error(f"Během testů došlo k neočekávané chybě: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
