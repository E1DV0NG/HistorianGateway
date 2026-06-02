import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import server


class TestServerFunctions(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.logs_dir = self.tmp_dir / 'logs'
        self.configs_dir = self.tmp_dir / 'configs'
        self.fakegen_file = self.tmp_dir / 'fakegen_config.json'
        self.stats_file = self.logs_dir / 'stats_snapshot.json'
        self.config_file = self.configs_dir / 'default.json'

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.configs_dir.mkdir(parents=True, exist_ok=True)

        self.old_logs_dir = server.LOGS_DIR
        self.old_configs_dir = server.CONFIGS_DIR
        self.old_config_file = server.CONFIG_FILE
        self.old_fakegen_file = server.FAKEGEN_CONFIG_FILE
        self.old_stats_file = server.STATS_SNAPSHOT_FILE
        self.old_global_stats = server.global_stats

        server.LOGS_DIR = self.logs_dir
        server.CONFIGS_DIR = self.configs_dir
        server.CONFIG_FILE = self.config_file
        server.FAKEGEN_CONFIG_FILE = self.fakegen_file
        server.STATS_SNAPSHOT_FILE = self.stats_file
        server.global_stats = {
            "started_at": datetime.utcnow().isoformat() + 'Z',
            "total_ingested_events": 0,
            "total_requests": 0,
            "failed_requests": 0,
            "tag_counters": {},
            "last_known_values": {},
            "request_latencies": [],
        }

    def tearDown(self):
        server.LOGS_DIR = self.old_logs_dir
        server.CONFIGS_DIR = self.old_configs_dir
        server.CONFIG_FILE = self.old_config_file
        server.FAKEGEN_CONFIG_FILE = self.old_fakegen_file
        server.STATS_SNAPSHOT_FILE = self.old_stats_file
        server.global_stats = self.old_global_stats
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_load_and_save_config(self):
        self.assertFalse(self.config_file.exists())

        config = {
            "gatewayId": "test-gateway",
            "apiUrl": "http://localhost:5000",
            "opcua": [],
            "sql": [],
            "offlineBufferMaxBytes": 1024,
        }
        server.save_config(config)
        self.assertTrue(self.config_file.exists())

        loaded = server.load_config()
        self.assertEqual(loaded["gatewayId"], "test-gateway")
        self.assertEqual(loaded["offlineBufferMaxBytes"], 1024)

    def test_build_statistics_payload_has_expected_fields(self):
        sample_file = self.logs_dir / 'sample.json'
        sample_file.write_text('[]', encoding='utf-8')

        server.global_stats.update({
            "started_at": (datetime.utcnow() - timedelta(minutes=10)).isoformat() + 'Z',
            "total_ingested_events": 120,
            "total_requests": 4,
            "failed_requests": 1,
            "tag_counters": {"Temperature": 3},
            "last_known_values": {"Temperature": {"value": 22.4, "timestamp": datetime.utcnow().isoformat() + 'Z', "quality": "Good"}},
            "request_latencies": [10.0, 20.0, 30.0],
        })

        payload = server.build_statistics_payload()
        self.assertEqual(payload["totalRequests"], 4)
        self.assertEqual(payload["failedRequests"], 1)
        self.assertEqual(payload["logFilesCount"], 1)
        self.assertEqual(payload["activeTagsCount"], 1)
        self.assertEqual(payload["tagDistribution"], {"Temperature": 3})
        self.assertTrue(payload["throughputPerMin"] > 0)
        self.assertEqual(payload["avgLatencyMs"], 20.0)
        self.assertTrue(self.stats_file.exists())

    def test_api_config_get_and_post(self):
        with server.app.test_client() as client:
            get_resp = client.get('/api/config')
            self.assertEqual(get_resp.status_code, 200)
            self.assertIn('gatewayId', get_resp.get_json())

            new_config = {
                "gatewayId": "saved-gateway",
                "apiUrl": "http://localhost:5000",
                "opcua": [],
                "sql": [],
                "offlineBufferMaxBytes": 2048,
            }
            post_resp = client.post('/api/config', json=new_config)
            self.assertEqual(post_resp.status_code, 200)
            self.assertTrue(self.config_file.exists())
            self.assertEqual(json.loads(self.config_file.read_text(encoding='utf-8'))["gatewayId"], "saved-gateway")

    def test_fakegen_config_get_and_post(self):
        with server.app.test_client() as client:
            if self.fakegen_file.exists():
                self.fakegen_file.unlink()

            get_resp = client.get('/api/fakegen/config')
            self.assertEqual(get_resp.status_code, 200)
            data = get_resp.get_json()
            self.assertIn('connectionString', data)
            self.assertIn('sensors', data)

            new_config = {
                "connectionString": "Driver={ODBC Driver 18 for SQL Server};Server=localhost;Database=eFactory;UID=sa;PWD=YourStrong!Passw0rd;TrustServerCertificate=yes;",
                "table": "CurrentValues",
                "tagColumn": "TagName",
                "valueColumn": "Value",
                "timestampColumn": "UpdatedAt",
                "intervalSeconds": 5,
                "sensors": {"Temperature": {"base": 30.0, "noise": 1.0}},
            }
            post_resp = client.post('/api/fakegen/config', json=new_config)
            self.assertEqual(post_resp.status_code, 200)
            self.assertTrue(self.fakegen_file.exists())
            saved = json.loads(self.fakegen_file.read_text(encoding='utf-8'))
            self.assertEqual(saved['table'], 'CurrentValues')
            self.assertEqual(saved['intervalSeconds'], 5)

    def test_ingest_endpoint_creates_log_and_updates_stats(self):
        with server.app.test_client() as client:
            request_data = {
                "gatewayId": "test-gateway",
                "events": [
                    {
                        "gatewayId": "test-gateway",
                        "assetId": 101,
                        "source": "unit-test",
                        "sourceId": "test-0:asset-101",
                        "tag": "Temperature",
                        "value": 23.5,
                        "timestamp": datetime.utcnow().isoformat() + 'Z',
                        "quality": "Good",
                    }
                ]
            }
            response = client.post('/api/ehistorian/gateway/ingest', json=request_data)
            self.assertEqual(response.status_code, 200)
            body = response.get_json()
            self.assertEqual(body['acceptedCount'], 1)
            self.assertEqual(body['status'], 'Accepted')
            self.assertEqual(server.global_stats['total_ingested_events'], 1)
            self.assertIn('Temperature', server.global_stats['tag_counters'])

            logs = list(self.logs_dir.glob('ingest_*.json'))
            self.assertEqual(len(logs), 1)
            data = json.loads(logs[0].read_text(encoding='utf-8'))
            self.assertEqual(data['gatewayId'], 'test-gateway')
            self.assertEqual(len(data['events']), 1)


if __name__ == '__main__':
    unittest.main()
