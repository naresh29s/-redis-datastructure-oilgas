#!/usr/bin/env python3
"""
Oil & Gas Field Operations Demo - Backend API
Redis Enterprise Demo for Halliburton

Features:
1. Geospatial Asset Tracking
2. Edge-to-Core Streaming with Redis Streams
3. Real-Time Operational Dashboard
"""

from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
import redis
import json
import time
import random
import os
import uuid
import threading
from datetime import datetime, timedelta
from collections import deque
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ============================================================================
# REDIS COMMAND MONITORING
# ============================================================================

class RedisCommandMonitor:
    """Monitor and log Redis commands for demo purposes"""

    def __init__(self, redis_client=None, max_commands=500):
        self.redis = redis_client
        self.max_commands = max_commands
        self.lock = threading.Lock()
        # Fallback to in-memory storage if Redis is not available
        self.commands = deque(maxlen=max_commands) if not redis_client else None

    def log_command(self, command, key=None, result=None, context=None):
        """Log a Redis command with timestamp and context"""
        with self.lock:
            command_info = {
                'timestamp': datetime.now().isoformat(),
                'command': command,
                'key': key,
                'result': str(result)[:100] if result else None,  # Truncate long results
                'type': self._categorize_command(command),
                'context': context or self._determine_context(command, key)
            }

            # Store in Redis if available, otherwise use in-memory storage
            if self.redis:
                try:
                    # Store command in Redis using a sorted set with timestamp as score
                    context_key = f"command_log:{command_info['context']}"
                    score = time.time()  # Use timestamp as score for ordering

                    # Add command to sorted set
                    self.redis.zadd(context_key, {json.dumps(command_info): score})

                    # Keep only the most recent commands (trim old ones)
                    total_commands = self.redis.zcard(context_key)
                    if total_commands > self.max_commands:
                        # Remove oldest commands, keep only max_commands
                        self.redis.zremrangebyrank(context_key, 0, total_commands - self.max_commands - 1)

                except Exception as e:
                    # Fallback to in-memory if Redis operation fails
                    if self.commands is None:
                        self.commands = deque(maxlen=self.max_commands)
                    self.commands.append(command_info)
            else:
                # Use in-memory storage
                if self.commands is None:
                    self.commands = deque(maxlen=self.max_commands)
                self.commands.append(command_info)

    def _categorize_command(self, command):
        """Categorize Redis commands by type"""
        read_commands = {'GET', 'HGET', 'HGETALL', 'XREAD', 'XRANGE', 'XREVRANGE', 'ZRANGE', 'ZREVRANGE', 'GEORADIUS', 'GEOPOS', 'KEYS', 'EXISTS', 'TTL'}
        write_commands = {'SET', 'HSET', 'XADD', 'ZADD', 'GEOADD', 'INCR', 'EXPIRE', 'DEL', 'ZREM', 'DECR'}

        if command in read_commands:
            return 'read'
        elif command in write_commands:
            return 'write'
        else:
            return 'other'

    def _determine_context(self, command, key):
        """Determine the context of a Redis command based on command and key patterns"""
        if not key:
            return 'dashboard'

        key_str = str(key).lower()

        # Session-related patterns
        if any(pattern in key_str for pattern in ['session:', 'sessions:active']):
            return 'session'

        # Dashboard-related patterns
        if any(pattern in key_str for pattern in [
            'asset:', 'assets:locations', 'sensor:', 'alerts:', 'metrics:', 'system:'
        ]):
            return 'dashboard'

        # Default to dashboard for unknown patterns
        return 'dashboard'

    def get_recent_commands(self, limit=50, context=None):
        """Get recent commands for display, optionally filtered by context"""
        try:
            if self.redis and context:
                # Get commands for specific context from Redis (simplified)
                context_key = f"command_log:{context}"
                # Get most recent commands (highest scores) with a reasonable limit
                raw_commands = self.redis.zrevrange(context_key, 0, min(limit - 1, 100))
                commands = []
                for raw_cmd in raw_commands:
                    try:
                        cmd = json.loads(raw_cmd)
                        commands.append(cmd)
                    except (json.JSONDecodeError, TypeError):
                        continue
                return commands
            elif self.redis and not context:
                # For all contexts, just return dashboard commands to avoid performance issues
                context_key = "command_log:dashboard"
                raw_commands = self.redis.zrevrange(context_key, 0, min(limit - 1, 50))
                commands = []
                for raw_cmd in raw_commands:
                    try:
                        cmd = json.loads(raw_cmd)
                        commands.append(cmd)
                    except (json.JSONDecodeError, TypeError):
                        continue
                return commands
            else:
                # Fallback to in-memory storage
                if self.commands:
                    commands = list(self.commands)
                    if context:
                        commands = [cmd for cmd in commands if cmd.get('context') == context]
                    return commands[-limit:]
                return []
        except Exception as e:
            logger.error(f"Error getting recent commands: {e}")
            return []

    def get_command_stats(self, context=None):
        """Get command statistics, optionally filtered by context"""
        try:
            # Get a smaller sample of recent commands to avoid performance issues
            commands = self.get_recent_commands(limit=100, context=context)

            read_count = sum(1 for cmd in commands if cmd.get('type') == 'read')
            write_count = sum(1 for cmd in commands if cmd.get('type') == 'write')
            total_count = len(commands)

            return {
                'read_count': read_count,
                'write_count': write_count,
                'total_count': total_count
            }
        except Exception as e:
            logger.error(f"Error getting command stats: {e}")
            return {
                'read_count': 0,
                'write_count': 0,
                'total_count': 0
            }

    def clear_command_history(self, context=None):
        """Clear command history for a specific context or all contexts"""
        with self.lock:
            if self.redis:
                try:
                    if context:
                        # Clear specific context
                        context_key = f"command_log:{context}"
                        self.redis.delete(context_key)
                    else:
                        # Clear all contexts
                        for ctx in ['dashboard', 'session', 'search']:
                            context_key = f"command_log:{ctx}"
                            self.redis.delete(context_key)
                except Exception:
                    pass

            # Also clear in-memory storage if it exists
            if self.commands:
                self.commands.clear()

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

