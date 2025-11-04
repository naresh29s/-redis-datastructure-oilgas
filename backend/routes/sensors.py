"""
Sensor Routes - Sensor data streaming and monitoring
Handles Redis Streams for edge-to-core sensor data ingestion
"""

from flask import Blueprint, jsonify, request
import json
import time
import logging

logger = logging.getLogger(__name__)

# Create blueprint
sensors_bp = Blueprint('sensors', __name__, url_prefix='/api')

# These will be injected by app.py
redis_client = None
command_monitor = None

def init_sensors(redis, monitor):
    """Initialize sensors blueprint with Redis client and monitor"""
    global redis_client, command_monitor
    redis_client = redis
    command_monitor = monitor


@sensors_bp.route('/sensors/data', methods=['POST'])
def ingest_sensor_data():
    """Ingest sensor data using Redis Streams"""
    try:
        data = request.json
        sensor_id = data['sensor_id']
        stream_key = f'sensors:{sensor_id}'
        
        # Add to Redis Stream
        stream_id = redis_client.xadd(stream_key, {
            'timestamp': data.get('timestamp', time.time()),
            'temperature': data.get('temperature', 0),
            'pressure': data.get('pressure', 0),
            'flow_rate': data.get('flow_rate', 0),
            'vibration': data.get('vibration', 0),
            'location': json.dumps(data.get('location', {}))
        })
        
        # Update latest sensor reading
        redis_client.hset(f'sensor:latest:{sensor_id}', mapping=data)
        
        return jsonify({
            'success': True,
            'stream_id': stream_id,
            'sensor_id': sensor_id
        })
    except Exception as e:
        logger.error(f"Error ingesting sensor data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sensors_bp.route('/sensors/<sensor_id>/stream', methods=['GET'])
def get_sensor_stream(sensor_id):
    """Get recent sensor data from stream"""
    try:
        stream_key = f'sensors:{sensor_id}'
        count = int(request.args.get('count', 100))
        
        # Read from Redis Stream
        messages = redis_client.xrevrange(stream_key, count=count)
        
        sensor_data = []
        for msg_id, fields in messages:
            sensor_data.append({
                'id': msg_id,
                'timestamp': float(fields.get('timestamp', 0)),
                'temperature': float(fields.get('temperature', 0)),
                'pressure': float(fields.get('pressure', 0)),
                'flow_rate': float(fields.get('flow_rate', 0)),
                'vibration': float(fields.get('vibration', 0)),
                'location': json.loads(fields.get('location', '{}'))
            })
        
        return jsonify({
            'success': True,
            'sensor_id': sensor_id,
            'data': sensor_data,
            'count': len(sensor_data)
        })
    except Exception as e:
        logger.error(f"Error getting sensor stream: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sensors_bp.route('/sensors/active', methods=['GET'])
def get_active_sensors():
    """Get list of active sensors with latest readings"""
    try:
        # Find all sensor keys
        command_monitor.log_command('KEYS', 'sensor:latest:*')
        sensor_keys = redis_client.keys('sensor:latest:*')
        sensors = []
        
        for key in sensor_keys:
            sensor_id = key.split(':')[-1]
            command_monitor.log_command('HGETALL', key)
            latest_data = redis_client.hgetall(key)
            if latest_data:
                sensors.append({
                    'sensor_id': sensor_id,
                    'latest_reading': latest_data,
                    'last_update': latest_data.get('timestamp', 'unknown')
                })
        
        return jsonify({
            'success': True,
            'sensors': sensors,
            'count': len(sensors)
        })
    except Exception as e:
        logger.error(f"Error getting active sensors: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sensors_bp.route('/assets/<asset_id>/sensors', methods=['GET'])
def get_asset_sensors(asset_id):
    """Get sensors associated with a specific asset"""
    try:
        # Find all sensor keys
        command_monitor.log_command('KEYS', 'sensor:latest:*', context='dashboard')
        sensor_keys = redis_client.keys('sensor:latest:*')
        asset_sensors = []
        
        for key in sensor_keys:
            sensor_id = key.split(':')[-1]
            command_monitor.log_command('HGETALL', key, context='dashboard')
            latest_data = redis_client.hgetall(key)
            if latest_data and latest_data.get('location') == asset_id:
                asset_sensors.append({
                    'sensor_id': sensor_id,
                    'type': latest_data.get('type', 'unknown'),
                    'value': latest_data.get('value', '0'),
                    'unit': latest_data.get('unit', ''),
                    'location': latest_data.get('location', 'unknown'),
                    'timestamp': latest_data.get('timestamp', ''),
                    'status': latest_data.get('status', 'active'),
                    'latest_reading': latest_data
                })
        
        return jsonify({
            'success': True,
            'asset_id': asset_id,
            'sensors': asset_sensors,
            'count': len(asset_sensors)
        })
    except Exception as e:
        logger.error(f"Error getting sensors for asset {asset_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

