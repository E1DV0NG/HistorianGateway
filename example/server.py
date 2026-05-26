"""
Jednoduchy mock API server - prijima POST a pise do logs
"""

import json
import os
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# Vytvor logs slozku
LOGS_DIR = Path(__file__).parent / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/ehistorian/gateway/config/<gateway_id>', methods=['GET'])
def get_config(gateway_id):
    config = {
        "gatewayId": gateway_id,
        "apiUrl": "http://localhost:5000",
        "opcua": [],
        "sql": []
    }
    print(f'[CONFIG] Gateway {gateway_id} requested config')
    return jsonify(config)

@app.route('/api/ehistorian/gateway/ingest', methods=['POST'])
def ingest():
    data = request.get_json()
    gateway_id = data.get('gatewayId', 'unknown')
    events = data.get('events', [])
    
    # Log do souboru
    log_file = LOGS_DIR / f'ingest_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.json'
    
    with open(log_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f'[INGEST] {len(events)} events from {gateway_id} -> {log_file.name}')
    
    return jsonify({
        'gatewayId': gateway_id,
        'acceptedCount': len(events),
        'rejectedCount': 0,
        'status': 'Accepted'
    })

if __name__ == '__main__':
    print(f'Server na http://0.0.0.0:5000')
    print(f'Logs piseme do: {LOGS_DIR}')
    print()
    app.run(host='0.0.0.0', port=5000, debug=False)