class SessionManager:
    """Manage user sessions using Redis"""

    def __init__(self, redis_client, monitor):
        self.redis = redis_client
        self.monitor = monitor
        self.session_ttl = 3600  # 1 hour session timeout

    def create_session(self, user_id, user_data=None):
        """Create a new user session"""
        session_id = str(uuid.uuid4())
        session_key = f'session:{session_id}'

        session_data = {
            'session_id': session_id,
            'user_id': user_id,
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'user_data': json.dumps(user_data or {})
        }

        # Store session with TTL
        self.monitor.log_command('HSET', session_key, context='session')
        self.redis.hset(session_key, mapping=session_data)

        self.monitor.log_command('EXPIRE', session_key, context='session')
        self.redis.expire(session_key, self.session_ttl)

        # Add to active sessions set
        self.monitor.log_command('ZADD', 'sessions:active', context='session')
        self.redis.zadd('sessions:active', {session_id: time.time()})

        return session_id

    def get_session(self, session_id):
        """Get session data"""
        try:
            session_key = f'session:{session_id}'
            session_data = self.redis.hgetall(session_key)

            if session_data:
                # Update last activity
                self.redis.hset(session_key, 'last_activity', datetime.now().isoformat())
                # Refresh TTL
                self.redis.expire(session_key, self.session_ttl)

                # Add status and TTL information
                ttl = self.redis.ttl(session_key)
                session_data['status'] = 'active' if ttl > 0 else 'expired'
                session_data['ttl'] = ttl if ttl > 0 else 0

                return session_data
            return None
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return None

    def delete_session(self, session_id):
        """Delete a session"""
        session_key = f'session:{session_id}'

        self.monitor.log_command('DEL', session_key, context='session')
        self.redis.delete(session_key)

        self.monitor.log_command('ZREM', 'sessions:active', context='session')
        self.redis.zrem('sessions:active', session_id)

    def get_active_sessions(self):
        """Get all active sessions"""
        try:
            session_ids = self.redis.zrange('sessions:active', 0, -1)
            sessions = []

            for session_id in session_ids:
                session_key = f'session:{session_id}'
                # Get session data directly without logging to avoid circular dependency
                session_data = self.redis.hgetall(session_key)

                if session_data:
                    # Add status and TTL information
                    ttl = self.redis.ttl(session_key)
                    session_data['status'] = 'active' if ttl > 0 else 'expired'
                    session_data['ttl'] = ttl if ttl > 0 else 0
                    sessions.append(session_data)
                else:
                    # Clean up expired session from active set
                    self.redis.zrem('sessions:active', session_id)

            return sessions
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []

    def get_session_metrics(self):
        """Get session statistics"""
        active_sessions = self.get_active_sessions()

        return {
            'total_active_sessions': len(active_sessions),
            'unique_users': len(set(s.get('user_id', '') for s in active_sessions)),
            'avg_session_duration': self._calculate_avg_duration(active_sessions),
            'sessions_by_user': self._group_by_user(active_sessions)
        }

    def _calculate_avg_duration(self, sessions):
        """Calculate average session duration in minutes"""
        if not sessions:
            return 0

        total_duration = 0
        for session in sessions:
            created_at = datetime.fromisoformat(session.get('created_at', ''))
            duration = (datetime.now() - created_at).total_seconds() / 60
            total_duration += duration

        return round(total_duration / len(sessions), 2)

    def _group_by_user(self, sessions):
        """Group sessions by user"""
        user_sessions = {}
        for session in sessions:
            user_id = session.get('user_id', 'unknown')
            if user_id not in user_sessions:
                user_sessions[user_id] = 0
            user_sessions[user_id] += 1
        return user_sessions

