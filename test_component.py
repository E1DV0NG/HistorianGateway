import json
from datetime import datetime
from flask import jsonify, request

GATEWAY_BUFFER_STATUS = {'bytesSize': 0, 'pendingCount': 0, 'maxBytes': 5000}
GATEWAY_SYNC_STATE = {'state': 'synchronized', 'error': None, 'timestamp': None}
SIMULATE_OUTAGE = False

def is_outage_simulated():
    return SIMULATE_OUTAGE

def attach_test_routes(app, load_config_fn, base_dir):
    global SIMULATE_OUTAGE, GATEWAY_BUFFER_STATUS, GATEWAY_SYNC_STATE
    
    @app.route('/api/config/status', methods=['GET'])
    def get_config_status():
        server_config = load_config_fn()
        gateway_cache_path = base_dir / 'eHistorian.Gateway' / 'cache' / 'current_active.json'
        gateway_config = {}
        if gateway_cache_path.exists():
            try:
                with open(gateway_cache_path, 'r', encoding='utf-8') as f:
                    gateway_config = json.load(f)
            except Exception:
                pass
                
        # Remove snapshot timestamps if present for comparison
        gateway_config.pop('_snapshot_timestamp', None)
        server_config.pop('_snapshot_timestamp', None)
        
        def normalize(d):
            return json.dumps(d, sort_keys=True, separators=(',', ':'))
            
        is_pending = normalize(server_config) != normalize(gateway_config)
        
        return jsonify({
            'isPending': is_pending,
            'serverConfig': server_config,
            'gatewayConfig': gateway_config,
            'gatewayState': GATEWAY_SYNC_STATE.get('state', 'unknown'),
            'gatewayError': GATEWAY_SYNC_STATE.get('error')
        })
        
    @app.route('/api/ehistorian/gateway/config-status', methods=['POST'])
    def gateway_config_status():
        data = request.get_json() or {}
        GATEWAY_SYNC_STATE['state'] = data.get('status', 'synchronized')
        GATEWAY_SYNC_STATE['error'] = data.get('error')
        GATEWAY_SYNC_STATE['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        return jsonify({'status': 'ok'})

    @app.route('/api/simulate-outage', methods=['GET', 'POST'])
    def toggle_outage():
        global SIMULATE_OUTAGE
        if request.method == 'POST':
            data = request.get_json() or {}
            if 'simulate' in data:
                SIMULATE_OUTAGE = bool(data['simulate'])
        return jsonify({'simulateOutage': SIMULATE_OUTAGE})

    @app.route('/api/ehistorian/gateway/buffer-status', methods=['GET', 'POST'])
    def handle_buffer_status():
        global GATEWAY_BUFFER_STATUS
        if request.method == 'POST':
            data = request.get_json() or {}
            GATEWAY_BUFFER_STATUS['bytesSize'] = data.get('bytesSize', 0)
            GATEWAY_BUFFER_STATUS['pendingCount'] = data.get('pendingCount', 0)
            GATEWAY_BUFFER_STATUS['maxBytes'] = data.get('maxBytes', 5000)
            return jsonify({'status': 'ok'})
        else:
            return jsonify({
                'simulateOutage': SIMULATE_OUTAGE,
                'buffer': GATEWAY_BUFFER_STATUS
            })
