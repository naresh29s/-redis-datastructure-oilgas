// Dashboard-specific JavaScript

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('🛢️ Dashboard: DOM Content Loaded');

    // Wait for Leaflet to be fully loaded before initializing map
    if (typeof L !== 'undefined') {
        console.log('✅ Leaflet loaded, initializing map...');
        initializeMap();
    } else {
        console.warn('⚠️ Leaflet not loaded yet, waiting...');
        // Wait for Leaflet to load
        let attempts = 0;
        const checkLeaflet = setInterval(() => {
            attempts++;
            if (typeof L !== 'undefined') {
                console.log('✅ Leaflet loaded after waiting, initializing map...');
                clearInterval(checkLeaflet);
                initializeMap();
            } else if (attempts > 20) {
                console.error('❌ Leaflet failed to load after 10 seconds');
                clearInterval(checkLeaflet);
                document.getElementById('map').innerHTML = '<div style="color: red; padding: 20px;">Error: Map library failed to load. Please refresh the page.</div>';
            }
        }, 500);
    }

    // Start data updates immediately (they don't depend on map)
    startDataUpdates();

    // Check if an asset was selected from search page
    const selectedAssetId = sessionStorage.getItem('selectedAssetId');
    if (selectedAssetId) {
        // Wait for assets to load, then select the asset
        setTimeout(() => {
            selectAsset(selectedAssetId);
            sessionStorage.removeItem('selectedAssetId');
        }, 2000);
    }

    console.log('🛢️ Dashboard Initialized');
    console.log(`📡 API Base URL: ${API_BASE_URL}`);
});

// ============================================================================
// DASHBOARD DATA UPDATES
// ============================================================================

function startDataUpdates() {
    // Update data every 5 seconds
    updateDashboardData();
    setInterval(updateDashboardData, 5000);

    // Update assets every 30 seconds
    setInterval(loadAssets, 30000);

    // Update Redis commands every 2 seconds
    updateDashboardCommands();
    setInterval(updateDashboardCommands, 2000);
}

async function updateDashboardData() {
    await Promise.all([
        updateKPIs(),
        updateSensorData(),
        updateAlerts()
    ]);
}

