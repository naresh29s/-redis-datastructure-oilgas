#!/usr/bin/env python3
"""
Oil & Gas Field Data Simulator
Generates realistic field operations data for Redis Enterprise demo

Simulates:
1. Field assets (drilling rigs, service vehicles, equipment)
2. IoT sensor data from drilling sites
3. Operational metrics and alerts
"""

import redis
import json
import time
import random
import math
import threading
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
except Exception as e:
    logger.error(f"❌ Failed to connect to Redis Cloud: {e}")
    exit(1)

# ============================================================================
# FIELD ASSET SIMULATION
# ============================================================================

class AssetSimulator:
    def __init__(self):
        # Texas oil field coordinates (Permian Basin area)
        self.base_lat = 31.8457
        self.base_lon = -102.3676
        self.field_radius = 0.5  # degrees (~50km)
        
        self.asset_types = [
            'drilling_rig', 'service_truck', 'pump_jack', 'compressor',
            'separator', 'tank_battery', 'pipeline_valve', 'wellhead'
        ]
        
        self.assets = {}
        self.initialize_assets()
    
    def initialize_assets(self):
        """Initialize field assets with comprehensive JSON data using RedisJSON"""
        import json
        from datetime import datetime, timedelta

        # Asset configurations with enhanced data and diverse types - 14 assets distributed across 100-mile radius
        # Base location: West Texas Permian Basin (32.02°N, -102.20°W)
        # Geographic distribution: ~100-mile radius (approximately 1.5 degrees lat/lon)
        asset_configs = [
            # Pump Jacks (3 assets) - Primary production equipment
            {'id': 'PUMP-001', 'name': 'Pump Jack Well-001', 'type': 'pump_jack', 'lat': 32.45, 'lon': -101.85, 'manufacturer': 'Schlumberger', 'model': 'PJ-4500X'},
            {'id': 'PUMP-002', 'name': 'Pump Jack Well-002', 'type': 'pump_jack', 'lat': 31.78, 'lon': -102.67, 'manufacturer': 'Halliburton', 'model': 'PJ-3800H'},
            {'id': 'PUMP-003', 'name': 'Pump Jack Well-003', 'type': 'pump_jack', 'lat': 32.89, 'lon': -102.34, 'manufacturer': 'Baker Hughes', 'model': 'BH-5200'},

            # Wells (3 assets) - Various well types
            {'id': 'WELL-001', 'name': 'Production Well Alpha', 'type': 'production_well', 'lat': 31.56, 'lon': -101.92, 'manufacturer': 'Schlumberger', 'model': 'WH-7500'},
            {'id': 'WELL-002', 'name': 'Injection Well Beta', 'type': 'injection_well', 'lat': 32.67, 'lon': -103.12, 'manufacturer': 'Halliburton', 'model': 'IW-6100'},
            {'id': 'WELL-003', 'name': 'Monitoring Well Gamma', 'type': 'monitoring_well', 'lat': 33.01, 'lon': -101.78, 'manufacturer': 'Baker Hughes', 'model': 'MW-5500'},

            # Drilling Rigs (2 assets) - Mobile drilling equipment
            {'id': 'RIG-ALPHA', 'name': 'Drilling Rig Alpha', 'type': 'drilling_rig', 'lat': 31.89, 'lon': -103.45, 'manufacturer': 'NOV', 'model': 'DR-9500'},
            {'id': 'RIG-BETA', 'name': 'Drilling Rig Beta', 'type': 'drilling_rig', 'lat': 32.34, 'lon': -101.56, 'manufacturer': 'Schlumberger', 'model': 'DR-8800'},

            # Compressors (2 assets) - Gas compression stations
            {'id': 'COMP-001', 'name': 'Gas Compressor Station 001', 'type': 'compressor', 'lat': 33.12, 'lon': -102.89, 'manufacturer': 'Weatherford', 'model': 'WF-C7500'},
            {'id': 'COMP-002', 'name': 'Gas Compressor Station 002', 'type': 'compressor', 'lat': 31.67, 'lon': -102.23, 'manufacturer': 'NOV', 'model': 'NOV-C6200'},

            # Separators (2 assets) - Oil-gas-water separation
            {'id': 'SEP-001', 'name': 'Oil-Gas Separator 001', 'type': 'separator', 'lat': 32.78, 'lon': -101.67, 'manufacturer': 'Halliburton', 'model': 'HAL-S4800'},
            {'id': 'SEP-002', 'name': 'Three-Phase Separator 002', 'type': 'separator', 'lat': 31.45, 'lon': -103.01, 'manufacturer': 'Baker Hughes', 'model': 'BH-S5500'},

            # Tank Battery (1 asset) - Storage facility
            {'id': 'TANK-001', 'name': 'Storage Tank Battery 001', 'type': 'tank_battery', 'lat': 32.56, 'lon': -102.78, 'manufacturer': 'Schlumberger', 'model': 'SLB-TB12000'},

            # Service Truck (1 asset) - Mobile service equipment
            {'id': 'SVC-001', 'name': 'Wireline Service Truck 001', 'type': 'service_truck', 'lat': 32.12, 'lon': -102.45, 'manufacturer': 'Weatherford', 'model': 'WF-ST3500'}
        ]

        maintenance_teams = ['Ops Crew A', 'Ops Crew B', 'Ops Crew C', 'Maintenance Team Alpha', 'Field Service Team']
        contacts = [
            {'name': 'John Doe', 'email': 'john.doe@lumenenergy.com'},
            {'name': 'Sarah Johnson', 'email': 'sarah.johnson@lumenenergy.com'},
            {'name': 'Mike Wilson', 'email': 'mike.wilson@lumenenergy.com'},
            {'name': 'Lisa Chen', 'email': 'lisa.chen@lumenenergy.com'},
            {'name': 'David Rodriguez', 'email': 'david.rodriguez@lumenenergy.com'}
        ]

        for config in asset_configs:
            lat, lon = config['lat'], config['lon']

            # Generate realistic dates
            install_date = datetime.now() - timedelta(days=random.randint(365, 1095))  # 1-3 years ago
            last_service = datetime.now() - timedelta(days=random.randint(1, 90))  # 1-90 days ago
            next_service = last_service + timedelta(days=random.randint(30, 120))  # 30-120 days from last service
            last_fault = datetime.now() - timedelta(days=random.randint(1, 30))  # 1-30 days ago

            # Create comprehensive asset JSON document
            asset_json = {
                "asset": {
                    "id": config['id'],
                    "name": config['name'],
                    "type": config['type'],
                    "group": "West Texas Field A",
                    "model": {
                        "manufacturer": config['manufacturer'],
                        "model_number": config['model'],
                        "serial_number": f"SN-{random.randint(10000000, 99999999)}",
                        "install_date": install_date.strftime("%Y-%m-%d")
                    },
                    "status": {
                        "state": random.choice(['active', 'maintenance', 'standby', 'offline']),
                        "last_update": datetime.now().isoformat(),
                        "health_score": random.randint(85, 99),
                        "runtime_hours": random.randint(1000, 8000)
                    },
                    "location": {
                        "latitude": lat,
                        "longitude": lon,
                        "elevation_ft": random.randint(2800, 3200),
                        "zone": f"Permian Basin Zone {random.randint(1, 6)}",
                        "region_code": f"TX-PB{random.randint(1, 6)}"
                    },
                    "metrics": self._generate_asset_metrics(config['type']),
                    "maintenance": {
                        "last_service_date": last_service.strftime("%Y-%m-%d"),
                        "next_service_due": next_service.strftime("%Y-%m-%d"),
                        "total_downtime_hours": random.randint(50, 300),
                        "last_fault": {
                            "code": f"E-{random.randint(100, 999)}",
                            "timestamp": last_fault.isoformat() + "Z"
                        },
                        "maintenance_team": random.choice(maintenance_teams),
                        "contact": random.choice(contacts)
                    },
                    "connectivity": {
                        "sensor_id": f"SENSOR-{config['id'].replace('-', '')}",
                        "communication_status": random.choice(['online', 'online', 'online', 'degraded']),  # Mostly online
                        "data_source": random.choice(['Modbus/TCP', 'OPC-UA', 'MQTT', 'LoRaWAN']),
                        "data_frequency": random.choice(['1s', '5s', '10s', '30s']),
                        "last_data_received": (datetime.now() - timedelta(seconds=random.randint(1, 300))).isoformat() + "Z"
                    },
                    "analytics": {
                        "avg_uptime_pct": round(random.uniform(95.0, 99.5), 1),
                        "maintenance_cost_to_date": round(random.uniform(5000, 25000), 2)
                    },
                    "metadata": {
                        "created_by": "system",
                        "created_at": install_date.isoformat() + "Z",
                        "updated_by": "Naresh Sanodariya",
                        "version": f"v1.{random.randint(1, 5)}.{random.randint(0, 9)}"
                    }
                }
            }

            # Store in memory for simulator use (simplified version)
            metrics = asset_json['asset']['metrics']
            self.assets[config['id']] = {
                'id': config['id'],
                'name': config['name'],
                'type': config['type'],
                'status': asset_json['asset']['status']['state'],
                'latitude': str(lat),
                'longitude': str(lon),
                'location': config['id'],  # For sensor data correlation
                'temperature': metrics['temperature_c'],
                'pressure': metrics['pressure_psi'],
                'flow_rate': metrics.get('flow_rate_bbl_per_hr', metrics.get('flow_rate_mmscfd', 0)),
                'vibration': metrics['vibration_mm_s'],
                'last_update': datetime.now().isoformat()
            }

            # Store in Redis using RedisJSON
            redis_client.execute_command('JSON.SET', f'asset:{config["id"]}', '.', json.dumps(asset_json))

            # Maintain geospatial index for map display
            redis_client.geoadd('assets:locations', (lon, lat, config['id']))

        logger.info(f"✅ Initialized {len(self.assets)} field assets with comprehensive JSON data")

    def _generate_asset_metrics(self, asset_type):
        """Generate asset-specific metrics based on equipment type"""
        if asset_type == 'pump_jack':
            return {
                "temperature_c": round(random.uniform(65, 95), 1),
                "pressure_psi": round(random.uniform(200, 400), 1),
                "flow_rate_bbl_per_hr": round(random.uniform(10, 50), 1),
                "vibration_mm_s": round(random.uniform(0.5, 3.0), 2),
                "power_kwh": round(random.uniform(3.0, 8.0), 1),
                "stroke_rate_spm": round(random.uniform(8, 15), 1)
            }
        elif asset_type in ['production_well', 'injection_well', 'monitoring_well']:
            return {
                "temperature_c": round(random.uniform(70, 110), 1),
                "pressure_psi": round(random.uniform(1500, 3500), 1),
                "flow_rate_bbl_per_hr": round(random.uniform(5, 80), 1),
                "vibration_mm_s": round(random.uniform(0.1, 1.5), 2),
                "power_kwh": round(random.uniform(1.0, 4.0), 1),
                "water_cut_pct": round(random.uniform(15, 45), 1)
            }
        elif asset_type == 'drilling_rig':
            return {
                "temperature_c": round(random.uniform(75, 105), 1),
                "pressure_psi": round(random.uniform(3000, 5000), 1),
                "flow_rate_bbl_per_hr": round(random.uniform(100, 300), 1),
                "vibration_mm_s": round(random.uniform(2.0, 8.0), 2),
                "power_kwh": round(random.uniform(50, 150), 1),
                "drilling_depth_ft": round(random.uniform(8000, 12000), 0),
                "drilling_rate_ft_hr": round(random.uniform(15, 45), 1)
            }
        elif asset_type == 'compressor':
            return {
                "temperature_c": round(random.uniform(80, 120), 1),
                "pressure_psi": round(random.uniform(500, 1200), 1),
                "flow_rate_mmscfd": round(random.uniform(5, 25), 1),
                "vibration_mm_s": round(random.uniform(1.5, 4.0), 2),
                "power_kwh": round(random.uniform(25, 75), 1),
                "compression_ratio": round(random.uniform(3.5, 6.0), 1),
                "efficiency_pct": round(random.uniform(80, 92), 1)
            }
        elif asset_type == 'separator':
            return {
                "temperature_c": round(random.uniform(70, 100), 1),
                "pressure_psi": round(random.uniform(100, 500), 1),
                "flow_rate_bbl_per_hr": round(random.uniform(50, 200), 1),
                "vibration_mm_s": round(random.uniform(0.2, 2.0), 2),
                "power_kwh": round(random.uniform(5, 20), 1),
                "separation_efficiency_pct": round(random.uniform(85, 98), 1),
                "water_content_pct": round(random.uniform(10, 30), 1)
            }
        elif asset_type == 'tank_battery':
            return {
                "temperature_c": round(random.uniform(60, 85), 1),
                "pressure_psi": round(random.uniform(0, 50), 1),
                "flow_rate_bbl_per_hr": round(random.uniform(20, 100), 1),
                "vibration_mm_s": round(random.uniform(0.1, 1.0), 2),
                "power_kwh": round(random.uniform(2, 10), 1),
                "tank_level_pct": round(random.uniform(25, 85), 1),
                "capacity_bbl": round(random.uniform(5000, 20000), 0)
            }
        elif asset_type == 'service_truck':
            return {
                "temperature_c": round(random.uniform(70, 95), 1),
                "pressure_psi": round(random.uniform(100, 300), 1),
                "flow_rate_bbl_per_hr": round(random.uniform(5, 30), 1),
                "vibration_mm_s": round(random.uniform(1.0, 5.0), 2),
                "power_kwh": round(random.uniform(10, 40), 1),
                "fuel_level_pct": round(random.uniform(30, 90), 1),
                "operating_hours": round(random.uniform(100, 2000), 0)
            }
        else:
            # Default metrics for unknown asset types
            return {
                "temperature_c": round(random.uniform(65, 95), 1),
                "pressure_psi": round(random.uniform(200, 400), 1),
                "flow_rate_bbl_per_hr": round(random.uniform(10, 50), 1),
                "vibration_mm_s": round(random.uniform(0.5, 3.0), 2),
                "power_kwh": round(random.uniform(2.0, 8.0), 1)
            }
    
    def simulate_asset_movement(self):
        """Simulate asset movement (mainly service vehicles)"""
        while True:
            try:
                # Only move service vehicles and some equipment
                mobile_assets = [aid for aid, asset in self.assets.items() 
                               if asset['type'] in ['service_truck', 'drilling_rig']]
                
                for asset_id in mobile_assets:
                    asset = self.assets[asset_id]
                    
                    # Small random movement
                    lat_delta = random.uniform(-0.01, 0.01)  # ~1km
                    lon_delta = random.uniform(-0.01, 0.01)
                    
                    new_lat = asset['latitude'] + lat_delta
                    new_lon = asset['longitude'] + lon_delta
                    
                    # Update asset location
                    asset['latitude'] = new_lat
                    asset['longitude'] = new_lon
                    asset['last_update'] = datetime.now().isoformat()
                    
                    # Update in Redis
                    redis_client.geoadd('assets:locations', (new_lon, new_lat, asset_id))
                    redis_client.hset(f'asset:{asset_id}', mapping=asset)
                
                time.sleep(30)  # Update every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in asset movement simulation: {e}")
                time.sleep(5)

