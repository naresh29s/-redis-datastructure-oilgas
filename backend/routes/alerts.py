"""
Alerts Routes - Alert management and notifications
Handles active alerts and warnings from Redis sorted sets
"""

from flask import Blueprint, jsonify
import json
import logging

logger = logging.getLogger(__name__)

# Create blueprint
alerts_bp = Blueprint('alerts', __name__, url_prefix='/api')

# These will be injected by app.py
redis_client = None
command_monitor = None

def init_alerts(redis, monitor):
    """Initialize alerts blueprint with Redis client and monitor"""
    global redis_client, command_monitor
    redis_client = redis
    command_monitor = monitor


@alerts_bp.route('/dashboard/alerts', methods=['GET'])
def get_active_alerts():
    """Get active alerts and warnings"""
    try:
        # Get alerts from sorted set (by timestamp)
        command_monitor.log_command('ZREVRANGE', 'alerts:active')
        alerts = redis_client.zrevrange('alerts:active', 0, 9, withscores=True)
        
        alert_list = []
        for alert_data, timestamp in alerts:
            alert_info = json.loads(alert_data)
            alert_list.append({
                'id': alert_info.get('id'),
                'type': alert_info.get('type', 'warning'),
                'message': alert_info.get('message'),
                'details': alert_info.get('details', ''),
                'location': alert_info.get('location', 'Unknown'),
                'sensor_id': alert_info.get('sensor_id'),
                'timestamp': alert_info.get('timestamp', timestamp),
                'severity': alert_info.get('severity', 'warning')
            })
        
        return jsonify({
            'success': True,
            'alerts': alert_list,
            'count': len(alert_list)
        })
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

