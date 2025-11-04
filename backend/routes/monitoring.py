"""
Monitoring Routes - Redis command monitoring and statistics
Handles Redis command logging and performance metrics
"""

from flask import Blueprint, jsonify, request
import logging

logger = logging.getLogger(__name__)

# Create blueprint
monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/api')

# These will be injected by app.py
command_monitor = None

def init_monitoring(monitor):
    """Initialize monitoring blueprint with command monitor"""
    global command_monitor
    command_monitor = monitor


@monitoring_bp.route('/redis/commands', methods=['GET'])
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


@monitoring_bp.route('/redis/commands/clear', methods=['POST'])
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


@monitoring_bp.route('/redis/stats', methods=['GET'])
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

