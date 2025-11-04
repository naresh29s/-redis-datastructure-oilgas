"""
Search Routes - RediSearch full-text search and filtering
Handles asset search with filters and autocomplete suggestions
"""

from flask import Blueprint, jsonify, request
import logging

logger = logging.getLogger(__name__)

# Create blueprint
search_bp = Blueprint('search', __name__, url_prefix='/api')

# These will be injected by app.py
redis_client = None
command_monitor = None

def init_search(redis, monitor):
    """Initialize search blueprint with Redis client and monitor"""
    global redis_client, command_monitor
    redis_client = redis
    command_monitor = monitor


@search_bp.route('/search/assets')
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


@search_bp.route('/search/suggestions')
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

