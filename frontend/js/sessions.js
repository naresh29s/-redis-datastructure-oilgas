// Sessions-specific JavaScript

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    startSessionUpdates();
    console.log('👥 Session Management Initialized');
    console.log(`📡 API Base URL: ${API_BASE_URL}`);
});

// ============================================================================
// SESSION MANAGEMENT
// ============================================================================

function startSessionUpdates() {
    // Update sessions every 10 seconds
    updateSessions();
    setInterval(updateSessions, 10000);

    // Update Redis commands every 2 seconds
    updateSessionCommands();
    setInterval(updateSessionCommands, 2000);
}

async function updateSessions() {
    try {
        // Get session metrics (always global)
        const metricsResponse = await fetch(`${API_BASE_URL}/api/sessions/metrics`);
        const metricsData = await metricsResponse.json();

        if (metricsData.success) {
            document.getElementById('total-sessions').textContent = metricsData.metrics.total_active_sessions;
            document.getElementById('unique-users').textContent = metricsData.metrics.unique_users;
        }

        // Get sessions (asset-specific if selected)
        let sessionsEndpoint = `${API_BASE_URL}/api/sessions`;
        if (selectedAsset) {
            sessionsEndpoint = `${API_BASE_URL}/api/assets/${selectedAsset}/sessions`;
        }

        const sessionsResponse = await fetch(sessionsEndpoint);
        const sessionsData = await sessionsResponse.json();

        if (sessionsData.success) {
            displaySessions(sessionsData.sessions);
        }
    } catch (error) {
        console.error('Error updating sessions:', error);
        document.getElementById('session-list').innerHTML = '<div class="loading">Error loading sessions</div>';
    }
}

function displaySessions(sessions) {
    const sessionList = document.getElementById('session-list');

    if (sessions.length === 0) {
        sessionList.innerHTML = '<div class="loading">No active sessions</div>';
        return;
    }

    const sessionHTML = sessions.map(session => {
        const userData = JSON.parse(session.user_data || '{}');
        const createdAt = new Date(session.created_at).toLocaleTimeString();
        const lastActivity = new Date(session.last_activity).toLocaleTimeString();

        return `
            <div class="session-item">
                <div class="session-user">${userData.name || session.user_id}</div>
                <div class="session-details">
                    Role: ${userData.role || 'Unknown'} | Location: ${userData.location || 'Unknown'}<br>
                    Created: ${createdAt} | Last Activity: ${lastActivity}
                </div>
            </div>
        `;
    }).join('');

    sessionList.innerHTML = sessionHTML;
}

// ============================================================================
// REDIS COMMAND MONITORING FOR SESSIONS
// ============================================================================

function updateSessionCommands() {
    updateRedisCommands('session', 'session-command-log', {
        read: 'session-read-count',
        write: 'session-write-count',
        total: 'session-total-commands'
    });
}

function clearSessionCommands() {
    clearCommandHistory('session', 'session-command-log', {
        read: 'session-read-count',
        write: 'session-write-count',
        total: 'session-total-commands'
    });
}

