// Search-specific JavaScript

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeSearchFilters();
    startSearchUpdates();
    
    // Add search input event listener for Enter key
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
    }
    
    console.log('🔍 Search Interface Initialized');
    console.log(`📡 API Base URL: ${API_BASE_URL}`);
});

// ============================================================================
// SEARCH INITIALIZATION
// ============================================================================

function startSearchUpdates() {
    // Update Redis commands every 2 seconds
    updateSearchCommands();
    setInterval(updateSearchCommands, 2000);
}

async function initializeSearchFilters() {
    try {
        // Load filter options from API for dropdown filters only
        // Note: 'region' field doesn't exist in index, so we skip it gracefully
        const dropdownFields = ['type'];

        for (const field of dropdownFields) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 3000); // 3 second timeout

                const response = await fetch(`${API_BASE_URL}/api/search/suggestions?field=${field}`, {
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                if (!response.ok) {
                    console.warn(`Failed to load ${field} suggestions: ${response.status}`);
                    continue;
                }

                const data = await response.json();

                if (data.success && data.suggestions && data.suggestions.length > 0) {
                    const selectElement = document.getElementById(`${field}-filter`);
                    data.suggestions.forEach(suggestion => {
                        const option = document.createElement('option');
                        option.value = suggestion;
                        option.textContent = suggestion.replace('_', ' ').toUpperCase();
                        selectElement.appendChild(option);
                    });
                    console.log(`✅ Loaded ${data.suggestions.length} ${field} options`);
                } else {
                    console.warn(`No suggestions available for ${field}`);
                }
            } catch (fieldError) {
                if (fieldError.name === 'AbortError') {
                    console.warn(`Timeout loading ${field} suggestions`);
                } else {
                    console.warn(`Error loading ${field} suggestions:`, fieldError);
                }
                // Continue with other fields even if one fails
            }
        }

        // Radio buttons for manufacturer and status are hardcoded in HTML
        console.log('✅ Search filters initialized');
    } catch (error) {
        console.error('Error initializing search filters:', error);
        // Don't block the page if filters fail to load
    }
}

// ============================================================================
// SEARCH FUNCTIONALITY
// ============================================================================

async function performSearch() {
    try {
        const query = document.getElementById('search-input').value.trim();
        const type = document.getElementById('type-filter').value;
        const manufacturer = document.querySelector('input[name="manufacturer"]:checked').value;
        const status = document.querySelector('input[name="status"]:checked').value;
        const region = document.getElementById('region-filter').value;
        const sortOrder = document.querySelector('input[name="sort"]:checked').value;

        // Build query parameters
        const params = new URLSearchParams();
        if (query) params.append('q', query);
        if (type) params.append('type', type);
        if (manufacturer) params.append('manufacturer', manufacturer);
        if (status) params.append('status', status);
        if (region) params.append('region', region);
        params.append('limit', '50');

        // Show loading state
        document.getElementById('search-results').innerHTML = '<div class="loading">Searching assets...</div>';
        document.getElementById('search-summary').textContent = 'Searching...';

        // Perform search
        const response = await fetch(`${API_BASE_URL}/api/search/assets?${params.toString()}`);
        const data = await response.json();

        if (data.success) {
            displaySearchResults(data);
            updateSearchSummary(data);
        } else {
            document.getElementById('search-results').innerHTML = `<div class="loading">Error: ${data.error}</div>`;
        }

    } catch (error) {
        console.error('Error performing search:', error);
        document.getElementById('search-results').innerHTML = '<div class="loading">Error performing search</div>';
    }
}

function displaySearchResults(data) {
    const resultsContainer = document.getElementById('search-results');

    if (data.assets.length === 0) {
        resultsContainer.innerHTML = '<div class="loading">No assets found matching your search criteria.</div>';
        return;
    }

    // Apply client-side sorting
    const sortOrder = document.querySelector('input[name="sort"]:checked').value;
    let sortedAssets = [...data.assets];

    if (sortOrder === 'status-asc') {
        sortedAssets.sort((a, b) => a.status.localeCompare(b.status));
    } else if (sortOrder === 'status-desc') {
        sortedAssets.sort((a, b) => b.status.localeCompare(a.status));
    }

    const resultsHTML = sortedAssets.map(asset => `
        <div class="search-result-item">
            <div class="search-result-header">
                <div class="search-result-title">${asset.name}</div>
                <div class="search-result-type">${asset.type.replace('_', ' ')}</div>
            </div>
            <div class="search-result-details">
                <div class="search-result-detail"><strong>ID:</strong> ${asset.id}</div>
                <div class="search-result-detail"><strong>Manufacturer:</strong> ${asset.manufacturer}</div>
                <div class="search-result-detail"><strong>Model:</strong> ${asset.model}</div>
                <div class="search-result-detail"><strong>Status:</strong> <span class="status-${asset.status}">${asset.status}</span></div>
                <div class="search-result-detail"><strong>Region:</strong> ${asset.region}</div>
                <div class="search-result-detail"><strong>Zone:</strong> ${asset.zone}</div>
                <div class="search-result-detail"><strong>Temperature:</strong> ${asset.temperature}°C</div>
                <div class="search-result-detail"><strong>Pressure:</strong> ${asset.pressure} PSI</div>
                <div class="search-result-detail"><strong>Flow Rate:</strong> ${asset.flow_rate} bbl/hr</div>
                <div class="search-result-detail"><strong>Team:</strong> ${asset.team}</div>
            </div>
            <div class="search-result-actions">
                <button class="search-result-button" onclick="viewAssetOnDashboard('${asset.id}')">
                    📍 View on Dashboard
                </button>
            </div>
        </div>
    `).join('');

    resultsContainer.innerHTML = resultsHTML;
}

function updateSearchSummary(data) {
    const summary = document.getElementById('search-summary');
    const queryText = data.query === '*' ? 'all assets' : `"${data.query}"`;
    const filtersText = Object.values(data.filters).filter(f => f).length > 0 ?
        ` with filters applied` : '';

    summary.textContent = `Found ${data.total} assets matching ${queryText}${filtersText}. Showing ${data.count} results.`;
}

function clearSearch() {
    document.getElementById('search-input').value = '';
    document.getElementById('type-filter').value = '';
    document.getElementById('region-filter').value = '';

    // Reset radio buttons to "All" options
    document.getElementById('manufacturer-all').checked = true;
    document.getElementById('status-all').checked = true;
    document.getElementById('sort-none').checked = true;

    document.getElementById('search-results').innerHTML = '<div class="loading">Enter search criteria and click "Search Assets" to find matching assets.</div>';
    document.getElementById('search-summary').textContent = 'Ready to search assets...';
}

function viewAssetOnDashboard(assetId) {
    // Store the asset ID in sessionStorage so dashboard can select it
    sessionStorage.setItem('selectedAssetId', assetId);
    // Navigate to dashboard
    window.location.href = 'dashboard.html';
}

// ============================================================================
// REDIS COMMAND MONITORING FOR SEARCH
// ============================================================================

function updateSearchCommands() {
    updateRedisCommands('search', 'search-command-log', {
        ftSearch: 'search-ft-search-count',
        ftTagvals: 'search-ft-tagvals-count',
        total: 'search-total-commands'
    });
}

function clearSearchCommands() {
    clearCommandHistory('search', 'search-command-log', {
        ftSearch: 'search-ft-search-count',
        ftTagvals: 'search-ft-tagvals-count',
        total: 'search-total-commands'
    });
}