# ============================================================================
# SENSOR DATA SIMULATION
# ============================================================================

class SensorSimulator:
    def __init__(self):
        self.sensors = {
            'TEMP-001': {'type': 'temperature', 'location': 'RIG-ALPHA', 'base_value': 85},
            'TEMP-002': {'type': 'temperature', 'location': 'RIG-BRAVO', 'base_value': 78},
            'PRESS-001': {'type': 'pressure', 'location': 'WELL-001', 'base_value': 2500},
            'PRESS-002': {'type': 'pressure', 'location': 'WELL-002', 'base_value': 2800},
            'FLOW-001': {'type': 'flow_rate', 'location': 'PUMP-001', 'base_value': 150},
            'FLOW-002': {'type': 'flow_rate', 'location': 'PUMP-002', 'base_value': 180},
            'VIB-001': {'type': 'vibration', 'location': 'COMP-001', 'base_value': 2.5},
            'VIB-002': {'type': 'vibration', 'location': 'SEP-001', 'base_value': 1.8},
        }
    
    def generate_sensor_reading(self, sensor_id, sensor_config):
        """Generate realistic sensor reading"""
        base_value = sensor_config['base_value']
        sensor_type = sensor_config['type']
        
        # Add realistic variations
        if sensor_type == 'temperature':
            # Temperature in Fahrenheit, varies ±10°F
            value = base_value + random.uniform(-10, 10)
        elif sensor_type == 'pressure':
            # Pressure in PSI, varies ±200 PSI
            value = base_value + random.uniform(-200, 200)
        elif sensor_type == 'flow_rate':
            # Flow rate in barrels/day, varies ±20
            value = max(0, base_value + random.uniform(-20, 20))
        elif sensor_type == 'vibration':
            # Vibration in mm/s, varies ±0.5
            value = max(0, base_value + random.uniform(-0.5, 0.5))
        else:
            value = base_value + random.uniform(-base_value*0.1, base_value*0.1)
        
        return round(value, 2)
    
    def simulate_sensor_data(self):
        """Continuously generate sensor data"""
        while True:
            try:
                for sensor_id, config in self.sensors.items():
                    # Generate reading
                    reading = {
                        'sensor_id': sensor_id,
                        'timestamp': str(time.time()),
                        'temperature': str(self.generate_sensor_reading(sensor_id, config) if config['type'] == 'temperature' else 0),
                        'pressure': str(self.generate_sensor_reading(sensor_id, config) if config['type'] == 'pressure' else 0),
                        'flow_rate': str(self.generate_sensor_reading(sensor_id, config) if config['type'] == 'flow_rate' else 0),
                        'vibration': str(self.generate_sensor_reading(sensor_id, config) if config['type'] == 'vibration' else 0),
                        'location': config['location']
                    }
                    
                    # Add to Redis Stream
                    stream_key = f'sensors:{sensor_id}'
                    redis_client.xadd(stream_key, reading)
                    
                    # Update latest reading
                    redis_client.hset(f'sensor:latest:{sensor_id}', mapping=reading)
                    
                    # Check for alerts
                    self.check_alerts(sensor_id, reading)

                # Generate system alerts occasionally
                self.generate_system_alerts()

                time.sleep(5)  # Generate data every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in sensor simulation: {e}")
                time.sleep(5)
    
    def check_alerts(self, sensor_id, reading):
        """Check for alert conditions"""
        alerts = []

        # Convert string values back to float for comparison
        temp = float(reading['temperature'])
        pressure = float(reading['pressure'])
        vibration = float(reading['vibration'])
        flow_rate = float(reading['flow_rate']) if reading['flow_rate'] != '0' else None

        # Get asset location for this sensor
        location = reading.get('location', 'UNKNOWN')

        # Temperature alerts
        if temp > 95:  # Lowered threshold to generate more alerts
            severity = 'critical' if temp > 110 else ('high' if temp > 105 else 'warning')
            alerts.append({
                'id': f'TEMP_HIGH_{sensor_id}_{int(time.time())}',
                'type': 'temperature_high',
                'message': f'High Temperature Detected',
                'details': f'{temp:.1f}°F exceeds normal operating range',
                'location': location,
                'sensor_id': sensor_id,
                'severity': severity,
                'timestamp': time.time()
            })

        # Pressure alerts
        if pressure > 2800:  # Lowered threshold to generate more alerts
            severity = 'critical' if pressure > 3200 else ('high' if pressure > 3000 else 'warning')
            alerts.append({
                'id': f'PRESS_HIGH_{sensor_id}_{int(time.time())}',
                'type': 'pressure_high',
                'message': f'Pressure Threshold Exceeded',
                'details': f'{pressure:.0f} PSI above safe operating limits',
                'location': location,
                'sensor_id': sensor_id,
                'severity': severity,
                'timestamp': time.time()
            })

        # Vibration alerts
        if vibration > 2.5:  # New vibration alert
            severity = 'critical' if vibration > 4.0 else ('high' if vibration > 3.0 else 'warning')
            alerts.append({
                'id': f'VIB_HIGH_{sensor_id}_{int(time.time())}',
                'type': 'vibration_high',
                'message': f'Excessive Vibration Detected',
                'details': f'{vibration:.1f} mm/s indicates potential equipment issue',
                'location': location,
                'sensor_id': sensor_id,
                'severity': severity,
                'timestamp': time.time()
            })

        # Flow rate alerts (low flow) - only for flow sensors
        if flow_rate is not None and flow_rate < 15:  # New low flow alert
            severity = 'high' if flow_rate < 10 else 'warning'
            alerts.append({
                'id': f'FLOW_LOW_{sensor_id}_{int(time.time())}',
                'type': 'flow_low',
                'message': f'Low Flow Rate Alert',
                'details': f'{flow_rate:.1f} GPM below expected production levels',
                'location': location,
                'sensor_id': sensor_id,
                'severity': severity,
                'timestamp': time.time()
            })

        # Add alerts to Redis
        for alert in alerts:
            redis_client.zadd('alerts:active', {json.dumps(alert): alert['timestamp']})
            redis_client.incr('alerts:count')
            logger.info(f"Generated alert: {alert['message']} at {alert['location']}")

        # Clean up old alerts (keep only last 50)
        redis_client.zremrangebyrank('alerts:active', 0, -51)

    def generate_system_alerts(self):
        """Generate periodic system-level alerts"""
        try:
            # Generate system alerts every 30-60 seconds
            if random.random() < 0.3:  # 30% chance each cycle
                alert_types = [
                    {
                        'type': 'maintenance_due',
                        'message': 'Scheduled Maintenance Due',
                        'details': 'Preventive maintenance window approaching',
                        'severity': 'warning'
                    },
                    {
                        'type': 'communication_issue',
                        'message': 'Communication Timeout',
                        'details': 'Intermittent connection to remote sensors',
                        'severity': 'warning'
                    },
                    {
                        'type': 'production_anomaly',
                        'message': 'Production Rate Anomaly',
                        'details': 'Output variance detected across multiple wells',
                        'severity': 'high'
                    },
                    {
                        'type': 'weather_warning',
                        'message': 'Weather Advisory',
                        'details': 'High winds forecasted - secure equipment',
                        'severity': 'warning'
                    }
                ]

                alert_info = random.choice(alert_types)
                location = random.choice(['FIELD-NORTH', 'FIELD-SOUTH', 'FIELD-CENTRAL', 'OPERATIONS-HQ'])

                alert = {
                    'id': f'SYS_{alert_info["type"].upper()}_{int(time.time())}',
                    'type': alert_info['type'],
                    'message': alert_info['message'],
                    'details': alert_info['details'],
                    'location': location,
                    'sensor_id': 'SYSTEM',
                    'severity': alert_info['severity'],
                    'timestamp': time.time()
                }

                redis_client.zadd('alerts:active', {json.dumps(alert): alert['timestamp']})
                redis_client.incr('alerts:count')
                logger.info(f"Generated system alert: {alert['message']} at {alert['location']}")

        except Exception as e:
            logger.error(f"Error generating system alerts: {e}")

