import json
import time
import threading
import unittest
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
import concurrent.futures
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server


class TestStressAndLoadSimulation(unittest.TestCase):
    """Stress test — ověření stability systému pod extrémní zátěží"""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.logs_dir = self.tmp_dir / 'logs'
        self.configs_dir = self.tmp_dir / 'configs'

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.configs_dir.mkdir(parents=True, exist_ok=True)

        self.old_logs_dir = server.LOGS_DIR
        self.old_configs_dir = server.CONFIGS_DIR
        self.old_config_file = server.CONFIG_FILE
        self.old_stats_file = server.STATS_SNAPSHOT_FILE
        self.old_global_stats = server.global_stats

        server.LOGS_DIR = self.logs_dir
        server.CONFIGS_DIR = self.configs_dir
        server.CONFIG_FILE = self.configs_dir / 'default.json'
        server.STATS_SNAPSHOT_FILE = self.logs_dir / 'stats_snapshot.json'
        server.global_stats = {
            "started_at": datetime.utcnow().isoformat() + 'Z',
            "total_ingested_events": 0,
            "total_requests": 0,
            "failed_requests": 0,
            "tag_counters": {},
            "last_known_values": {},
            "request_latencies": [],
        }

        # Inicializujem Flask test client
        self.client = server.app.test_client()

    def tearDown(self):
        server.LOGS_DIR = self.old_logs_dir
        server.CONFIGS_DIR = self.old_configs_dir
        server.CONFIG_FILE = self.old_config_file
        server.STATS_SNAPSHOT_FILE = self.old_stats_file
        server.global_stats = self.old_global_stats
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_ingest_payload(self, gateway_id: str, num_events: int, tag_prefix: str = "Tag") -> dict:
        """Vytvoří ingest payload se zadaným počtem eventů"""
        events = []
        for i in range(num_events):
            events.append({
                "gatewayId": gateway_id,
                "assetId": 100 + (i % 100),
                "source": f"source-{i % 10}",
                "sourceId": f"source-{i % 10}:asset-{i % 100}",
                "tag": f"{tag_prefix}-{i % 50}",
                "value": 10.5 + (i % 100) * 0.1,
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "quality": "Good" if i % 5 != 0 else "Uncertain"
            })
        return {"gatewayId": gateway_id, "events": events}

    def test_01_high_volume_single_request(self):
        """STRESS: Jeden request s maximálním počtem eventů"""
        num_events = 5000
        payload = self._create_ingest_payload("gateway-stress-1", num_events)

        start = time.perf_counter()
        response = self.client.post('/api/ehistorian/gateway/ingest', json=payload)
        duration = time.perf_counter() - start

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body['acceptedCount'], num_events)
        self.assertEqual(server.global_stats['total_ingested_events'], num_events)

        throughput = num_events / duration
        print(f"\n[STRESS] High Volume Single Request:")
        print(f"  Events: {num_events} | Duration: {duration:.3f}s | Throughput: {throughput:.0f} events/s")
        self.assertGreater(throughput, 1000, "Throughput should exceed 1000 events/sec")

    def test_02_parallel_requests_fast_fire(self):
        """STRESS: 50 paralelních requestů s 100 eventy každý"""
        num_requests = 50
        events_per_request = 100

        def send_request(request_id):
            payload = self._create_ingest_payload(f"gateway-parallel-{request_id}", events_per_request)
            response = self.client.post('/api/ehistorian/gateway/ingest', json=payload)
            return (request_id, response.status_code, response.get_json())

        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(send_request, range(num_requests)))
        duration = time.perf_counter() - start

        successful = sum(1 for _, status, _ in results if status == 200)
        self.assertEqual(successful, num_requests, f"All {num_requests} requests should succeed")

        total_events = num_requests * events_per_request
        self.assertEqual(server.global_stats['total_ingested_events'], total_events)

        throughput = total_events / duration
        print(f"\n[STRESS] Parallel Requests (Fast Fire):")
        print(f"  Requests: {num_requests} | Events/Request: {events_per_request}")
        print(f"  Total Events: {total_events} | Duration: {duration:.3f}s | Throughput: {throughput:.0f} events/s")
        self.assertGreater(throughput, 5000, "Throughput should exceed 5000 events/sec")

    def test_03_sustained_load_over_time(self):
        """STRESS: Vydrž zátěž po dobu 10 sekund — 100+ requestů za sebou"""
        duration_target = 10.0
        request_id = 0
        failed_count = 0
        successful_count = 0

        start = time.perf_counter()
        while (time.perf_counter() - start) < duration_target:
            payload = self._create_ingest_payload(f"gateway-sustained-{request_id}", 50)
            response = self.client.post('/api/ehistorian/gateway/ingest', json=payload)
            if response.status_code == 200:
                successful_count += 1
            else:
                failed_count += 1
            request_id += 1

        elapsed = time.perf_counter() - start
        total_events = server.global_stats['total_ingested_events']
        throughput = total_events / elapsed

        print(f"\n[STRESS] Sustained Load Over Time:")
        print(f"  Duration: {elapsed:.3f}s | Requests: {successful_count} successful, {failed_count} failed")
        print(f"  Total Events: {total_events} | Throughput: {throughput:.0f} events/s")

        self.assertEqual(failed_count, 0, "No requests should fail under sustained load")
        self.assertGreater(successful_count, 50, "Should process 50+ requests in 10 seconds")
        self.assertGreater(total_events, 2500, "Should ingest 2500+ events in 10 seconds")

    def test_04_memory_stability_incremental_load(self):
        """STRESS: Incrementální zátěž — vytvářej stále větší zátěž a ověř stabilitu"""
        loads = [100, 500, 1000, 2000, 3000]

        for load_size in loads:
            payload = self._create_ingest_payload(f"gateway-incremental-{load_size}", load_size)
            start = time.perf_counter()
            response = self.client.post('/api/ehistorian/gateway/ingest', json=payload)
            duration = time.perf_counter() - start

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['acceptedCount'], load_size)

            throughput = load_size / duration
            print(f"\n[STRESS] Incremental Load — Size: {load_size} events")
            print(f"  Duration: {duration:.3f}s | Throughput: {throughput:.0f} events/s")

        # Všechny requesty by měly projít bez problémů
        self.assertGreater(server.global_stats['total_ingested_events'], 6500)

    def test_05_burst_traffic_pattern(self):
        """STRESS: Burst traffic — napodobuj špičky provozu s přestávkami"""
        bursts = 5
        requests_per_burst = 20
        events_per_request = 200

        for burst_num in range(bursts):
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for i in range(requests_per_burst):
                    payload = self._create_ingest_payload(f"gateway-burst-{burst_num}-{i}", events_per_request)
                    future = executor.submit(self.client.post, '/api/ehistorian/gateway/ingest', json=payload)
                    futures.append(future)

                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            successful = sum(1 for r in results if r.status_code == 200)
            print(f"\n[STRESS] Burst {burst_num + 1}/{bursts}: {successful}/{requests_per_burst} successful")
            self.assertEqual(successful, requests_per_burst, f"Burst {burst_num} should complete successfully")

            if burst_num < bursts - 1:
                time.sleep(0.5)  # Oddychovací doba mezi bursts

        expected_total = bursts * requests_per_burst * events_per_request
        self.assertEqual(server.global_stats['total_ingested_events'], expected_total)

    def test_06_malformed_and_edge_case_recovery(self):
        """STRESS: Recovery test — systém musí zvládnout chyby a pokračovat"""
        # Normální request
        payload_ok = self._create_ingest_payload("gateway-recovery", 100)
        r1 = self.client.post('/api/ehistorian/gateway/ingest', json=payload_ok)
        self.assertEqual(r1.status_code, 200)

        # Prázdný payload
        r2 = self.client.post('/api/ehistorian/gateway/ingest', json={"gatewayId": "test", "events": []})
        self.assertEqual(r2.status_code, 200)

        # Payload s null hodnotami (měl by být zpracován)
        payload_nulls = {
            "gatewayId": "gateway-nulls",
            "events": [
                {
                    "gatewayId": "gateway-nulls",
                    "assetId": 999,
                    "source": "test",
                    "sourceId": "test:999",
                    "tag": "NullTag",
                    "value": None,
                    "timestamp": datetime.utcnow().isoformat() + 'Z',
                    "quality": "Bad"
                }
            ]
        }
        r3 = self.client.post('/api/ehistorian/gateway/ingest', json=payload_nulls)
        self.assertEqual(r3.status_code, 200)

        # Pokračuj normálně po chybách
        payload_final = self._create_ingest_payload("gateway-after-errors", 200)
        r4 = self.client.post('/api/ehistorian/gateway/ingest', json=payload_final)
        self.assertEqual(r4.status_code, 200)

        print(f"\n[STRESS] Recovery Test:")
        print(f"  Total ingested after recovery sequence: {server.global_stats['total_ingested_events']}")

    def test_07_extreme_tag_diversity(self):
        """STRESS: Miliony unikátních tagů — test tag_counters stabilitu"""
        num_unique_tags = 1000
        events = []

        for i in range(num_unique_tags):
            events.append({
                "gatewayId": "gateway-diversity",
                "assetId": 1000 + i,
                "source": "diversity-test",
                "sourceId": f"diversity:asset-{i}",
                "tag": f"UniqueTag_{i:04d}",
                "value": float(i),
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "quality": "Good"
            })

        payload = {"gatewayId": "gateway-diversity", "events": events}
        response = self.client.post('/api/ehistorian/gateway/ingest', json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(server.global_stats['tag_counters']), num_unique_tags)
        self.assertEqual(server.global_stats['total_ingested_events'], num_unique_tags)

        print(f"\n[STRESS] Tag Diversity:")
        print(f"  Unique tags created: {len(server.global_stats['tag_counters'])}")
        print(f"  Total events: {server.global_stats['total_ingested_events']}")

    def test_08_latency_consistency_under_load(self):
        """STRESS: Ověř, že latence zůstává konzistentní i pod maximální zátěží"""
        payloads = []
        for i in range(100):
            payloads.append(self._create_ingest_payload(f"gateway-latency-{i}", 100))

        latencies = []
        for payload in payloads:
            start = time.perf_counter()
            self.client.post('/api/ehistorian/gateway/ingest', json=payload)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)

        print(f"\n[STRESS] Latency Under Load:")
        print(f"  Min: {min_latency:.2f}ms | Avg: {avg_latency:.2f}ms | Max: {max_latency:.2f}ms")
        print(f"  Total events processed: {server.global_stats['total_ingested_events']}")

        # Latence by neměla být zcela nepředvídatelná
        self.assertLess(max_latency, min_latency * 10, "Max latency should not be 10x min latency")

    def test_09_config_operations_during_load(self):
        """STRESS: Config změny během heavy ingest — musí zůstat stabilní"""
        # Spusť zátěž v jednom vlákně
        def continuous_ingest():
            for i in range(20):
                payload = self._create_ingest_payload(f"gateway-config-stress-{i}", 100)
                self.client.post('/api/ehistorian/gateway/ingest', json=payload)
                time.sleep(0.05)

        # Spusť config změny v jiném vlákně
        def change_config():
            for i in range(5):
                new_config = {
                    "gatewayId": f"updated-gateway-{i}",
                    "apiUrl": "http://localhost:5000",
                    "opcua": [],
                    "sql": [],
                    "offlineBufferMaxBytes": 1024 * (i + 1)
                }
                self.client.post('/api/config', json=new_config)
                time.sleep(0.1)

        t1 = threading.Thread(target=continuous_ingest)
        t2 = threading.Thread(target=change_config)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        print(f"\n[STRESS] Config Changes During Load:")
        print(f"  Events ingested: {server.global_stats['total_ingested_events']}")
        print(f"  Final config gateway ID: {server.load_config()['gatewayId']}")

        self.assertGreater(server.global_stats['total_ingested_events'], 1000)

    def test_10_statistics_accuracy_under_stress(self):
        """STRESS: Ověř, že statistiky zůstávají přesné pod zátěží"""
        num_requests = 50
        events_per_request = 100

        for req_id in range(num_requests):
            payload = self._create_ingest_payload(f"gateway-stats-{req_id}", events_per_request)
            response = self.client.post('/api/ehistorian/gateway/ingest', json=payload)
            self.assertEqual(response.status_code, 200)

        stats_payload = server.build_statistics_payload()

        expected_total = num_requests * events_per_request
        self.assertEqual(stats_payload['totalIngestedEvents'], expected_total)
        self.assertEqual(stats_payload['totalRequests'], num_requests)
        self.assertGreater(stats_payload['avgLatencyMs'], 0)
        self.assertEqual(stats_payload['failedRequests'], 0)

        print(f"\n[STRESS] Statistics Accuracy:")
        print(f"  Total Events: {stats_payload['totalIngestedEvents']}")
        print(f"  Total Requests: {stats_payload['totalRequests']}")
        print(f"  Avg Latency: {stats_payload['avgLatencyMs']}ms")
        print(f"  Throughput: {stats_payload['throughputPerMin']:.1f} events/min")


if __name__ == '__main__':
    unittest.main(verbosity=2)
