"""
eHistorian Gateway — Unified Server (API + Web UI)
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# ui/ je ve stejne slozce jako tento soubor
BASE_DIR = Path(__file__).parent
UI_DIR   = BASE_DIR / 'ui'

app = Flask(
    __name__,
    template_folder=str(UI_DIR),   # index.html
    static_folder=str(UI_DIR),     # styles.css, app.js
    static_url_path=''             # /styles.css misto /static/styles.css
)
CORS(app)

# ── Paths ────────────────────────────────────────────────
CONFIG_FILE = BASE_DIR / 'test.config.json'
LOGS_DIR    = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# ── Process handles ──────────────────────────────────────
processes = {
    'gateway': None
}

# ── Config helpers ───────────────────────────────────────
def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "gatewayId": "line-01-secret",
        "apiUrl":    "http://localhost:5000",
        "opcua":     [],
        "sql":       []
    }

def save_config(config: dict) -> None:
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

# ── Process helpers ──────────────────────────────────────
def start_process(name: str, cmd: str) -> bool:
    try:
        processes[name] = subprocess.Popen(cmd, shell=True)
        return True
    except Exception as e:
        print(f"[ERROR] Starting {name}: {e}")
        return False

def stop_process(name: str) -> bool:
    proc = processes[name]
    if proc is None:
        return True
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    processes[name] = None
    return True

def is_running(name: str) -> bool:
    proc = processes[name]
    return proc is not None and proc.poll() is None

# ── Routes: UI ───────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

# Config (UI)
@app.route('/api/config', methods=['GET', 'POST'])
def ui_config():
    if request.method == 'GET':
        return jsonify(load_config())
    config_data = request.get_json()
    save_config(config_data)
    return jsonify({'status': 'saved'})

# Fix SQL drivers
@app.route('/api/config/fix-drivers', methods=['POST'])
def fix_drivers():
    try:
        import pyodbc
        import re
    except ImportError:
        return jsonify({'status': 'error', 'message': 'Missing pyodbc library'}), 500

    drivers = pyodbc.drivers()
    if not drivers:
        return jsonify({'status': 'error', 'message': 'Žádné ODBC ovladače nebyly nalezeny.'}), 404

    best_driver = None
    priorities = ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"]
    for p in priorities:
        if p in drivers:
            best_driver = p
            break
            
    if not best_driver:
        return jsonify({'status': 'error', 'message': f'Nenalezen žádný kompatibilní ovladač. Dostupné: {drivers}'}), 404

    config = load_config()
    changed = False
    
    for src in config.get('sql', []):
        conn_str = src.get('connectionString', '')
        if conn_str:
            new_conn_str = re.sub(r'Driver=\{[^}]+\}', f'Driver={{{best_driver}}}', conn_str, flags=re.IGNORECASE)
            
            if "ODBC Driver 18" in best_driver:
                if "TrustServerCertificate=yes" not in new_conn_str and "TrustServerCertificate=Yes" not in new_conn_str:
                    new_conn_str = re.sub(r'TrustServerCertificate=no;?', '', new_conn_str, flags=re.IGNORECASE)
                    if not new_conn_str.endswith(';'):
                        new_conn_str += ';'
                    new_conn_str += 'TrustServerCertificate=yes;'
                    
            if new_conn_str != conn_str:
                src['connectionString'] = new_conn_str
                changed = True

    if changed:
        save_config(config)
        return jsonify({'status': 'ok', 'message': f'Ovladač nastaven na {best_driver}'})
    else:
        return jsonify({'status': 'ok', 'message': 'Konfigurace je aktuální.'})

# Status
@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        'gateway': is_running('gateway')
    })

# Device IP
@app.route('/api/ip', methods=['GET'])
def get_ip():
    try:
        import urllib.request
        req = urllib.request.Request('https://api.ipify.org')
        with urllib.request.urlopen(req, timeout=3) as response:
            ip = response.read().decode('utf8')
        return jsonify({'ip': ip})
    except Exception as e:
        return jsonify({'ip': 'unknown', 'error': str(e)})

# Process control
@app.route('/api/processes/<name>', methods=['POST'])
def manage_process(name: str):
    if name not in processes:
        return jsonify({'status': 'error', 'message': 'Unknown process'}), 400

    action = (request.get_json() or {}).get('action')

    if action == 'start':
        if name == 'gateway':
            env = os.environ.copy()
            env["EHG_BOOTSTRAP_CONFIG"] = str(CONFIG_FILE)
            python_exe = str(BASE_DIR / ".venv" / "Scripts" / "python.exe")
            cwd = str(BASE_DIR / "eHistorian.Gateway")
            
            try:
                processes[name] = subprocess.Popen(
                    [python_exe, "-m", "ehistorian_gateway.main"],
                    cwd=cwd,
                    env=env
                )
                success = True
            except Exception as e:
                print(f"[ERROR] Starting {name}: {e}")
                success = False
        else:
            return jsonify({'status': 'error', 'message': 'No command defined'}), 400

        return jsonify({'status': 'started' if success else 'error', 'process': name})

    elif action == 'stop':
        stop_process(name)
        return jsonify({'status': 'stopped', 'process': name})

    return jsonify({'status': 'error', 'message': 'Unknown action'}), 400

# Test event
@app.route('/api/test', methods=['POST'])
def run_test():
    try:
        import requests as req

        url  = "http://localhost:5000/api/ehistorian/gateway/ingest"
        data = {
            "gatewayId": load_config().get('gatewayId', 'test-gateway'),
            "events": [
                {
                    "gatewayId": "test-gateway",
                    "assetId":   101,
                    "source":    "test",
                    "sourceId":  "test-0:asset-101",
                    "tag":       "Temperature",
                    "value":     20 + (hash(str(datetime.now())) % 10),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "quality":   "Good"
                }
            ]
        }

        response = req.post(url, json=data, timeout=5)
        return jsonify({'status': 'ok', 'response': response.json()})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Logs — list
@app.route('/api/logs', methods=['GET'])
def list_logs():
    log_files = sorted(LOGS_DIR.glob('*.json'), reverse=True)
    result = []
    for f in log_files:
        try:
            size = f.stat().st_size
            result.append({
                'name':          f.name,
                'timestamp':     datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                'size':          size,
                'size_readable': f"{size / 1024:.1f} KB" if size > 1024 else f"{size} B"
            })
        except Exception:
            pass
    return jsonify(result)

# Logs — get single
@app.route('/api/log/<filename>', methods=['GET'])
def get_log(filename: str):
    path = LOGS_DIR / filename
    if not path.exists() or path.suffix != '.json':
        return jsonify({'error': 'Not found'}), 404
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Logs — delete single
@app.route('/api/log/<filename>', methods=['DELETE'])
def delete_log(filename: str):
    path = LOGS_DIR / filename
    if not path.exists():
        return jsonify({'error': 'Not found'}), 404
    try:
        path.unlink()
        return jsonify({'status': 'deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Logs — clear all
@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    try:
        deleted = 0
        for f in LOGS_DIR.glob('*.json'):
            f.unlink()
            deleted += 1
        return jsonify({'status': 'cleared', 'deleted': deleted})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Routes: Gateway API ──────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/ehistorian/gateway/config/<gateway_id>', methods=['GET'])
def get_gateway_config(gateway_id):
    # Fix: read actual config from the test.config.json file
    config = load_config()
    print(f'[CONFIG] Gateway {gateway_id} requested config (Returning {len(config.get("opcua", []))} OPC UA, {len(config.get("sql", []))} SQL)')
    return jsonify(config)

@app.route('/api/ehistorian/gateway/ingest', methods=['POST'])
def ingest():
    data = request.get_json()
    gateway_id = data.get('gatewayId', 'unknown')
    events = data.get('events', [])
    
    log_file = LOGS_DIR / f'ingest_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.json'
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f'[INGEST] {len(events)} events from {gateway_id} -> {log_file.name}')
    
    return jsonify({
        'gatewayId': gateway_id,
        'acceptedCount': len(events),
        'rejectedCount': 0,
        'status': 'Accepted'
    })


# ── Entry point ──────────────────────────────────────────
if __name__ == '__main__':
    print()
    print("=" * 50)
    print("  eHistorian Server & Control Panel")
    print("=" * 50)
    print(f"\n  Config : {CONFIG_FILE}")
    print(f"  Logs   : {LOGS_DIR}")
    print(f"  UI     : {UI_DIR}")
    print(f"\n  http://localhost:5000\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
