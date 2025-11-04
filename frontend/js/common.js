// Oil & Gas Field Operations - Common JavaScript Functions

// Configuration - Local development
const API_BASE_URL = 'http://localhost:5001';

// Global variables
let map;
let assetMarkers = {};
let selectedAsset = null;
let selectedMarker = null;

// ============================================================================
// MAP INITIALIZATION AND ASSET TRACKING
// ============================================================================

function initializeMap() {
    try {
        console.log('🗺️ Initializing map...');
        console.log('🔍 Checking Leaflet availability:', typeof L);

        // Check if map element exists
        const mapElement = document.getElementById('map');
        if (!mapElement) {
            console.error('❌ Map element not found!');
            return;
        }
        console.log('✅ Map element found:', mapElement);

        // Check if Leaflet is available
        if (typeof L === 'undefined') {
            console.error('❌ Leaflet (L) is not defined!');
            mapElement.innerHTML = '<div style="color: red; padding: 20px; text-align: center;">Map library not loaded. Please refresh the page.</div>';
            return;
        }

        // Initialize Leaflet map (Texas Permian Basin)
        console.log('🗺️ Creating Leaflet map instance...');
        map = L.map('map').setView([31.8457, -102.3676], 10);
        console.log('✅ Map instance created:', map);

        // Add OpenStreetMap tiles
        console.log('🗺️ Adding tile layer...');
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        console.log('✅ Map initialized successfully');

        // Load initial assets
        loadAssets();
    } catch (error) {
        console.error('❌ Error initializing map:', error);
        console.error('❌ Error stack:', error.stack);
        const mapElement = document.getElementById('map');
        if (mapElement) {
            mapElement.innerHTML = '<div style="color: red; padding: 20px; text-align: center;">Error initializing map: ' + error.message + '</div>';
        }
    }
}