# Redis Cloud connection configuration
# Credentials are loaded from .env file (see .env.example for template)
REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_USERNAME = os.getenv('REDIS_USERNAME', 'default')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')

# Validate required environment variables
if not REDIS_HOST:
    logger.error("❌ REDIS_HOST environment variable is not set!")
    logger.error("Please copy .env.example to .env and configure your Redis credentials.")
    exit(1)

if not REDIS_PASSWORD:
    logger.error("❌ REDIS_PASSWORD environment variable is not set!")
    logger.error("Please copy .env.example to .env and configure your Redis credentials.")
    exit(1)

try:
    # Connect to Redis Cloud with authentication
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_connect_timeout=10,
        socket_timeout=10
    )

    # Test connection
    redis_client.ping()
    logger.info(f"✅ Connected to Redis Cloud at {REDIS_HOST}:{REDIS_PORT}")

    # Test RedisJSON and RediSearch modules
    try:
        # Test RedisJSON
        redis_client.execute_command('JSON.SET', 'test:json', '.', '{"test": "value"}')
        redis_client.execute_command('JSON.GET', 'test:json')
        redis_client.delete('test:json')
        logger.info("✅ RedisJSON module is available")

        # Test RediSearch (check if module is loaded)
        modules = redis_client.execute_command('MODULE', 'LIST')
        search_available = any('search' in str(module).lower() for module in modules)
        if search_available:
            logger.info("✅ RediSearch module is available")
        else:
            logger.warning("⚠️ RediSearch module not detected")

    except Exception as module_e:
        logger.warning(f"⚠️ Module test failed: {module_e}")

    # Initialize monitoring and session management
    command_monitor = RedisCommandMonitor(redis_client)
    session_manager = SessionManager(redis_client, command_monitor)

    # Create some demo sessions for the demo
    demo_users = [
        {'user_id': 'operator_1', 'name': 'John Smith', 'role': 'Field Operator', 'location': 'Rig Alpha'},
        {'user_id': 'supervisor_1', 'name': 'Sarah Johnson', 'role': 'Field Supervisor', 'location': 'Control Center'},
        {'user_id': 'engineer_1', 'name': 'Mike Chen', 'role': 'Drilling Engineer', 'location': 'Rig Bravo'},
        {'user_id': 'technician_1', 'name': 'Lisa Rodriguez', 'role': 'Maintenance Tech', 'location': 'Service Truck 001'}
    ]

    # Create demo sessions
    for user in demo_users:
        session_manager.create_session(user['user_id'], user)

    logger.info("✅ Initialized command monitoring and session management")

