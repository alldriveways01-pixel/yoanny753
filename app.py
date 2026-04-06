import os
import time
import threading
from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS
from proxy_farm import ProxyFarmCore

app = Flask(__name__)
CORS(app)
# Enable CORS for all origins during development
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize the core orchestrator
core = ProxyFarmCore()

# --- BACKGROUND UPDATER ---
def background_updater():
    """Continuously pushes system status to connected clients."""
    while True:
        try:
            status = core.get_system_status()
            socketio.emit('status_update', status)
            
            if core.monitoring:
                hunting_data = {
                    'logs': core.seeker.logs,
                    'hunters': core.seeker.get_hunting_status().get('hunters', {}),
                    'stats': core.seeker.get_hunter_stats()
                }
                socketio.emit('hunting_update', hunting_data)
                
        except Exception as e:
            print(f"Background updater error: {e}")
        time.sleep(2)

# Start the background thread
update_thread = threading.Thread(target=background_updater, daemon=True)
update_thread.start()

# --- WEBSOCKET EVENTS ---
@socketio.on('connect')
def handle_connect():
    print("Client connected")
    socketio.emit('status_update', core.get_system_status())

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

@socketio.on('request_update')
def handle_request_update():
    socketio.emit('status_update', core.get_system_status())

# --- REST API ENDPOINTS ---

@app.route('/api/system/status', methods=['GET'])
def get_status():
    return jsonify(core.get_system_status())

@app.route('/api/system/initialize', methods=['POST'])
def initialize_system():
    success = core.initialize()
    return jsonify({"success": success})

@app.route('/api/system/deploy', methods=['POST'])
def deploy_nodes():
    data = request.json or {}
    node_count = data.get('node_count', 6) # CHANGED: Default to 6
    success = core.deploy_nodes(node_count=node_count)
    return jsonify({"success": success})

@app.route('/api/system/start-monitoring', methods=['POST'])
def start_monitoring():
    success = core.start_monitoring()
    return jsonify({"success": success})

@app.route('/api/system/stop-monitoring', methods=['POST'])
def stop_monitoring():
    success = core.stop_monitoring()
    return jsonify({"success": success})

@app.route('/api/system/cleanup', methods=['POST'])
def cleanup():
    success = core.cleanup()
    return jsonify({"success": success})

@app.route('/api/system/rotate', methods=['POST'])
def force_rotation():
    # Run rotation in a background thread so we don't block the API response
    threading.Thread(target=core.force_rotation).start()
    return jsonify({"success": True, "message": "Rotation initiated"})

@app.route('/api/system/auto-rotate', methods=['POST'])
def toggle_auto_rotate():
    data = request.json or {}
    enabled = data.get('enabled', True)
    success = core.toggle_auto_rotation(enabled)
    return jsonify({"success": success})

@app.route('/api/nodes/<int:node_id>', methods=['GET'])
def get_node_details(node_id):
    node = core.get_detailed_node(node_id)
    if node:
        return jsonify(node)
    return jsonify({"error": "Node not found"}), 404

# --- LAB & ANALYSIS ENDPOINTS (Stubs for now) ---

@app.route('/api/lab/assign', methods=['POST'])
def assign_lab_strategy():
    data = request.json or {}
    node_id = data.get('node_id')
    strategy = data.get('strategy')
    if not node_id or not strategy:
        return jsonify({"error": "Missing node_id or strategy"}), 400
    success = core.lab_manager.assign_strategy(node_id, strategy)
    return jsonify({"success": success})

@app.route('/api/lab/status', methods=['GET'])
def get_lab_status():
    return jsonify({"is_running": core.lab_manager.is_test_running()})

@app.route('/api/explorer/data', methods=['GET'])
def get_explorer_data():
    return jsonify(core.get_ip_explorer_data())

@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    if request.method == 'POST':
        success = core.update_configuration(request.json)
        return jsonify({"success": success})
    return jsonify(core.get_configuration())

if __name__ == '__main__':
    print("Starting Proxy Farm OS Backend on port 3001...")
    # Run with socketio to support WebSockets
    socketio.run(app, host='0.0.0.0', port=3001, debug=True, use_reloader=False)
