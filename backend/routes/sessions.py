"""
Session Routes - User session management
Handles active user sessions and session metrics
"""

from flask import Blueprint, jsonify, request
import json
import random
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Create blueprint
sessions_bp = Blueprint('sessions', __name__, url_prefix='/api')

# These will be injected by app.py
redis_client = None
command_monitor = None
session_manager = None

def init_sessions(redis, monitor, sess_manager):
    """Initialize sessions blueprint with Redis client, monitor, and session manager"""
    global redis_client, command_monitor, session_manager
    redis_client = redis
    command_monitor = monitor
    session_manager = sess_manager


@sessions_bp.route('/sessions', methods=['GET'])
def get_sessions():
    """Get all active sessions"""
    try:
        sessions = session_manager.get_active_sessions()
        return jsonify({
            'success': True,
            'sessions': sessions,
            'count': len(sessions)
        })
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sessions_bp.route('/sessions/metrics', methods=['GET'])
def get_session_metrics():
    """Get session statistics"""
    try:
        metrics = session_manager.get_session_metrics()
        return jsonify({
            'success': True,
            'metrics': metrics
        })
    except Exception as e:
        logger.error(f"Error getting session metrics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sessions_bp.route('/assets/<asset_id>/sessions', methods=['GET'])
def get_asset_sessions(asset_id):
    """Get sessions associated with a specific asset"""
    try:
        # Get all active sessions
        all_sessions = session_manager.get_active_sessions()
        
        # Filter sessions related to this asset
        asset_sessions = []
        for session in all_sessions:
            user_data = json.loads(session.get('user_data', '{}'))
            
            # Check if user is assigned to this asset or location matches
            if (user_data.get('location') == asset_id or
                user_data.get('assigned_asset') == asset_id or
                asset_id in user_data.get('location', '')):
                asset_sessions.append(session)
        
        # If no direct matches, simulate some sessions for demo purposes
        if not asset_sessions and asset_id:
            # Get asset details for context
            command_monitor.log_command('HGETALL', f'asset:{asset_id}')
            asset_data = redis_client.hgetall(f'asset:{asset_id}')
            asset_name = asset_data.get('name', asset_id)
            
            # Create simulated sessions for this asset
            demo_sessions = []
            if random.random() > 0.3:  # 70% chance of having active sessions
                session_count = random.randint(1, 3)
                for i in range(session_count):
                    role = random.choice(['Field Operator', 'Technician', 'Engineer', 'Supervisor'])
                    name = random.choice(['John Smith', 'Sarah Johnson', 'Mike Chen', 'Lisa Rodriguez', 'Tom Wilson'])
                    
                    demo_sessions.append({
                        'session_id': f'demo-{asset_id}-{i}',
                        'user_id': f'user_{i}',
                        'created_at': (datetime.now() - timedelta(hours=random.randint(1, 8))).isoformat(),
                        'last_activity': (datetime.now() - timedelta(minutes=random.randint(1, 30))).isoformat(),
                        'user_data': json.dumps({
                            'name': name,
                            'role': role,
                            'location': asset_name,
                            'assigned_asset': asset_id,
                            'activity': random.choice(['Monitoring', 'Maintenance', 'Inspection', 'Data Collection'])
                        })
                    })
            
            asset_sessions = demo_sessions
        
        return jsonify({
            'success': True,
            'asset_id': asset_id,
            'sessions': asset_sessions,
            'count': len(asset_sessions)
        })
    except Exception as e:
        logger.error(f"Error getting sessions for asset {asset_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sessions_bp.route('/sessions', methods=['POST'])
def create_session():
    """Create a new session"""
    try:
        data = request.json
        user_id = data.get('user_id')
        user_data = data.get('user_data', {})
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        session_id = session_manager.create_session(user_id, user_data)
        return jsonify({
            'success': True,
            'session_id': session_id
        })
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sessions_bp.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session"""
    try:
        session_manager.delete_session(session_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