except Exception as e:
    logger.error(f"❌ Failed to connect to Redis: {e}")
    redis_client = None
    command_monitor = None
    session_manager = None

# ============================================================================
# 1. GEOSPATIAL ASSET TRACKING
# ============================================================================

@app.route('/api/assets', methods=['GET'])
def get_assets():
    """Get all field assets with their locations"""
    try:
        # Get all assets from geospatial index
        command_monitor.log_command('ZRANGE', 'assets:locations', context='dashboard')
        assets = redis_client.zrange('assets:locations', 0, -1, withscores=False)
        asset_data = []

        for asset_id in assets:
            # Get asset position
            command_monitor.log_command('GEOPOS', 'assets:locations', context='dashboard')
            position = redis_client.geopos('assets:locations', asset_id)
            if position and position[0]:
                lon, lat = position[0]

                # Get asset details using RedisJSON
                command_monitor.log_command('JSON.GET', f'asset:{asset_id}', context='dashboard')
                asset_json = redis_client.execute_command('JSON.GET', f'asset:{asset_id}')

                if asset_json:
                    import json
                    asset_doc = json.loads(asset_json)
                    asset_info = asset_doc.get('asset', {})

                    # Extract only the essential fields for UI display
                    asset_data.append({
                        'id': asset_id,
                        'name': asset_info.get('name', asset_id),
                        'type': asset_info.get('type', 'unknown'),
                        'status': asset_info.get('status', {}).get('state', 'active'),
                        'latitude': lat,
                        'longitude': lon,
                        'temperature': asset_info.get('metrics', {}).get('temperature_c', 0),
                        'pressure': asset_info.get('metrics', {}).get('pressure_psi', 0),
                        'last_update': asset_info.get('status', {}).get('last_update', datetime.now().isoformat())
                    })
        
        return jsonify({
            'success': True,
            'assets': asset_data,
            'count': len(asset_data)
        })
    except Exception as e:
        logger.error(f"Error getting assets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/assets/<asset_id>', methods=['GET'])
def get_asset_details(asset_id):
    """Get detailed information about a specific asset"""
    try:
        # Get asset position
        command_monitor.log_command('GEOPOS', 'assets:locations', context='dashboard')
        position = redis_client.geopos('assets:locations', asset_id)

        if not position or not position[0]:
            return jsonify({'success': False, 'error': 'Asset not found'}), 404

        lon, lat = position[0]

        # Get asset details using RedisJSON
        command_monitor.log_command('JSON.GET', f'asset:{asset_id}', context='dashboard')
        asset_json = redis_client.execute_command('JSON.GET', f'asset:{asset_id}')

        if not asset_json:
            return jsonify({'success': False, 'error': 'Asset not found'}), 404

        import json
        asset_doc = json.loads(asset_json)
        asset_info = asset_doc.get('asset', {})

        asset_details = {
            'id': asset_id,
            'name': asset_info.get('name', asset_id),
            'type': asset_info.get('type', 'unknown'),
            'status': asset_info.get('status', {}).get('state', 'active'),
            'latitude': lat,
            'longitude': lon,
            'temperature': asset_info.get('metrics', {}).get('temperature_c', 0),
            'pressure': asset_info.get('metrics', {}).get('pressure_psi', 0),
            'flow_rate': asset_info.get('metrics', {}).get('flow_rate_bbl_per_hr', 0),
            'vibration': asset_info.get('metrics', {}).get('vibration_mm_s', 0),
            'last_update': asset_info.get('status', {}).get('last_update', ''),
            'description': f'{asset_info.get("type", "Asset").title()} located in {asset_info.get("location", {}).get("zone", "the field")}',
            'operational_since': asset_info.get('model', {}).get('install_date', '2023-01-01'),
            'maintenance_schedule': 'Monthly',
            'manufacturer': asset_info.get('model', {}).get('manufacturer', 'Unknown'),
            'model': asset_info.get('model', {}).get('model_number', 'Unknown'),
            'health_score': asset_info.get('status', {}).get('health_score', 95)
        }

        return jsonify({
            'success': True,
            'asset': asset_details
        })
    except Exception as e:
        logger.error(f"Error getting asset details for {asset_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/assets/nearby', methods=['GET'])
def get_nearby_assets():
    """Find assets within radius of a location"""
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        radius = float(request.args.get('radius', 10))  # km
        
        # Use Redis GEORADIUS command
        nearby = redis_client.georadius(
            'assets:locations', lon, lat, radius, unit='km',
            withdist=True, withcoord=True
        )
        
        nearby_assets = []
        for asset_id, distance, coords in nearby:
            asset_info = redis_client.hgetall(f'asset:{asset_id}')
            nearby_assets.append({
                'id': asset_id,
                'name': asset_info.get('name', asset_id),
                'type': asset_info.get('type', 'unknown'),
                'distance_km': round(distance, 2),
                'latitude': coords[1],
                'longitude': coords[0]
            })
        
        return jsonify({
            'success': True,
            'nearby_assets': nearby_assets,
            'search_center': {'lat': lat, 'lon': lon},
            'radius_km': radius,
            'count': len(nearby_assets)
        })
    except Exception as e:
        logger.error(f"Error finding nearby assets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/assets/<asset_id>/update', methods=['POST'])
def update_asset_location(asset_id):
    """Update asset location and details"""
    try:
        data = request.json
        lat = data['latitude']
        lon = data['longitude']
        
        # Update geospatial location
        redis_client.geoadd('assets:locations', (lon, lat, asset_id))
        
        # Update asset details
        asset_data = {
            'name': data.get('name', asset_id),
            'type': data.get('type', 'equipment'),
            'status': data.get('status', 'active'),
            'last_update': datetime.now().isoformat()
        }
        redis_client.hset(f'asset:{asset_id}', mapping=asset_data)
        
        return jsonify({'success': True, 'message': f'Asset {asset_id} updated'})
    except Exception as e:
        logger.error(f"Error updating asset: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# 2. EDGE-TO-CORE STREAMING WITH REDIS STREAMS
# ============================================================================

@app.route('/api/sensors/data', methods=['POST'])
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

@app.route('/api/sensors/<sensor_id>/stream', methods=['GET'])
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

@app.route('/api/sensors/active', methods=['GET'])
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

@app.route('/api/assets/<asset_id>/sensors', methods=['GET'])
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

# ============================================================================
# 3. REAL-TIME OPERATIONAL DASHBOARD
# ============================================================================

@app.route('/api/dashboard/kpis', methods=['GET'])
def get_dashboard_kpis():
    """Get real-time KPIs for operational dashboard"""
    try:
        # Get current metrics
        kpis = {
            'total_assets': redis_client.zcard('assets:locations') or 0,
            'active_sensors': len(redis_client.keys('sensor:latest:*')),
            'total_alerts': redis_client.get('alerts:count') or 0,
            'avg_temperature': redis_client.get('metrics:avg_temperature') or 0,
            'avg_pressure': redis_client.get('metrics:avg_pressure') or 0,
            'total_production': redis_client.get('metrics:total_production') or 0,
            'system_uptime': redis_client.get('system:uptime') or 0
        }
        
        # Convert string values to numbers
        for key, value in kpis.items():
            try:
                kpis[key] = float(value)
            except (ValueError, TypeError):
                kpis[key] = 0
        
        return jsonify({
            'success': True,
            'kpis': kpis,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting KPIs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/assets/<asset_id>/kpis', methods=['GET'])
def get_asset_kpis(asset_id):
    """Get KPIs specific to an asset"""
    try:
        # Get asset details using RedisJSON
        command_monitor.log_command('JSON.GET', f'asset:{asset_id}', context='dashboard')
        asset_json = redis_client.execute_command('JSON.GET', f'asset:{asset_id}')

        if not asset_json:
            return jsonify({'success': False, 'error': 'Asset not found'}), 404

        import json
        asset_doc = json.loads(asset_json)
        asset_info = asset_doc.get('asset', {})
        asset_type = asset_info.get('type', 'unknown')

        # Generate asset-specific KPIs based on type
        if asset_type == 'drilling_rig':
            kpis = {
                'drilling_depth': random.uniform(8000, 12000),  # feet
                'drilling_rate': random.uniform(15, 45),  # ft/hr
                'mud_weight': random.uniform(9.5, 12.0),  # ppg
                'rotary_speed': random.uniform(80, 150),  # rpm
                'uptime_hours': random.uniform(20, 24),  # hours today
                'efficiency': random.uniform(85, 95)  # percentage
            }
        elif asset_type == 'pump_jack':
            kpis = {
                'production_rate': random.uniform(50, 200),  # bpd
                'water_cut': random.uniform(15, 45),  # percentage
                'pump_efficiency': random.uniform(75, 90),  # percentage
                'runtime_hours': random.uniform(22, 24),  # hours today
                'pressure_avg': random.uniform(2200, 2800),  # psi
                'temperature_avg': random.uniform(75, 95),  # °F
                'stroke_rate': random.uniform(8, 15)  # strokes per minute
            }
        elif asset_type in ['production_well', 'injection_well', 'monitoring_well']:
            kpis = {
                'production_rate': random.uniform(30, 150),  # bpd
                'water_cut': random.uniform(10, 50),  # percentage
                'well_efficiency': random.uniform(70, 95),  # percentage
                'runtime_hours': random.uniform(20, 24),  # hours today
                'pressure_avg': random.uniform(1500, 3500),  # psi
                'temperature_avg': random.uniform(70, 110),  # °F
                'flow_rate': random.uniform(5, 80)  # bbl/hr
            }
        elif asset_type == 'compressor':
            kpis = {
                'compression_ratio': random.uniform(3.5, 6.0),
                'throughput': random.uniform(5, 25),  # MMSCFD
                'efficiency': random.uniform(80, 92),  # percentage
                'vibration_level': random.uniform(1.5, 4.0),  # mm/s
                'operating_hours': random.uniform(20, 24),  # hours today
                'fuel_consumption': random.uniform(800, 1500),  # scf/hr
                'discharge_pressure': random.uniform(500, 1200)  # psi
            }
        elif asset_type == 'separator':
            kpis = {
                'separation_efficiency': random.uniform(85, 98),  # percentage
                'throughput': random.uniform(50, 200),  # bbl/hr
                'water_content': random.uniform(10, 30),  # percentage
                'operating_hours': random.uniform(22, 24),  # hours today
                'pressure_drop': random.uniform(5, 25),  # psi
                'temperature_avg': random.uniform(70, 100)  # °F
            }
        elif asset_type == 'tank_battery':
            kpis = {
                'tank_level': random.uniform(25, 85),  # percentage
                'capacity_utilization': random.uniform(60, 90),  # percentage
                'throughput': random.uniform(20, 100),  # bbl/hr
                'operating_hours': random.uniform(24, 24),  # hours today (always on)
                'temperature_avg': random.uniform(60, 85),  # °F
                'total_capacity': random.uniform(5000, 20000)  # barrels
            }
        elif asset_type == 'service_truck':
            kpis = {
                'fuel_level': random.uniform(30, 90),  # percentage
                'operating_hours': random.uniform(8, 16),  # hours today
                'efficiency': random.uniform(75, 95),  # percentage
                'maintenance_due': random.choice([True, False, False, False]),
                'last_service': f"{random.randint(5, 30)} days ago",
                'total_miles': random.uniform(50000, 200000)  # total miles
            }
        else:
            # Generic equipment KPIs
            kpis = {
                'uptime': random.uniform(95, 99),  # percentage
                'efficiency': random.uniform(80, 95),  # percentage
                'operating_hours': random.uniform(18, 24),  # hours today
                'maintenance_due': random.choice([True, False, False, False]),
                'last_service': f"{random.randint(5, 30)} days ago"
            }

        # Add common metrics
        kpis.update({
            'asset_id': asset_id,
            'asset_name': asset_info.get('name', asset_id),
            'asset_type': asset_type,
            'status': asset_info.get('status', {}).get('state', 'active'),
            'last_update': asset_info.get('status', {}).get('last_update', datetime.now().isoformat())
        })

        return jsonify({
            'success': True,
            'asset_id': asset_id,
            'kpis': kpis,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting KPIs for asset {asset_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dashboard/alerts', methods=['GET'])
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

# ============================================================================
# HEALTH CHECK AND STATUS
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        redis_client.ping()
        return jsonify({
            'status': 'healthy',
            'redis_connected': True,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'redis_connected': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/', methods=['GET'])
def index():
    """Serve the frontend HTML"""
    try:
        # Serve the frontend HTML file
        frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'index.html')
        if os.path.exists(frontend_path):
            with open(frontend_path, 'r', encoding='utf-8') as f:
                return f.read(), 200, {'Content-Type': 'text/html'}
        else:
            # Fallback to API documentation if frontend not found
            return jsonify({
                'service': 'Oil & Gas Field Operations Demo API',
                'version': '1.0.0',
                'features': [
                    'Geospatial Asset Tracking',
                    'Edge-to-Core Streaming',
                    'Real-Time Operational Dashboard'
                ],
                'endpoints': {
                    'assets': '/api/assets',
                    'nearby_assets': '/api/assets/nearby?lat=X&lon=Y&radius=Z',
                    'sensor_data': '/api/sensors/data (POST)',
                    'sensor_stream': '/api/sensors/{id}/stream',
                    'dashboard_kpis': '/api/dashboard/kpis',
                    'alerts': '/api/dashboard/alerts',
                    'health': '/health'
                },
                'note': f'Frontend HTML not found at: {frontend_path}'
            })
    except Exception as e:
        logger.error(f"Error serving frontend: {e}")
        return jsonify({'error': 'Failed to serve frontend', 'details': str(e)}), 500

# ============================================================================
# SESSION MANAGEMENT ENDPOINTS
# ============================================================================

@app.route('/api/sessions', methods=['GET'])
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

@app.route('/api/sessions/metrics', methods=['GET'])
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

@app.route('/api/assets/<asset_id>/sessions', methods=['GET'])
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

@app.route('/api/sessions', methods=['POST'])
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

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session"""
    try:
        session_manager.delete_session(session_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# ASSET SEARCH ENDPOINTS (RediSearch)
# ============================================================================

@app.route('/api/search/assets')
def search_assets():
    """Search assets using RediSearch with filters and full-text search"""
    try:
        # Get search parameters
        query = request.args.get('q', '*')  # Default to match all
        asset_type = request.args.get('type', '')
        manufacturer = request.args.get('manufacturer', '')
        status = request.args.get('status', '')
        region = request.args.get('region', '')
        team = request.args.get('team', '')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))

        # Build search query
        search_parts = []

        # Add text search if provided
        if query and query != '*':
            search_parts.append(f"({query})")

        # Add filters
        if asset_type:
            search_parts.append(f"@type:{{{asset_type}}}")
        if manufacturer:
            search_parts.append(f"@manufacturer:{{{manufacturer}}}")
        if status:
            search_parts.append(f"@status:{{{status}}}")
        if region:
            search_parts.append(f"@region:{{{region}}}")
        if team:
            search_parts.append(f"@team:{{{team}}}")

        # Combine search parts
        if search_parts:
            search_query = " ".join(search_parts)
        else:
            search_query = "*"

        # Log the search command
        command_monitor.log_command('FT.SEARCH', f'idx:assets {search_query}', context='search')

        # Execute search
        search_result = redis_client.execute_command(
            'FT.SEARCH', 'idx:assets', search_query,
            'LIMIT', offset, limit,
            'RETURN', '12',
            'id', 'name', 'type', 'manufacturer', 'model', 'status',
            'zone', 'region', 'temperature', 'pressure', 'flow_rate', 'team'
        )

        # Parse results
        total_results = search_result[0] if search_result else 0
        assets = []

        # Process search results (skip total count, then process pairs of key-values)
        for i in range(1, len(search_result), 2):
            asset_key = search_result[i]
            asset_fields = search_result[i + 1] if i + 1 < len(search_result) else []

            # Convert field list to dictionary
            asset_data = {}
            for j in range(0, len(asset_fields), 2):
                if j + 1 < len(asset_fields):
                    field_name = asset_fields[j]
                    field_value = asset_fields[j + 1]
                    asset_data[field_name] = field_value

            if asset_data:
                assets.append(asset_data)

        return jsonify({
            'success': True,
            'total': total_results,
            'count': len(assets),
            'assets': assets,
            'query': search_query,
            'filters': {
                'type': asset_type,
                'manufacturer': manufacturer,
                'status': status,
                'region': region,
                'team': team
            }
        })

    except Exception as e:
        logger.error(f"Error searching assets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search/suggestions')
def get_search_suggestions():
    """Get autocomplete suggestions for search fields"""
    try:
        field = request.args.get('field', 'type')

        # Log the command
        command_monitor.log_command('FT.TAGVALS', f'idx:assets {field}', context='search')

        # Get tag values for the specified field
        if field in ['type', 'manufacturer', 'status', 'region', 'team']:
            suggestions = redis_client.execute_command('FT.TAGVALS', 'idx:assets', field)
            return jsonify({
                'success': True,
                'field': field,
                'suggestions': suggestions
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Field {field} is not available for suggestions'
            }), 400

    except Exception as e:
        logger.error(f"Error getting search suggestions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# REDIS COMMAND MONITORING ENDPOINTS
# ============================================================================

@app.route('/api/redis/commands', methods=['GET'])
def get_redis_commands():
    """Get recent Redis commands for monitoring"""
    try:
        limit = int(request.args.get('limit', 50))
        context = request.args.get('context')  # 'dashboard' or 'session'
        commands = command_monitor.get_recent_commands(limit, context)
        return jsonify({
            'success': True,
            'commands': commands,
            'count': len(commands),
            'context': context
        })
    except Exception as e:
        logger.error(f"Error getting Redis commands: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/redis/commands/clear', methods=['POST'])
def clear_redis_commands():
    """Clear Redis command history"""
    try:
        context = request.json.get('context') if request.json else None
        command_monitor.clear_command_history(context)
        return jsonify({
            'success': True,
            'message': f'Command history cleared for context: {context or "all"}'
        })
    except Exception as e:
        logger.error(f"Error clearing Redis commands: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/redis/stats', methods=['GET'])
def get_redis_stats():
    """Get Redis command statistics"""
    try:
        context = request.args.get('context')  # 'dashboard' or 'session'
        stats = command_monitor.get_command_stats(context)

        return jsonify({
            'success': True,
            'stats': stats,
            'context': context
        })
    except Exception as e:
        logger.error(f"Error getting Redis stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('FLASK_RUN_PORT', '5001'))  # Use port 5001 by default to avoid conflicts
    app.run(host='0.0.0.0', port=port, debug=True)