async function updateKPIs() {
    try {
        let endpoint = `${API_BASE_URL}/api/dashboard/kpis`;
        if (selectedAsset) {
            endpoint = `${API_BASE_URL}/api/assets/${selectedAsset}/kpis`;
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

        const response = await fetch(endpoint, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            if (selectedAsset && data.kpis) {
                // Display asset-specific KPIs
                displayAssetKPIs(data.kpis);
            } else {
                // Display overall KPIs
                const kpis = data.kpis;
                document.getElementById('total-assets').textContent = kpis.total_assets || 0;
                document.getElementById('active-sensors').textContent = kpis.active_sensors || 0;
                document.getElementById('avg-temperature').textContent =
                    kpis.avg_temperature ? `${kpis.avg_temperature}°F` : '--°F';
                document.getElementById('avg-pressure').textContent =
                    kpis.avg_pressure ? `${Math.round(kpis.avg_pressure)}` : '--';
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.error('KPI request timed out');
        } else {
            console.error('Error updating KPIs:', error);
        }
        // Don't show error to user, just log it
    }
}

function displayAssetKPIs(kpis) {
    // Update KPI display for selected asset
    const kpiContainer = document.querySelector('.kpi-grid');
    if (!kpiContainer) return;

    let kpiHTML = '';

    // Helper function to format KPI values with proper decimal places
    function formatKPIValue(value, unit = '') {
        if (typeof value === 'number') {
            return parseFloat(value.toFixed(2)) + unit;
        }
        return value + unit;
    }

    // Display different KPIs based on asset type
    if (kpis.asset_type === 'drilling_rig') {
        kpiHTML = `
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.drilling_depth)}</div>
                <div class="kpi-label">Drilling Depth (ft)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.drilling_rate)}</div>
                <div class="kpi-label">Rate (ft/hr)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.efficiency, '%')}</div>
                <div class="kpi-label">Efficiency</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.uptime_hours)}</div>
                <div class="kpi-label">Uptime (hrs)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.mud_weight)}</div>
                <div class="kpi-label">Mud Weight (ppg)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.rotary_speed)}</div>
                <div class="kpi-label">Rotary Speed (rpm)</div>
            </div>
        `;
    } else if (kpis.asset_type === 'pump_jack' || kpis.asset_type === 'wellhead') {
        kpiHTML = `
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.production_rate)}</div>
                <div class="kpi-label">Production (bpd)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.water_cut, '%')}</div>
                <div class="kpi-label">Water Cut</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.pump_efficiency, '%')}</div>
                <div class="kpi-label">Efficiency</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.runtime_hours)}</div>
                <div class="kpi-label">Runtime (hrs)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.pressure_avg)}</div>
                <div class="kpi-label">Avg Pressure (psi)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.temperature_avg)}</div>
                <div class="kpi-label">Avg Temp (°F)</div>
            </div>
        `;
    } else if (kpis.asset_type === 'compressor') {
        kpiHTML = `
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.throughput)}</div>
                <div class="kpi-label">Throughput (MMSCFD)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.efficiency, '%')}</div>
                <div class="kpi-label">Efficiency</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.vibration_level)}</div>
                <div class="kpi-label">Vibration (mm/s)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.runtime_hours)}</div>
                <div class="kpi-label">Runtime (hrs)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.pressure_ratio)}</div>
                <div class="kpi-label">Pressure Ratio</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.temperature_avg)}</div>
                <div class="kpi-label">Avg Temp (°F)</div>
            </div>
        `;
    } else if (kpis.asset_type === 'separator' || kpis.asset_type === 'tank_battery') {
        kpiHTML = `
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.throughput)}</div>
                <div class="kpi-label">Throughput (bpd)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.oil_volume)}</div>
                <div class="kpi-label">Oil Volume (bbl)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.water_volume)}</div>
                <div class="kpi-label">Water Volume (bbl)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.gas_volume)}</div>
                <div class="kpi-label">Gas Volume (MCF)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.pressure_avg)}</div>
                <div class="kpi-label">Avg Pressure (psi)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.temperature_avg)}</div>
                <div class="kpi-label">Avg Temp (°F)</div>
            </div>
        `;
    } else if (kpis.asset_type === 'service_truck') {
        kpiHTML = `
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.distance_traveled)}</div>
                <div class="kpi-label">Distance (mi)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.fuel_level, '%')}</div>
                <div class="kpi-label">Fuel Level</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.speed)}</div>
                <div class="kpi-label">Speed (mph)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.engine_hours)}</div>
                <div class="kpi-label">Engine Hours</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${kpis.current_location || 'N/A'}</div>
                <div class="kpi-label">Location</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${kpis.next_service || 'N/A'}</div>
                <div class="kpi-label">Next Service</div>
            </div>
        `;
    } else {
        // Default KPIs for other asset types
        kpiHTML = `
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.temperature || 0)}</div>
                <div class="kpi-label">Temperature (°F)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.pressure || 0)}</div>
                <div class="kpi-label">Pressure (psi)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${formatKPIValue(kpis.flow_rate || 0)}</div>
                <div class="kpi-label">Flow Rate (bbl/hr)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">${kpis.status || 'Unknown'}</div>
                <div class="kpi-label">Status</div>
            </div>
        `;
    }

    kpiContainer.innerHTML = kpiHTML;
}

async function updateSensorData() {
    try {
        const startTime = performance.now();
        let endpoint = `${API_BASE_URL}/api/sensors/active`;
        if (selectedAsset) {
            endpoint = `${API_BASE_URL}/api/assets/${selectedAsset}/sensors`;
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);

        const response = await fetch(endpoint, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const fetchTime = performance.now() - startTime;

        if (data.success && data.sensors) {
            displaySensorData(data.sensors);
            console.log(`📊 Sensors updated (${data.sensors.length} sensors) in ${fetchTime.toFixed(0)}ms`);
        } else {
            // No sensors available, but not an error
            const sensorList = document.getElementById('sensor-list');
            if (sensorList) {
                sensorList.innerHTML = '<div class="loading">No sensor data available</div>';
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.error('❌ Sensor data request timed out');
        } else {
            console.error('❌ Error updating sensor data:', error);
        }
        // Only show error in console, not in UI - keep previous data or show loading
        const sensorList = document.getElementById('sensor-list');
        if (sensorList && sensorList.innerHTML.includes('Loading')) {
            sensorList.innerHTML = '<div class="loading">Connecting to sensors...</div>';
        }
    }
}

function displaySensorData(sensors) {
    const sensorList = document.getElementById('sensor-list');

    if (!sensors || sensors.length === 0) {
        sensorList.innerHTML = '<div class="loading">No sensor data available</div>';
        return;
    }

    const sensorHTML = sensors.map(sensor => {
        // Handle both direct properties and nested latest_reading structure
        const reading = sensor.latest_reading || sensor;
        const temperature = parseFloat(reading.temperature || 0);
        const pressure = parseFloat(reading.pressure || 0);
        const flowRate = parseFloat(reading.flow_rate || 0);
        const vibration = parseFloat(reading.vibration || 0);
        const timestamp = new Date(parseFloat(reading.timestamp) * 1000).toLocaleTimeString();

        let statusClass = 'normal';
        if (temperature > 200 || pressure > 1500) {
            statusClass = 'critical';
        } else if (temperature > 180 || pressure > 1200) {
            statusClass = 'warning';
        }

        // Build sensor display based on available data
        let sensorValues = [];
        if (temperature > 0) sensorValues.push(`🌡️ ${temperature.toFixed(1)}°F`);
        if (pressure > 0) sensorValues.push(`📊 ${pressure.toFixed(0)} PSI`);
        if (flowRate > 0) sensorValues.push(`💧 ${flowRate.toFixed(1)} bbl/hr`);
        if (vibration > 0) sensorValues.push(`📳 ${vibration.toFixed(2)} mm/s`);
        sensorValues.push(`🕐 ${timestamp}`);

        return `
            <div class="sensor-item ${statusClass}">
                <div class="sensor-name">${sensor.sensor_id}</div>
                <div class="sensor-values">
                    ${sensorValues.join(' | ')}
                </div>
            </div>
        `;
    }).join('');

    sensorList.innerHTML = sensorHTML;
}

async function updateAlerts() {
    try {
        const startTime = performance.now();
        // Always show all dashboard alerts - do NOT filter by selected asset
        const endpoint = `${API_BASE_URL}/api/dashboard/alerts`;

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);

        const response = await fetch(endpoint, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const fetchTime = performance.now() - startTime;

        if (data.success && data.alerts) {
            // Display ALL alerts regardless of selected asset
            displayAlerts(data.alerts);
            console.log(`🚨 Alerts updated (${data.alerts.length} alerts) in ${fetchTime.toFixed(0)}ms`);
        } else {
            // No alerts available, but not an error
            const alertsList = document.getElementById('alerts-list');
            if (alertsList) {
                alertsList.innerHTML = '<div class="loading">No active alerts</div>';
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.error('❌ Alerts request timed out');
        } else {
            console.error('❌ Error updating alerts:', error);
        }
        // Only show error in console, not in UI - keep previous data or show loading
        const alertsList = document.getElementById('alerts-list');
        if (alertsList && alertsList.innerHTML.includes('Loading')) {
            alertsList.innerHTML = '<div class="loading">Connecting to alert system...</div>';
        }
    }
}

function displayAlerts(alerts) {
    const alertsList = document.getElementById('alerts-list');

    if (alerts.length === 0) {
        alertsList.innerHTML = '<div class="loading">No active alerts</div>';
        return;
    }

    const alertsHTML = alerts.map(alert => {
        const timestamp = new Date(alert.timestamp);
        const dateString = timestamp.toLocaleDateString();
        const timeString = timestamp.toLocaleTimeString();

        // Determine severity styling
        let severityClass = 'warning';
        let severityIcon = '⚠️';
        if (alert.severity === 'critical') {
            severityClass = 'critical';
            severityIcon = '🚨';
        } else if (alert.severity === 'high') {
            severityClass = 'critical';
            severityIcon = '🔴';
        } else if (alert.severity === 'warning') {
            severityIcon = '🟡';
        }

        return `
            <div class="alert-item ${severityClass}">
                <div class="alert-header">
                    <span class="alert-icon">${severityIcon}</span>
                    <strong>${alert.message}</strong>
                    <span class="alert-severity">${alert.severity.toUpperCase()}</span>
                </div>
                <div class="alert-details">${alert.details || 'No additional details'}</div>
                <div class="alert-meta">
                    <span class="alert-location">📍 ${alert.location}</span>
                    <span class="alert-time">${dateString} ${timeString}</span>
                </div>
            </div>
        `;
    }).join('');

    alertsList.innerHTML = alertsHTML;
}

// ============================================================================
// REDIS COMMAND MONITORING FOR DASHBOARD
// ============================================================================

function updateDashboardCommands() {
    updateRedisCommands('dashboard', 'command-log', {
        read: 'read-count',
        write: 'write-count',
        total: 'total-commands'
    });
}

function clearDashboardCommands() {
    clearCommandHistory('dashboard', 'command-log', {
        read: 'read-count',
        write: 'write-count',
        total: 'total-commands'
    });
}

