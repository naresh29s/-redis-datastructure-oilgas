"""
Dashboard Routes - Asset tracking and KPIs
Handles geospatial asset queries and dashboard metrics
"""

from flask import Blueprint, jsonify, request
import json
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api')

# These will be injected by app.py
redis_client = None
command_monitor = None

def init_dashboard(redis, monitor):
    """Initialize dashboard blueprint with Redis client and monitor"""
    global redis_client, command_monitor
    redis_client = redis
    command_monitor = monitor


@dashboard_bp.route('/assets', methods=['GET'])
def get_assets():
    """Get all field assets with their locations - OPTIMIZED with pipelining"""
    try:
        start_time = time.time()
        
        # Get all assets from geospatial index
        command_monitor.log_command('ZRANGE', 'assets:locations', context='dashboard')
        assets = redis_client.zrange('assets:locations', 0, -1, withscores=False)
        
        if not assets:
            return jsonify({
                'success': True,
                'assets': [],
                'count': 0
            })
        
        # OPTIMIZATION: Use Redis pipeline to batch all commands
        # This reduces network round-trips from N to 1
        pipe = redis_client.pipeline()
        
        # Queue all GEOPOS commands in the pipeline
        for asset_id in assets:
            pipe.geopos('assets:locations', asset_id)
        
        # Queue all JSON.GET commands in the pipeline
        for asset_id in assets:
            pipe.execute_command('JSON.GET', f'asset:{asset_id}')
        
        # Execute all commands at once (single network round-trip)
        command_monitor.log_command('PIPELINE', f'{len(assets)*2} commands', context='dashboard')
        results = pipe.execute()
        
        # Split results into positions and JSON documents
        positions = results[:len(assets)]
        json_docs = results[len(assets):]
        
        # Build asset data from pipelined results
        asset_data = []
        for i, asset_id in enumerate(assets):
            position = positions[i]
            asset_json = json_docs[i]
            
            if position and position[0] and asset_json:
                lon, lat = position[0]
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
        
        elapsed_time = time.time() - start_time
        logger.info(f"✅ Loaded {len(asset_data)} assets in {elapsed_time:.3f}s (optimized with pipelining)")
        
        return jsonify({
            'success': True,
            'assets': asset_data,
            'count': len(asset_data)
        })
    except Exception as e:
        logger.error(f"Error getting assets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/assets/<asset_id>', methods=['GET'])
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
            return jsonify({'success': False, 'error': 'Asset details not found'}), 404
        
        asset_doc = json.loads(asset_json)
        asset_info = asset_doc.get('asset', {})
        
        # Build complete asset information
        asset_details = {
            'id': asset_id,
            'name': asset_info.get('name', asset_id),
            'type': asset_info.get('type', 'unknown'),
            'status': asset_info.get('status', {}),
            'location': {
                'latitude': lat,
                'longitude': lon,
                'field': asset_info.get('location', {}).get('field', 'Unknown')
            },
            'metrics': asset_info.get('metrics', {}),
            'model': asset_info.get('model', {}),
            'last_update': asset_info.get('status', {}).get('last_update', datetime.now().isoformat())
        }
        
        return jsonify({
            'success': True,
            'asset': asset_details
        })
    except Exception as e:
        logger.error(f"Error getting asset details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/assets/nearby', methods=['GET'])
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


@dashboard_bp.route('/assets/<asset_id>/update', methods=['POST'])
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


@dashboard_bp.route('/dashboard/kpis', methods=['GET'])
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


@dashboard_bp.route('/assets/<asset_id>/kpis', methods=['GET'])
def get_asset_kpis(asset_id):
    """Get KPIs specific to an asset"""
    try:
        import random

        # Get asset details using RedisJSON
        command_monitor.log_command('JSON.GET', f'asset:{asset_id}', context='dashboard')
        asset_json = redis_client.execute_command('JSON.GET', f'asset:{asset_id}')

        if not asset_json:
            return jsonify({'success': False, 'error': 'Asset not found'}), 404

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

