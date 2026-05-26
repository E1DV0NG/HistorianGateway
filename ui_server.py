"""
eHistorian Gateway — Web UI Server
Slozka ui/ obsahuje index.html, styles.css, app.js
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
    'server':  None,
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

# ── Routes ───────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

# Config
@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'GET':
        return jsonify(load_config())
    config_data = request.get_json()
    save_config(config_data)
    return jsonify({'status': 'saved'})

# Status
@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        'server':  is_running('server'),
        'gateway': is_running('gateway')
    })

# Process control
@app.route('/api/processes/<name>', methods=['POST'])
def manage_process(name: str):
    if name not in processes:
        return jsonify({'status': 'error', 'message': 'Unknown process'}), 400

    action = (request.get_json() or {}).get('action')

    if action == 'start':
        if name == 'server':
            cmd = (
                f'cd /d "{BASE_DIR}" && '
                f'.venv\\Scripts\\activate.bat && '
                f'python server.py'
            )
        elif name == 'gateway':
            cmd = (
                f'cd /d "{BASE_DIR}" && '
                f'.venv\\Scripts\\activate.bat && '
                f'set EHG_BOOTSTRAP_CONFIG={CONFIG_FILE} && '
                f'cd eHistorian.Gateway && '
                f'python -m ehistorian_gateway.main'
            )
        else:
            return jsonify({'status': 'error', 'message': 'No command defined'}), 400

        success = start_process(name, cmd)
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

# ── Entry point ──────────────────────────────────────────
if __name__ == '__main__':
    print()
    print("=" * 50)
    print("  eHistorian Control Panel")
    print("=" * 50)
    print(f"\n  Config : {CONFIG_FILE}")
    print(f"  Logs   : {LOGS_DIR}")
    print(f"  UI     : {UI_DIR}")
    print(f"\n  http://localhost:5001\n")
    app.run(host='0.0.0.0', port=5001, debug=False)