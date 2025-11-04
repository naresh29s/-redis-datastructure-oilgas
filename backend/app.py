#!/usr/bin/env python3
"""
Oil & Gas Field Operations Demo - Backend API
Redis Enterprise Demo for Halliburton

Features:
1. Geospatial Asset Tracking
2. Edge-to-Core Streaming with Redis Streams
3. Real-Time Operational Dashboard

REFACTORED: Routes organized into separate blueprint modules
"""

from flask import Flask, jsonify, redirect
from flask_cors import CORS
import redis
import json
import time
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


# ============================================================================
# REDIS CONNECTION SETUP
# ============================================================================

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
# IMPORT AND REGISTER BLUEPRINTS
# ============================================================================

from routes.dashboard import dashboard_bp, init_dashboard
from routes.sensors import sensors_bp, init_sensors
from routes.alerts import alerts_bp, init_alerts
from routes.search import search_bp, init_search
from routes.sessions import sessions_bp, init_sessions
from routes.monitoring import monitoring_bp, init_monitoring

# Initialize blueprints with dependencies
init_dashboard(redis_client, command_monitor)
init_sensors(redis_client, command_monitor)
init_alerts(redis_client, command_monitor)
init_search(redis_client, command_monitor)
init_sessions(redis_client, command_monitor, session_manager)
init_monitoring(command_monitor)

# Register blueprints
app.register_blueprint(dashboard_bp)
app.register_blueprint(sensors_bp)
app.register_blueprint(alerts_bp)
app.register_blueprint(search_bp)
app.register_blueprint(sessions_bp)
app.register_blueprint(monitoring_bp)

logger.info("✅ Registered all route blueprints")


# ============================================================================
# HEALTH CHECK AND STATIC FILE SERVING
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
    """Redirect to dashboard"""
    return redirect('/dashboard.html')


@app.route('/<path:filename>', methods=['GET'])
def serve_frontend(filename):
    """Serve frontend files (HTML, CSS, JS) - but not API routes"""
    # Skip API routes - let them be handled by their specific handlers
    if filename.startswith('api/'):
        return jsonify({'error': 'API endpoint not found'}), 404

    try:
        frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
        file_path = os.path.join(frontend_dir, filename)

        # Security check: ensure the file is within the frontend directory
        if not os.path.abspath(file_path).startswith(os.path.abspath(frontend_dir)):
            return jsonify({'error': 'Invalid file path'}), 403

        if os.path.exists(file_path) and os.path.isfile(file_path):
            # Determine content type based on file extension
            content_type = 'text/html'
            if filename.endswith('.css'):
                content_type = 'text/css'
            elif filename.endswith('.js'):
                content_type = 'application/javascript'
            elif filename.endswith('.json'):
                content_type = 'application/json'
            elif filename.endswith('.png'):
                content_type = 'image/png'
            elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
                content_type = 'image/jpeg'
            elif filename.endswith('.svg'):
                content_type = 'image/svg+xml'

            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read(), 200, {'Content-Type': content_type}
        else:
            # Frontend file not found
            return jsonify({
                'error': 'File not found',
                'file': filename,
                'note': 'Available pages: dashboard.html, sessions.html, search.html'
            }), 404
    except Exception as e:
        logger.error(f"Error serving frontend: {e}")
        return jsonify({'error': 'Failed to serve frontend', 'details': str(e)}), 500


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('FLASK_RUN_PORT', '5001'))  # Use port 5001 by default to avoid conflicts
    app.run(host='0.0.0.0', port=port, debug=True)

