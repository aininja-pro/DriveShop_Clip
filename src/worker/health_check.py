"""
Simple health check server for the background worker.
Runs alongside the worker to provide health status to Render.
"""

from flask import Flask, jsonify
import threading
import time
from datetime import datetime, timezone
import os

app = Flask(__name__)

# Shared state with the worker
worker_health = {
    'status': 'starting',
    'last_heartbeat': datetime.now(timezone.utc),
    'current_job': None,
    'jobs_processed': 0,
    'worker_id': os.environ.get('WORKER_ID', 'unknown')
}

def update_health(status='healthy', current_job=None, increment_jobs=False):
    """Update health status (called by the worker)"""
    global worker_health
    worker_health['status'] = status
    worker_health['last_heartbeat'] = datetime.now(timezone.utc)
    if current_job is not None:
        worker_health['current_job'] = current_job
    if increment_jobs:
        worker_health['jobs_processed'] += 1

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    global worker_health
    
    # Check if heartbeat is recent (within last 2 minutes)
    time_since_heartbeat = (datetime.now(timezone.utc) - worker_health['last_heartbeat']).total_seconds()
    
    if time_since_heartbeat > 120:
        return jsonify({
            'status': 'unhealthy',
            'message': 'Worker not responding',
            'last_heartbeat_seconds_ago': time_since_heartbeat
        }), 503
    
    return jsonify({
        'status': worker_health['status'],
        'worker_id': worker_health['worker_id'],
        'current_job': worker_health['current_job'],
        'jobs_processed': worker_health['jobs_processed'],
        'last_heartbeat_seconds_ago': time_since_heartbeat
    }), 200

@app.route('/metrics')
def metrics():
    """Detailed metrics endpoint"""
    global worker_health
    
    return jsonify({
        'worker_id': worker_health['worker_id'],
        'status': worker_health['status'],
        'current_job': worker_health['current_job'],
        'jobs_processed': worker_health['jobs_processed'],
        'last_heartbeat': worker_health['last_heartbeat'].isoformat(),
        'uptime_seconds': time.time() - app.start_time if hasattr(app, 'start_time') else 0,
        'environment': {
            'render_service': os.environ.get('RENDER_SERVICE_NAME', 'unknown'),
            'region': os.environ.get('RENDER_REGION', 'unknown'),
            'instance_id': os.environ.get('RENDER_INSTANCE_ID', 'unknown')
        }
    })

def run_health_server():
    """Run the health check server in a separate thread"""
    app.start_time = time.time()
    # Run on port 10000 (Render's default health check port)
    app.run(host='0.0.0.0', port=10000, debug=False)

if __name__ == '__main__':
    run_health_server()