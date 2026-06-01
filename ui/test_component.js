// UI test logic for dashboard
function formatBytesTest(bytes, decimals = 2) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Ensure the UI cards exist in the dashboard
window.addEventListener("load", () => {
    const dashboardGrid = document.querySelector('.dashboard-grid');
    if (!dashboardGrid) return;
    
    // Inject Configuration Sync Card
    const syncCardHTML = `
        <div class="card" id="config-status-card">
            <div class="card-header">
                <div>
                    <div class="card-title">Configuration Sync</div>
                    <div class="card-subtitle">Server vs Gateway status</div>
                </div>
            </div>
            <div class="status-row" style="margin-bottom: 12px;">
                <span class="status-text" style="color: var(--text-dim);">Sync Status:</span>
                <span class="status-text" id="config-sync-status" style="font-weight: bold; margin-left: 5px;">Loading...</span>
            </div>
            <div id="pending-config-alert" style="display: none; background: rgba(234, 179, 8, 0.1); border: 1px solid var(--warning); border-radius: 4px; padding: 10px; margin-bottom: 12px;">
                <span style="color: var(--warning); font-size: 12px;">
                    <strong>Pending changes detected!</strong><br>
                    The Gateway has not yet adopted the latest server configuration.
                </span>
                <button class="btn-ghost btn-full" style="margin-top: 8px; font-size: 11px;" onclick="viewPendingConfigDiff()">View Pending JSON Difference</button>
            </div>
            <div class="divider"></div>
            <div class="grid-2">
                <button class="btn-ghost btn-full" onclick="updateConfigStatus()">
                    Refresh Sync Status
                </button>
                <button id="toggle-invalid-config-btn" class="btn-danger btn-full" onclick="toggleInvalidConfig()">
                    Send Invalid JSON
                </button>
            </div>
        </div>
    `;
    dashboardGrid.insertAdjacentHTML('beforeend', syncCardHTML);

    // Inject Outage Buffer Card
    const bufferCardHTML = `
        <div class="card" id="test-buffer-card">
            <div class="card-header">
                <div>
                    <div class="card-title">Simulated Outage & Buffer</div>
                    <div class="card-subtitle">Test Gateway's offline behavior</div>
                </div>
            </div>
            <div class="status-row" style="margin-bottom: 16px;">
                <span class="status-text" style="color: var(--text-dim);">Connection State:</span>
                <button id="toggle-outage-btn" class="btn-danger" style="padding: 4px 12px; font-size: 12px;" onclick="toggleOutage()">Simulate Outage</button>
            </div>
            
            <div>
                <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px;">
                    <span style="color: var(--text-muted)">Local Buffer Usage</span>
                    <span id="buffer-usage-text" style="font-weight: bold; font-family: monospace;">0 B / 10 MB</span>
                </div>
                <div style="background: var(--border); border-radius: 4px; height: 6px; margin-bottom: 12px; overflow: hidden;">
                    <div id="buffer-progress-fill" style="height: 100%; width: 0%; background: var(--success); border-radius: 4px; transition: width 0.4s ease, background 0.4s ease;"></div>
                </div>
                <div style="font-size: 12px; color: var(--text-dim); margin-top: 8px; text-align: right;">
                    Pending Batches: <strong id="buffer-pending-count">0</strong>
                </div>
            </div>
        </div>
    `;
    dashboardGrid.insertAdjacentHTML('beforeend', bufferCardHTML);

    // Setup intervals
    updateOutageAndBufferStatus();
    setInterval(updateOutageAndBufferStatus, 2000);
    updateConfigStatus();
    setInterval(updateConfigStatus, 2000);
});

// Sync Status logic
let _lastServerConfig = null;
let _lastGatewayConfig = null;