async function loadAssets() {
    try {
        const startTime = performance.now();
        console.log('📍 Loading assets...');

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout (optimized with pipelining)

        const response = await fetch(`${API_BASE_URL}/api/assets`, {
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const fetchTime = performance.now() - startTime;

        if (data.success && data.assets) {
            console.log(`✅ Loaded ${data.assets.length} assets in ${fetchTime.toFixed(0)}ms`);
            updateAssetMarkers(data.assets);
        } else {
            console.warn('⚠️ No assets returned from API');
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.error('❌ Asset loading timed out after 15 seconds');
        } else {
            console.error('❌ Error loading assets:', error);
        }
        // Show error message on map
        const mapElement = document.getElementById('map');
        if (mapElement && map) {
            const errorPopup = L.popup()
                .setLatLng([31.8457, -102.3676])
                .setContent('<div style="color: red; font-weight: bold;">⚠️ Failed to load assets. Retrying...</div>')
                .openOn(map);

            // Retry after 5 seconds
            setTimeout(() => {
                console.log('🔄 Retrying asset load...');
                loadAssets();
            }, 5000);
        }
    }
}

function updateAssetMarkers(assets) {
    // Check if map is initialized
    if (!map) {
        console.warn('⚠️ Map not initialized yet, skipping marker update');
        return;
    }

    if (!assets || assets.length === 0) {
        console.warn('⚠️ No assets to display on map');
        return;
    }

    console.log(`🗺️ Updating ${assets.length} asset markers on map...`);

    // Clear existing markers
    Object.values(assetMarkers).forEach(marker => {
        if (map && marker) {
            map.removeLayer(marker);
        }
    });
    assetMarkers = {};

    // Add new markers
    assets.forEach(asset => {
        if (!asset.latitude || !asset.longitude) {
            console.warn(`⚠️ Asset ${asset.id} missing coordinates, skipping`);
            return;
        }

        const icon = getAssetIcon(asset.type, asset.status);
        const marker = L.marker([asset.latitude, asset.longitude], { icon })
            .addTo(map)
            .bindPopup(`
                <strong>${asset.name}</strong><br>
                Type: ${asset.type}<br>
                Status: <span class="status-${asset.status}">${asset.status}</span><br>
                Last Update: ${new Date(asset.last_update).toLocaleTimeString()}<br>
                <button onclick="selectAsset('${asset.id}')" style="margin-top: 5px; padding: 3px 8px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">Select Asset</button>
            `)
            .on('click', function() {
                selectAsset(asset.id);
            });

        // Store asset data with marker
        marker.assetData = asset;
        assetMarkers[asset.id] = marker;
    });

    console.log(`✅ Added ${Object.keys(assetMarkers).length} markers to map`);
}

function getAssetIcon(type, status) {
    const colors = {
        'active': '#2ecc71',
        'maintenance': '#f39c12',
        'offline': '#e74c3c'
    };
    
    const icons = {
        'drilling_rig': '🏗️',
        'service_truck': '🚛',
        'pump_jack': '⚡',
        'compressor': '🔧',
        'separator': '⚙️',
        'tank_battery': '🛢️',
        'pipeline_valve': '🔩',
        'wellhead': '🕳️'
    };
    
    return L.divIcon({
        html: `<div style="background: ${colors[status] || '#7f8c8d'}; 
                      border-radius: 50%; 
                      width: 30px; 
                      height: 30px; 
                      display: flex; 
                      align-items: center; 
                      justify-content: center; 
                      font-size: 16px; 
                      border: 2px solid white;">
                 ${icons[type] || '📍'}
               </div>`,
        className: 'custom-div-icon',
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    });
}

// ============================================================================
// ASSET SELECTION FUNCTIONALITY
// ============================================================================

function selectAsset(assetId) {
    // Clear previous selection
    if (selectedMarker) {
        selectedMarker.setIcon(getAssetIcon(selectedMarker.assetData.type, selectedMarker.assetData.status));
    }

    // Set new selection
    selectedAsset = assetId;
    selectedMarker = assetMarkers[assetId];

    if (selectedMarker) {
        // Highlight selected marker
        selectedMarker.setIcon(getSelectedAssetIcon(selectedMarker.assetData.type, selectedMarker.assetData.status));

        // Update dashboard title
        updateAssetHeader(selectedMarker.assetData);

        // Update all dashboard panels with asset-specific data
        if (typeof updateDashboardData === 'function') {
            updateDashboardData();
        }
    }
}

function deselectAsset() {
    if (selectedMarker) {
        selectedMarker.setIcon(getAssetIcon(selectedMarker.assetData.type, selectedMarker.assetData.status));
    }

    selectedAsset = null;
    selectedMarker = null;

    // Reset dashboard title
    const headerElement = document.querySelector('h1');
    if (headerElement) {
        headerElement.innerHTML = '🛢️ Digital Twin System';
    }

    // Update dashboard with overall data
    if (typeof updateDashboardData === 'function') {
        updateDashboardData();
    }
}

function updateAssetHeader(assetData) {
    const headerElement = document.querySelector('h1');
    if (headerElement) {
        headerElement.innerHTML = `
            🛢️ Digital Twin: ${assetData.name} - ${assetData.type.replace('_', ' ').toUpperCase()}
            <button onclick="deselectAsset()" style="margin-left: 10px; padding: 2px 6px; background: #e74c3c; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.8em;">Show All</button>
        `;
    }
}

function getSelectedAssetIcon(type, status) {
    // Create highlighted version of the icon
    const colors = {
        'active': '#e74c3c',      // Red for selected
        'maintenance': '#e74c3c',
        'inactive': '#e74c3c'
    };

    const icons = {
        'drilling_rig': '🏗️',
        'service_truck': '🚛',
        'pump_jack': '⛽',
        'compressor': '🔧',
        'separator': '🏭',
        'tank_battery': '🛢️',
        'pipeline_valve': '🔧',
        'wellhead': '🕳️'
    };

    return L.divIcon({
        html: `<div style="background-color: ${colors[status] || colors.active};
                      color: white;
                      border-radius: 50%;
                      width: 30px;
                      height: 30px;
                      display: flex;
                      align-items: center;
                      justify-content: center;
                      font-size: 16px;
                      border: 3px solid #fff;
                      box-shadow: 0 0 10px rgba(231, 76, 60, 0.8);">
               ${icons[type] || '📍'}
               </div>`,
        className: 'custom-div-icon',
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    });
}

// ============================================================================
// REDIS COMMAND MONITORING
// ============================================================================

async function updateRedisCommands(context = 'dashboard', logElementId = 'command-log', counters = {}) {
    try {
        // Get command statistics
        const statsResponse = await fetch(`${API_BASE_URL}/api/redis/stats?context=${context}`);
        const statsData = await statsResponse.json();

        if (statsData.success) {
            if (context === 'session') {
                if (counters.read) document.getElementById(counters.read).textContent = statsData.stats.read_count;
                if (counters.write) document.getElementById(counters.write).textContent = statsData.stats.write_count;
                if (counters.total) document.getElementById(counters.total).textContent = statsData.stats.total_count;
            } else if (context === 'search') {
                const ftSearchCount = statsData.stats.command_counts?.['FT.SEARCH'] || 0;
                const ftTagvalsCount = statsData.stats.command_counts?.['FT.TAGVALS'] || 0;
                if (counters.ftSearch) document.getElementById(counters.ftSearch).textContent = ftSearchCount;
                if (counters.ftTagvals) document.getElementById(counters.ftTagvals).textContent = ftTagvalsCount;
                if (counters.total) document.getElementById(counters.total).textContent = statsData.stats.total_count;
            } else {
                if (counters.read) document.getElementById(counters.read).textContent = statsData.stats.read_count;
                if (counters.write) document.getElementById(counters.write).textContent = statsData.stats.write_count;
                if (counters.total) document.getElementById(counters.total).textContent = statsData.stats.total_count;
            }
        }

        // Get recent commands
        const commandsResponse = await fetch(`${API_BASE_URL}/api/redis/commands?limit=100&context=${context}`);
        const commandsData = await commandsResponse.json();

        if (commandsData.success) {
            displayRedisCommands(commandsData.commands, logElementId);
        }
    } catch (error) {
        console.error('Error updating Redis commands:', error);
        document.getElementById(logElementId).innerHTML = '<div class="loading">Error loading commands</div>';
    }
}

function displayRedisCommands(commands, targetElementId = 'command-log') {
    const commandLog = document.getElementById(targetElementId);

    if (commands.length === 0) {
        commandLog.innerHTML = '<div class="loading">No commands logged yet</div>';
        return;
    }

    // Show most recent commands first
    const recentCommands = commands.slice(-50).reverse();

    const commandHTML = recentCommands.map(cmd => {
        const timestamp = new Date(cmd.timestamp).toLocaleTimeString();
        const commandClass = `command-${cmd.type}`;
        const keyInfo = cmd.key ? ` ${cmd.key}` : '';

        return `
            <div class="command-item">
                <span class="command-timestamp">${timestamp}</span>
                <span class="command-text ${commandClass}">${cmd.command}${keyInfo}</span>
            </div>
        `;
    }).join('');

    commandLog.innerHTML = commandHTML;

    // Auto-scroll to bottom to show latest commands
    commandLog.scrollTop = commandLog.scrollHeight;
}

async function clearCommandHistory(context, logElementId, counters = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/redis/commands/clear`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ context: context })
        });

        const data = await response.json();
        if (data.success) {
            // Clear the display immediately
            document.getElementById(logElementId).innerHTML = '<div class="loading">Command history cleared</div>';

            // Reset counters
            Object.values(counters).forEach(counterId => {
                const element = document.getElementById(counterId);
                if (element) element.textContent = '0';
            });

            console.log(`Command history cleared for context: ${context}`);
        } else {
            console.error('Failed to clear command history:', data.error);
        }
    } catch (error) {
        console.error('Error clearing command history:', error);
    }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
});

