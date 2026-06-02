import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import simulator.fake_data_generator as fdg


class DummyCursor:
    def __init__(self):
        self.commands = []

    def execute(self, query, params):
        self.commands.append((query, params))

    def close(self):
        pass


class DummyConnection:
    def __init__(self):
        self.cursor_obj = DummyCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class TestFakeDataGenerator(unittest.TestCase):
    def test_generate_value_returns_rounded_number_in_range(self):
        base = 50.0
        noise = 5.0
        for _ in range(20):
            value = fdg.generate_value(base, noise)
            self.assertGreaterEqual(value, base - noise)
            self.assertLessEqual(value, base + noise)
            self.assertEqual(round(value, 2), value)

    def test_load_config_returns_default_when_file_missing(self):
        with patch.dict(os.environ, {'FAKEGEN_CONFIG': str(Path(tempfile.gettempdir()) / 'missing_fakegen_config.json')}):
            config = fdg.load_config()
            self.assertEqual(config['table'], 'CurrentValues')
            self.assertEqual(config['tagColumn'], 'TagName')
            self.assertIn('sensors', config)

    def test_load_config_reads_file_from_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / 'fakegen_config.json'
            config_data = {
                'connectionString': 'Driver={ODBC Driver 18 for SQL Server};Server=localhost;Database=eFactory;',
                'table': 'MyTable',
                'tagColumn': 'TagName',
                'valueColumn': 'Value',
                'timestampColumn': 'UpdatedAt',
                'intervalSeconds': 15,
                'sensors': {'Temperature': {'base': 22.0, 'noise': 1.0}},
            }
            config_path.write_text(json.dumps(config_data), encoding='utf-8')
            with patch.dict(os.environ, {'FAKEGEN_CONFIG': str(config_path)}):
                loaded = fdg.load_config()
                self.assertEqual(loaded['table'], 'MyTable')
                self.assertEqual(loaded['intervalSeconds'], 15)
                self.assertIsInstance(loaded['sensors'], dict)

    def test_write_data_to_db_succeeds_with_mocked_connection(self):
        cfg = {
            'connectionString': 'Driver={ODBC Driver 18 for SQL Server};Server=localhost;Database=eFactory;',
            'table': 'CurrentValues',
            'tagColumn': 'TagName',
            'valueColumn': 'Value',
            'timestampColumn': 'UpdatedAt',
            'intervalSeconds': 10,
            'connectionTimeout': 5,
            'connectRetries': 1,
            'connectRetryBaseSeconds': 0.1,
            'connectRetryMaxSeconds': 1,
            'sensors': {
                'Temperature': {'base': 22.0, 'noise': 1.5},
                'Pressure': {'base': 1013.25, 'noise': 10.0},
            },
        }

        dummy_connection = DummyConnection()
        with patch.object(fdg, 'pyodbc') as mock_pyodbc:
            mock_pyodbc.connect.return_value = dummy_connection
            result = fdg.write_data_to_db(cfg)

        self.assertTrue(result)
        self.assertTrue(dummy_connection.committed)
        self.assertTrue(dummy_connection.closed)
        self.assertEqual(len(dummy_connection.cursor_obj.commands), 2)

    def test_write_data_to_db_returns_false_when_connection_fails(self):
        cfg = {
            'connectionString': 'Driver={ODBC Driver 18 for SQL Server};Server=localhost;Database=eFactory;',
            'table': 'CurrentValues',
            'tagColumn': 'TagName',
            'valueColumn': 'Value',
            'timestampColumn': 'UpdatedAt',
            'intervalSeconds': 10,
            'connectionTimeout': 1,
            'connectRetries': 2,
            'connectRetryBaseSeconds': 0.01,
            'connectRetryMaxSeconds': 0.01,
            'sensors': {'Temperature': {'base': 22.0, 'noise': 1.5}},
        }

        class ErrorConnection:
            pass

        with patch.object(fdg, 'pyodbc') as mock_pyodbc:
            mock_pyodbc.connect.side_effect = Exception('connection failed')
            result = fdg.write_data_to_db(cfg)

        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