window.updateConfigStatus = function() {
    fetch('/api/config/status')
    .then(r => r.json())
    .then(data => {
        _lastServerConfig = data.serverConfig;
        _lastGatewayConfig = data.gatewayConfig;
        
        const statusEl = document.getElementById('config-sync-status');
        const alertEl = document.getElementById('pending-config-alert');
        if (!statusEl) return;
        
        if (data.invalidConfigSimulated) {
            statusEl.textContent = 'Simulating Invalid Config';
            statusEl.style.color = 'var(--danger)';
            if (alertEl) {
                alertEl.style.display = 'block';
                alertEl.style.borderColor = 'var(--danger)';
                alertEl.querySelector('span').innerHTML = '<strong>Server is sending INVALID JSON!</strong><br>Gateway will fallback to Last Known Good Config.';
                alertEl.querySelector('span').style.color = 'var(--danger)';
            }
        } else if (data.isPending) {
            if (data.gatewayState === 'testing') {
                statusEl.textContent = 'Testing Configuration... (Checking SQL connections)';
                statusEl.style.color = 'var(--accent)';
                if (alertEl) {
                    alertEl.style.display = 'block';
                    alertEl.style.borderColor = 'var(--accent)';
                    alertEl.querySelector('span').innerHTML = '<strong>Gateway is currently testing the configuration.</strong><br>Please wait...';
                    alertEl.querySelector('span').style.color = 'var(--accent)';
                }
            } else if (data.gatewayState === 'rejected') {
                statusEl.textContent = 'Rejected by Gateway';
                statusEl.style.color = 'var(--danger)';
                if (alertEl) {
                    alertEl.style.display = 'block';
                    alertEl.style.borderColor = 'var(--danger)';
                    alertEl.querySelector('span').innerHTML = '<strong>Configuration Rejected!</strong><br>Gateway tested the new configuration but the tests failed. Error: ' + (data.gatewayError || 'Unknown error');
                    alertEl.querySelector('span').style.color = 'var(--danger)';
                }
            } else {
                statusEl.textContent = 'Pending (Waiting for Gateway to fetch)';
                statusEl.style.color = 'var(--warning)';
                if (alertEl) {
                    alertEl.style.display = 'block';
                    alertEl.style.borderColor = 'var(--warning)';
                    alertEl.querySelector('span').innerHTML = '<strong>Pending changes detected!</strong><br>The Gateway has not yet adopted the latest server configuration.';
                    alertEl.querySelector('span').style.color = 'var(--warning)';
                }
            }
        } else {
            statusEl.textContent = 'Synchronized';
            statusEl.style.color = 'var(--success)';
            if (alertEl) alertEl.style.display = 'none';
        }
    })
    .catch(() => {});
};

window.viewPendingConfigDiff = function() {
    showPage('logs');
    const card = document.getElementById("log-viewer-card");
    if (!card) return;
    card.style.display = "block";
    document.getElementById("log-viewer-title").textContent = "Pending Config JSON";
    document.getElementById("log-viewer-subtitle").textContent = "The configuration the gateway is currently evaluating (or failed to adopt)";
    
    currentLogData = _lastServerConfig;
    setLogViewMode('json');
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

window.simulateInvalidConfigState = false;
window.toggleInvalidConfig = function() {
    fetch('/api/simulate-invalid-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ simulate: !window.simulateInvalidConfigState })
    })
    .then(r => r.json())
    .then(data => {
        window.simulateInvalidConfigState = data.simulateInvalidConfig;
        const btn = document.getElementById('toggle-invalid-config-btn');
        if (btn) {
            if (window.simulateInvalidConfigState) {
                btn.textContent = "Stop Sending Invalid JSON";
                btn.className = "btn-success btn-full";
            } else {
                btn.textContent = "Send Invalid JSON";
                btn.className = "btn-danger btn-full";
            }
        }
    });
};

// Outage Buffer logic
window.toggleOutage = function() {
    fetch('/api/simulate-outage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ simulate: !window.simulateOutageState })
    })
    .then(r => r.json())
    .then(data => {
        updateOutageUI(data.simulateOutage);
    });
};

window.simulateOutageState = false;
function updateOutageUI(isSimulated) {
    window.simulateOutageState = isSimulated;
    const btn = document.getElementById('toggle-outage-btn');
    if (!btn) return;
    if (isSimulated) {
        btn.textContent = "Restore Connection";
        btn.className = "btn-success";
    } else {
        btn.textContent = "Simulate Outage";
        btn.className = "btn-danger";
    }
}

window.updateOutageAndBufferStatus = function() {
    fetch('/api/ehistorian/gateway/buffer-status')
    .then(r => r.json())
    .then(data => {
        updateOutageUI(data.simulateOutage);
        const b = data.buffer;
        const usedStr = formatBytesTest(b.bytesSize);
        const maxStr = formatBytesTest(b.maxBytes);
        
        const usageEl = document.getElementById('buffer-usage-text');
        const fillEl = document.getElementById('buffer-progress-fill');
        const countEl = document.getElementById('buffer-pending-count');
        
        if (usageEl) usageEl.textContent = usedStr + " / " + maxStr;
        if (countEl) countEl.textContent = b.pendingCount;
        
        if (fillEl) {
            let pct = (b.bytesSize / b.maxBytes) * 100;
            if (pct > 100) pct = 100;
            fillEl.style.width = pct + "%";
            if (pct > 90) fillEl.style.background = 'var(--danger)';
            else if (pct > 70) fillEl.style.background = 'var(--warning)';
            else fillEl.style.background = 'var(--success)';
        }
    })
    .catch(() => {});
};
