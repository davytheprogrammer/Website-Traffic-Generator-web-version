from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_socketio import SocketIO
import threading
import json
import os
import time
from datetime import datetime

# Import custom modules
from url_validator import validate_url
from traffic_generator import TrafficGenerator

app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app)

# Active traffic generation sessions
active_sessions = {}

@app.route('/')
def index():
    """Main page with disclaimer and input form"""
    # Check if user has acknowledged disclaimer
    if not session.get('disclaimer_accepted', False):
        return redirect(url_for('disclaimer'))
    return render_template('index.html')

@app.route('/disclaimer')
def disclaimer():
    """Disclaimer page that users must accept before using the tool"""
    return render_template('disclaimer.html')

@app.route('/accept-disclaimer', methods=['POST'])
def accept_disclaimer():
    """Mark the disclaimer as accepted"""
    session['disclaimer_accepted'] = True
    return redirect(url_for('index'))

@app.route('/validate-url', methods=['POST'])
def validate_url_endpoint():
    """Endpoint to validate a URL before starting traffic generation"""
    data = request.json
    url = data.get('url', '')
    
    # Validate the URL
    is_valid, message = validate_url(url)
    
    return jsonify({
        'valid': is_valid,
        'message': message
    })

@app.route('/dashboard')
def dashboard():
    """Dashboard page for visualizing traffic generation"""
    # Get URL and visit count from query parameters
    url = request.args.get('url', '')
    visit_count = request.args.get('visits', 0, type=int)
    
    # Validate input
    if not url or visit_count <= 0 or visit_count > 500:
        return redirect(url_for('index'))
    
    return render_template(
        'dashboard.html', 
        url=url, 
        max_visits=visit_count,
        start_time=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    )

@app.route('/start-traffic', methods=['POST'])
def start_traffic():
    """Start traffic generation process"""
    data = request.json
    url = data.get('url', '')
    visit_count = data.get('visits', 0)
    
    # Validate inputs
    if not url or visit_count <= 0 or visit_count > 500:
        return jsonify({'success': False, 'message': 'Invalid parameters'})
    
    # Generate unique session ID
    session_id = f"{int(time.time())}-{os.urandom(4).hex()}"
    
    # Create traffic generator
    generator = TrafficGenerator(url, visit_count, session_id, socketio)
    
    # Start generation in a separate thread
    thread = threading.Thread(target=generator.start)
    thread.daemon = True
    thread.start()
    
    # Store active session
    active_sessions[session_id] = {
        'generator': generator,
        'thread': thread,
        'url': url,
        'max_visits': visit_count,
        'started_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return jsonify({
        'success': True, 
        'session_id': session_id
    })

@app.route('/stop-traffic', methods=['POST'])
def stop_traffic():
    """Stop an active traffic generation session"""
    data = request.json
    session_id = data.get('session_id', '')
    
    if session_id in active_sessions:
        active_sessions[session_id]['generator'].stop()
        del active_sessions[session_id]
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Session not found'})

@app.route('/session-status/<session_id>')
def session_status(session_id):
    """Get the status of a traffic generation session"""
    if session_id in active_sessions:
        generator = active_sessions[session_id]['generator']
        return jsonify({
            'active': generator.is_active(),
            'visits_completed': generator.visits_completed,
            'max_visits': generator.max_visits,
            'urls_visited': generator.urls_visited
        })
    
    return jsonify({'active': False, 'message': 'Session not found'})

@socketio.on('connect')
def handle_connect():
    """Handle client connection to WebSocket"""
    pass

if __name__ == '__main__':
    # Use debug=False in production
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)