# ============================================================================
# DASHBOARD METRICS SIMULATION
# ============================================================================

class MetricsSimulator:
    def __init__(self):
        pass
    
    def update_dashboard_metrics(self):
        """Update dashboard KPIs"""
        while True:
            try:
                # Calculate metrics from sensor data
                sensor_keys = redis_client.keys('sensor:latest:*')
                
                total_temp = 0
                total_pressure = 0
                temp_count = 0
                pressure_count = 0
                
                for key in sensor_keys:
                    data = redis_client.hgetall(key)
                    if data.get('temperature'):
                        total_temp += float(data['temperature'])
                        temp_count += 1
                    if data.get('pressure'):
                        total_pressure += float(data['pressure'])
                        pressure_count += 1
                
                # Update averages
                if temp_count > 0:
                    redis_client.set('metrics:avg_temperature', round(total_temp / temp_count, 1))
                if pressure_count > 0:
                    redis_client.set('metrics:avg_pressure', round(total_pressure / pressure_count, 1))
                
                # Simulate production metrics
                redis_client.set('metrics:total_production', random.randint(8500, 9500))
                redis_client.set('system:uptime', int(time.time()))
                
                time.sleep(10)  # Update every 10 seconds
                
            except Exception as e:
                logger.error(f"Error updating metrics: {e}")
                time.sleep(10)

# ============================================================================
# MAIN SIMULATION CONTROLLER
# ============================================================================

def main():
    """Start all simulators"""
    logger.info("🚀 Starting Oil & Gas Field Data Simulator")
    
    try:
        # Test Redis connection
        redis_client.ping()
        logger.info("✅ Connected to Redis Enterprise")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        return
    
    # Initialize simulators
    asset_sim = AssetSimulator()
    sensor_sim = SensorSimulator()
    metrics_sim = MetricsSimulator()
    
    # Start simulation threads
    threads = [
        threading.Thread(target=asset_sim.simulate_asset_movement, daemon=True),
        threading.Thread(target=sensor_sim.simulate_sensor_data, daemon=True),
        threading.Thread(target=metrics_sim.update_dashboard_metrics, daemon=True)
    ]
    
    for thread in threads:
        thread.start()
    
    logger.info("✅ All simulators started")
    logger.info("📊 Generating realistic oil & gas field data...")
    logger.info("🔄 Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Stopping simulators...")

if __name__ == '__main__':
    main()
