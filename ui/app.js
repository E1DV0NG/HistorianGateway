/**
 * eHistorian Control Panel — app.js
 */

"use strict";

// ── State ───────────────────────────────────────────────
let currentConfig = {
  gatewayId: "",
  apiUrl: "",
  opcua: [],
  sql: [],
};



// ── Init ────────────────────────────────────────────────
window.addEventListener("load", () => {
  updateStatus();
  setInterval(updateStatus, 2000);
  setInterval(pollServerActivity, 2000);
  setInterval(pollStats, 3000);

  loadConfig();
  loadLogs();
  fetchDeviceIp();
  pollStats();
  // Restore sidebar state
  if (localStorage.getItem('sidebarCollapsed') === 'true') {
    document.body.classList.add('sidebar-collapsed');
  }
});

// ── Sidebar Toggle ──────────────────────────────────────────
function toggleSidebar() {
  const collapsed = document.body.classList.toggle('sidebar-collapsed');
  localStorage.setItem('sidebarCollapsed', collapsed);
}

// ── Activity Monitor ───────────────────────────────────
const LOG_COLORS = {
  info:    'var(--text-dim)',
  ok:      'var(--success)',
  error:   'var(--danger)',
  warn:    'var(--warning)',
  process: 'var(--accent)',
};
const LOG_ICONS = {
  info:    '▸',
  ok:      '✔',
  error:   '✘',
  warn:    '⚠',
  process: '▶',
};

function logActivity(msg, type = 'info') {
  const log = document.getElementById('activity-log');
  if (!log) return;

  // Remove placeholder
  const placeholder = log.querySelector('[data-placeholder]');
  if (placeholder) placeholder.remove();
  const empty = log.querySelector('div[style*="text-align: center"]');
  if (empty) empty.remove();

  const now = new Date();
  const ts = now.toLocaleTimeString('cs-CZ', { hour12: false }) + 
              '.' + String(now.getMilliseconds()).padStart(3, '0');

  const entry = document.createElement('div');
  entry.style.cssText = `color: ${LOG_COLORS[type] || LOG_COLORS.info}; border-bottom: 1px solid var(--border-light); padding: 3px 0; display: flex; gap: 10px; align-items: baseline;`;
  entry.innerHTML = `
    <span style="color: var(--text-muted); flex-shrink: 0;">${ts}</span>
    <span style="color: ${LOG_COLORS[type]}; flex-shrink: 0;">${LOG_ICONS[type] || '▸'}</span>
    <span>${msg}</span>
  `;

  // Prepend (newest at top due to flex-direction: column-reverse)
  log.appendChild(entry);

  // Keep max 200 entries
  while (log.children.length > 200) log.removeChild(log.firstChild);
}

function clearActivityLog() {
  const log = document.getElementById('activity-log');
  if (log) log.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 20px 0;">No activity yet...</div>';
}

// ── Server activity poll ───────────────────────────────────
let _activityLastId = 0;

function pollServerActivity() {
  fetch(`/api/activity?since=${_activityLastId}`)
    .then(r => r.json())
    .then(entries => {
      entries.forEach(e => {
        if (e.id > _activityLastId) _activityLastId = e.id;
        // Convert server UTC timestamp to local time
        const d = new Date(e.timestamp);
        const ts = d.toLocaleTimeString('cs-CZ', { hour12: false }) +
                   '.' + String(d.getMilliseconds()).padStart(3, '0');
        // Reuse logActivity but inject pre-formatted timestamp
        logActivityRaw(ts, e.msg, e.kind);

        // Auto-reload logs list if an ingest occurred
        if (e.msg.startsWith("INGEST")) {
          loadLogs();
        }
      });
    })
    .catch(() => {});
}

function logActivityRaw(ts, msg, type = 'info') {
  const log = document.getElementById('activity-log');
  if (!log) return;
  const empty = log.querySelector('div[style*="text-align: center"]');
  if (empty) empty.remove();

  const entry = document.createElement('div');
  entry.style.cssText = `color: ${LOG_COLORS[type] || LOG_COLORS.info}; border-bottom: 1px solid var(--border-light); padding: 3px 0; display: flex; gap: 10px; align-items: baseline;`;
  entry.innerHTML = `
    <span style="color: var(--text-muted); flex-shrink: 0;">${ts}</span>
    <span style="color: ${LOG_COLORS[type]}; flex-shrink: 0;">${LOG_ICONS[type] || '▸'}</span>
    <span>${msg}</span>
  `;
  log.appendChild(entry);
  while (log.children.length > 300) log.removeChild(log.firstChild);
  
  // Auto-scroll to top (newest is at top due to column-reverse)
  log.scrollTop = 0;
}

// ── Excel Export ────────────────────────────────────────────
function exportLogsExcel() {
  const btn = event.target.closest('button');
  const origText = btn.innerHTML;
  btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Generating...`;
  btn.disabled = true;

  fetch('/api/logs/export/excel')
    .then(res => {
      if (!res.ok) return res.json().then(e => { throw new Error(e.error || 'Export failed'); });
      return res.blob();
    })
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `eHistorian_Export_${new Date().toISOString().replace(/[:.]/g,'-').slice(0,19)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      notify('Excel export downloaded!');
    })
    .catch(err => notify(err.message, true))
    .finally(() => {
      btn.innerHTML = origText;
      btn.disabled = false;
    });
}

// ── Navigation ──────────────────────────────────────────
function showPage(id, el) {
  document
    .querySelectorAll(".page")
    .forEach((p) => p.classList.remove("active"));
  document
    .querySelectorAll(".nav-item")
    .forEach((n) => n.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  if (el) el.classList.add("active");

  if (id === "config-view") renderConfigView();
  if (id === "statistics") pollStats();
}

// ── Status ────────────────────────────────────────────────
let _prevStatus = {};
function updateStatus() {
  fetch("/api/status")
    .then((r) => r.json())
    .then((data) => {
      ['gateway', 'fakegen', 'opcuaserver'].forEach(name => {
        setDot(name, data[name]);
        if (_prevStatus[name] !== undefined && _prevStatus[name] !== data[name]) {
          logActivity(`${name.charAt(0).toUpperCase()+name.slice(1)} ${data[name] ? 'started' : 'stopped'}`, data[name] ? 'process' : 'warn');
        }
        _prevStatus[name] = data[name];
      });
    })
    .catch(() => {});
}



function setDot(name, running) {
  const dot = document.getElementById(`${name}-dot`);
  const text = document.getElementById(`${name}-status`);
  if (!dot || !text) return;

  if (running) {
    dot.classList.add("running");
    text.classList.add("running");
    text.textContent = "Running";
  } else {
    dot.classList.remove("running");
    text.classList.remove("running");
    text.textContent = "Stopped";
  }
}

// ── Device IP ───────────────────────────────────────────
function fetchDeviceIp() {
  const el = document.getElementById("device-ip-status");
  if (el) el.textContent = "Loading...";
  fetch("/api/ip")
    .then((r) => r.json())
    .then((data) => {
      if (el) el.textContent = data.ip !== 'unknown' ? data.ip : "Error fetching IP";
    })
    .catch(() => {
      if (el) el.textContent = "Error";
    });
}

// ── Process Controls ──────────────────────────────────────
function processAction(name, action) {
  logActivity(`${capitalize(name)}: ${action === 'start' ? 'Starting...' : 'Stopping...'}`, 'process');
  fetch(`/api/processes/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  }).then((r) => r.json()).then(data => {
    if (data.status === 'error') logActivity(`${capitalize(name)}: ${data.message}`, 'error');
    setTimeout(updateStatus, action === "start" ? 1500 : 500);
  });
}


const startGateway = () => processAction("gateway", "start");
const stopGateway  = () => processAction("gateway", "stop");

// Fake Data Generator controls
const startFakegen = () => processAction("fakegen", "start");
const stopFakegen  = () => processAction("fakegen", "stop");

// OPC UA Simulator controls
const startOpcuaServer = () => processAction("opcuaserver", "start");
const stopOpcuaServer  = () => processAction("opcuaserver", "stop");

function toggleFakegenSettings() {
  const panel = document.getElementById("fakegen-settings");
  if (!panel) return;
  const visible = panel.style.display !== "none";
  panel.style.display = visible ? "none" : "block";
  if (!visible) loadFakegenConfig();
}

function parseFakegenConnStr(connStr) {
  const p = {};
  connStr.split(';').forEach(part => {
    const idx = part.indexOf('=');
    if (idx > 0) p[part.substring(0, idx).trim().toLowerCase()] = part.substring(idx + 1).trim();
  });
  return p;
}

function buildFakegenConnStr(server, database, uid, pwd) {
  return `Driver={ODBC Driver 18 for SQL Server};Server=${server};Database=${database};UID=${uid};PWD=${pwd};TrustServerCertificate=yes;Encrypt=yes;`;
}

function loadFakegenConfig() {
  fetch('/api/fakegen/config')
    .then(r => r.json())
    .then(cfg => {
      const p = parseFakegenConnStr(cfg.connectionString || '');
      const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
      set('fg-server',   p['server'] || '');
      set('fg-database', p['database'] || '');
      set('fg-uid',      p['uid'] || '');
      set('fg-pwd',      p['pwd'] || '');
      set('fg-table',    cfg.table || 'CurrentValues');
      set('fg-tagcol',   cfg.tagColumn || 'TagName');
      set('fg-interval', cfg.intervalSeconds || 10);
      set('fg-connstr-raw', cfg.connectionString || '');
      logActivity(`Fakegen config loaded — db: ${p['database']||'?'}, interval: ${cfg.intervalSeconds}s`, 'info');
    });
}

function saveFakegenConfig() {
  const get = id => document.getElementById(id)?.value || '';
  const rawConn = get('fg-connstr-raw');
  const connStr = rawConn || buildFakegenConnStr(get('fg-server'), get('fg-database'), get('fg-uid'), get('fg-pwd'));

  const cfg = {
    connectionString: connStr,
    table:            get('fg-table') || 'CurrentValues',
    tagColumn:        get('fg-tagcol') || 'TagName',
    valueColumn:      'Value',
    timestampColumn:  'UpdatedAt',
    intervalSeconds:  parseInt(get('fg-interval')) || 10,
    sensors: {
      Temperature: { base: 22.0,    noise: 1.5  },
      Pressure:    { base: 1013.25, noise: 10.0 },
      Flow:        { base: 50.0,    noise: 5.0  },
      Level:       { base: 75.0,    noise: 2.0  }
    }
  };

  fetch('/api/fakegen/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg)
  }).then(() => {
    notify('Fakegen config saved — changes apply on next cycle');
    logActivity(`Fakegen config saved (interval: ${cfg.intervalSeconds}s, table: ${cfg.table})`, 'ok');
  });
}

// ── Test ────────────────────────────────────────────────
function runTest() {
  logActivity('Sending test event...', 'info');
  fetch("/api/test", { method: "POST" })
    .then((r) => r.json())
    .then((data) => {
      if (data.status === "ok") {
        notify("Event sent successfully");
        logActivity('Test event sent successfully', 'ok');
        setTimeout(loadLogs, 1000);
      } else {
        notify("Error: " + data.message, true);
        logActivity('Test event failed: ' + data.message, 'error');
      }
    })
    .catch(() => { notify("Control server not running", true); logActivity('Server not reachable', 'error'); });
}


// ── Config Load/Save ────────────────────────────────────
function loadConfig() {
  fetch("/api/config")
    .then((r) => r.json())
    .then((config) => {
      currentConfig = config;
      document.getElementById("gatewayId").value = config.gatewayId || "";
      document.getElementById("apiUrl").value = config.apiUrl || "";
      const bufferInput = document.getElementById("offlineBufferMaxBytes");
      if (bufferInput) bufferInput.value = config.offlineBufferMaxBytes || 10485760;
      renderSources();
      logActivity(`Config loaded: GW=${config.gatewayId}, SQL=${(config.sql||[]).length}, OPC UA=${(config.opcua||[]).length}`, 'info');
    })
    .catch(() => {});
}

function saveConfig() {
  currentConfig.gatewayId = document.getElementById("gatewayId").value;
  currentConfig.apiUrl = document.getElementById("apiUrl").value;
  const bufferInput = document.getElementById("offlineBufferMaxBytes");
  if (bufferInput && bufferInput.value) {
    currentConfig.offlineBufferMaxBytes = parseInt(bufferInput.value, 10);
  }

  fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentConfig),
  }).then(() => {
    notify("Configuration saved");
    logActivity(`Config saved (${currentConfig.sql.length} SQL, ${currentConfig.opcua.length} OPC UA)`, 'ok');
  });
}

// ── OPC UA ──────────────────────────────────────────────
function addOpcUa() {
  currentConfig.opcua.push({
    assetId: 101,
    url: "opc.tcp://localhost:4840",
    samplingMs: 1000,
    tags: [],
  });
  renderSources();
}

function removeOpcUa(i) {
  currentConfig.opcua.splice(i, 1);
  renderSources();
  saveConfig();
}

// ── SQL ──────────────────────────────────────────────────
function addSql() {
  currentConfig.sql.push({
    assetId: 201,
    connectionString: "Driver={ODBC Driver 18 for SQL Server};Server=tcp:efactory-server.database.windows.net,1433;Database=eFactory;Uid=dbadmin;Pwd=Password123;Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=30;",
    table: "CurrentValues",
    tagColumn: "TagName",
    valueColumn: "Value",
    timestampColumn: "UpdatedAt",
    pollingMs: 5000,
    onChange: 1,
  });
  renderSources();
}

function removeSql(i) {
  currentConfig.sql.splice(i, 1);
  renderSources();
  saveConfig();
}

function fixSqlDrivers() {
  const btn = document.getElementById("fix-drivers-btn");
  if (btn) btn.textContent = "Opravuji...";
  
  fetch("/api/config/fix-drivers", { method: "POST" })
    .then(r => r.json())
    .then(data => {
      if (btn) btn.textContent = "Opravit SQL Ovladače";
      if (data.status === "ok") {
        alert("Konfigurace byla úspěšně upravena! Restartuji SQL poller...");
        loadConfig();
        processAction("gateway", "start");
      } else {
        alert("Chyba při opravě ovladačů: " + data.message);
      }
    })
    .catch(err => {
      if (btn) btn.textContent = "Opravit SQL Ovladače";
      alert("Nepodařilo se zavolat API: " + err);
    });
}

// ── SQL Connection String Helper ────────────────────────
function updateSqlConnStr(i, key, val) {
  const src = currentConfig.sql[i];
  let params = {};
  if (src.connectionString) {
    src.connectionString.split(';').forEach(p => {
      const idx = p.indexOf('=');
      if (idx > 0) {
        params[p.substring(0, idx).trim()] = p.substring(idx + 1).trim();
      }
    });
  }
  
  if (val === '') {
    delete params[key];
  } else {
    params[key] = val;
  }
  
  src.connectionString = Object.entries(params)
    .map(([k, v]) => `${k}=${v}`)
    .join(';') + (Object.keys(params).length > 0 ? ';' : '');
    
  saveConfig();
  renderSources();
}

// ── Render Sources ──────────────────────────────────────
function renderSources() {
  const opcList = document.getElementById("opcua-list");
  const sqlList = document.getElementById("sql-list");

  if (currentConfig.opcua.length === 0) {
    opcList.innerHTML = `<div class="empty-state">No OPC UA sources configured</div>`;
  } else {
    opcList.innerHTML = currentConfig.opcua
      .map(
        (src, i) => `
      <div class="source-item">
        <div class="source-item-header">
          <span class="source-tag">OPC UA — Asset ${src.assetId}</span>
          <button class="btn-danger" onclick="removeOpcUa(${i})">Remove</button>
        </div>
        <div class="grid-2">
          <div class="form-row">
            <label>Asset ID</label>
            <input type="number" value="${src.assetId}"
              onchange="currentConfig.opcua[${i}].assetId=parseInt(this.value); saveConfig();">
          </div>
          <div class="form-row">
            <label>Sampling (ms)</label>
            <input type="number" value="${src.samplingMs}"
              onchange="currentConfig.opcua[${i}].samplingMs=parseInt(this.value); saveConfig();">
          </div>
        </div>
        <div class="form-row">
          <label>Endpoint URL</label>
          <input type="text" value="${src.url}"
            onchange="currentConfig.opcua[${i}].url=this.value; saveConfig();">
        </div>
        <div class="form-row">
          <label>Tags (comma separated)</label>
          <input type="text" value="${src.tags.join(", ")}"
            onchange="currentConfig.opcua[${i}].tags=this.value.split(',').map(t=>t.trim()).filter(Boolean); saveConfig();">
        </div>
      </div>
    `,
      )
      .join("");
  }

  if (currentConfig.sql.length === 0) {
    sqlList.innerHTML = `<div class="empty-state">No SQL sources configured</div>`;
  } else {
    sqlList.innerHTML = currentConfig.sql
      .map((src, i) => {
        let params = {};
        if (src.connectionString) {
          src.connectionString.split(';').forEach(p => {
            const idx = p.indexOf('=');
            if (idx > 0) params[p.substring(0, idx).trim()] = p.substring(idx + 1).trim();
          });
        }
        return `
      <div class="source-item">
        <div class="source-item-header">
          <span class="source-tag">SQL — Asset ${src.assetId}</span>
          <button class="btn-danger" onclick="removeSql(${i})">Remove</button>
        </div>
        <div class="grid-3">
          <div class="form-row">
            <label>Asset ID</label>
            <input type="number" value="${src.assetId}"
              onchange="currentConfig.sql[${i}].assetId=parseInt(this.value); saveConfig();">
          </div>
          <div class="form-row">
            <label>Polling (ms)</label>
            <input type="number" value="${src.pollingMs}"
              onchange="currentConfig.sql[${i}].pollingMs=parseInt(this.value); saveConfig();">
          </div>
          <div class="form-row">
            <label>Only Changes</label>
            <select onchange="currentConfig.sql[${i}].onChange=parseInt(this.value); saveConfig();">
              <option value="1" ${src.onChange !== 0 ? 'selected' : ''}>Yes (1)</option>
              <option value="0" ${src.onChange === 0 ? 'selected' : ''}>No (0)</option>
            </select>
          </div>
        </div>
        <div class="grid-2">
          <div class="form-row">
            <label>Server</label>
            <input type="text" value="${params['Server'] || ''}" onchange="updateSqlConnStr(${i}, 'Server', this.value)">
          </div>
          <div class="form-row">
            <label>Database</label>
            <input type="text" value="${params['Database'] || ''}" onchange="updateSqlConnStr(${i}, 'Database', this.value)">
          </div>
          <div class="form-row">
            <label>User (Uid)</label>
            <input type="text" value="${params['Uid'] || ''}" onchange="updateSqlConnStr(${i}, 'Uid', this.value)">
          </div>
          <div class="form-row">
            <label>Password (Pwd)</label>
            <input type="password" value="${params['Pwd'] || ''}" onchange="updateSqlConnStr(${i}, 'Pwd', this.value)">
          </div>
        </div>
        <details style="margin-bottom: 12px;">
          <summary style="cursor: pointer; font-size: 11px; color: var(--accent); font-family: var(--mono); margin-bottom: 8px;">Advanced: Raw Connection String</summary>
          <div class="form-row">
            <input type="text" value="${src.connectionString}"
              onchange="currentConfig.sql[${i}].connectionString=this.value; saveConfig(); renderSources();">
          </div>
        </details>
        <div class="grid-3">
          <div class="form-row">
            <label>Table</label>
            <input type="text" value="${src.table}"
              onchange="currentConfig.sql[${i}].table=this.value; saveConfig();">
          </div>
          <div class="form-row">
            <label>Tag Column</label>
            <input type="text" value="${src.tagColumn}"
              onchange="currentConfig.sql[${i}].tagColumn=this.value; saveConfig();">
          </div>
          <div class="form-row">
            <label>Value Column</label>
            <input type="text" value="${src.valueColumn}"
              onchange="currentConfig.sql[${i}].valueColumn=this.value; saveConfig();">
          </div>
        </div>
        <div class="form-row">
          <label>Timestamp Column</label>
          <input type="text" value="${src.timestampColumn}"
            onchange="currentConfig.sql[${i}].timestampColumn=this.value; saveConfig();">
        </div>
      </div>
    `;
      })
      .join("");
  }
}

// ── Config Viewer ───────────────────────────────────────
function renderConfigView() {
  const el = document.getElementById("config-json");
  if (!el) return;
  el.innerHTML = syntaxHighlight(JSON.stringify(currentConfig, null, 2));
}

function refreshConfigView() {
  fetch("/api/config")
    .then((r) => r.json())
    .then((config) => {
      currentConfig = config;
      renderConfigView();
      notify("Configuration refreshed");
    })
    .catch(() => notify("Failed to fetch configuration", true));
}

function downloadConfig() {
  const json = JSON.stringify(currentConfig, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "ehistorian.config.json";
  a.click();
  URL.revokeObjectURL(url);
  notify("Config downloaded");
}

function copyConfig() {
  const json = JSON.stringify(currentConfig, null, 2);
  navigator.clipboard
    .writeText(json)
    .then(() => notify("Copied to clipboard"))
    .catch(() => notify("Copy failed", true));
}

function syntaxHighlight(json) {
  return json
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      (match) => {
        let cls = "json-num";
        if (/^"/.test(match)) cls = /:$/.test(match) ? "json-key" : "json-str";
        else if (/true|false/.test(match)) cls = "json-bool";
        else if (/null/.test(match)) cls = "json-null";
        return `<span class="${cls}">${match}</span>`;
      },
    );
}

// ── Logs ────────────────────────────────────────────────
let currentLogData = null;
let currentLogFilename = "";

function loadLogs() {
  fetch("/api/logs")
    .then((r) => r.json())
    .then((logs) => {
      const el = document.getElementById("logs-list");
      if (logs.length === 0) {
        el.innerHTML = `<div class="empty-state">No log files found</div>`;
        return;
      }
      el.innerHTML = logs
        .map((log) => {
          const time = new Date(log.timestamp).toLocaleString("cs-CZ");
          return `
          <div class="log-item">
            <div>
              <div class="log-name">${log.name}</div>
              <div class="log-time">${time}</div>
            </div>
            <div class="btn-group">
              <button class="btn-ghost" onclick="viewLog('${log.name}')">View</button>
              <button class="btn-danger" onclick="deleteLog('${log.name}')">Delete</button>
            </div>
          </div>
        `;
        })
        .join("");
    })
    .catch(() => {});
}

function viewLog(filename) {
  logActivity(`Opening log: ${filename}`, 'info');
  fetch(`/api/log/${filename}`)
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      currentLogData = data;
      currentLogFilename = filename;
      const events = data.events || [];
      document.getElementById("log-viewer-card").style.display = "block";
      document.getElementById("log-viewer-title").textContent = "Log Details";
      document.getElementById("log-viewer-subtitle").textContent = `${filename} — ${events.length} event(s)`;
      setLogViewMode('table');
      logActivity(`Log opened: ${filename} (${events.length} events, GW: ${data.gatewayId||'?'})`, 'ok');
      // Scroll viewer into view
      document.getElementById("log-viewer-card").scrollIntoView({ behavior: 'smooth', block: 'start' });
    })
    .catch(e => {
      console.error("Failed to load log:", e);
      notify("Failed to load log: " + e.message, true);
      logActivity(`Failed to open log: ${filename} (${e.message})`, 'error');
    });
}

function closeLogViewer() {
  document.getElementById("log-viewer-card").style.display = "none";
  currentLogData = null;
  currentLogFilename = "";
}

function setLogViewMode(mode) {
  const btnJson = document.getElementById("btn-view-json");
  const btnTable = document.getElementById("btn-view-table");
  const elJson = document.getElementById("log-viewer-json");
  const elTable = document.getElementById("log-viewer-table");

  if (mode === 'json') {
    btnJson.className = "btn-primary";
    btnTable.className = "btn-ghost";
    elJson.style.display = "block";
    elTable.style.display = "none";
    elJson.innerHTML = syntaxHighlight(JSON.stringify(currentLogData, null, 2));
  } else {
    btnJson.className = "btn-ghost";
    btnTable.className = "btn-primary";
    elJson.style.display = "none";
    elTable.style.display = "block";
    elTable.innerHTML = generateLogTable(currentLogData);
  }
}

function generateLogTable(data) {
  if (!data) return "No data";
  let html = `<table class="log-table">`;
  
  if (data.events && Array.isArray(data.events)) {
    // Ingest log format
    html += `<thead><tr>
      <th>Gateway ID</th>
      <th>Asset ID</th>
      <th>Source</th>
      <th>Source ID</th>
      <th>Tag</th>
      <th>Value</th>
      <th>Quality</th>
      <th>Timestamp</th>
    </tr></thead><tbody>`;
    data.events.forEach(ev => {
      html += `<tr>
        <td><span class="source-tag" style="background:var(--surface); color:var(--text); border:1px solid var(--border-light);">${ev.gatewayId || ''}</span></td>
        <td><span style="font-weight:bold; color:var(--text);">${ev.assetId || ''}</span></td>
        <td>${ev.source || ''}</td>
        <td>${ev.sourceId || ''}</td>
        <td><span class="source-tag">${ev.tag || ''}</span></td>
        <td style="font-weight: 600; color: var(--accent); font-size: 14px;">${ev.value !== undefined ? ev.value : ''}</td>
        <td><span style="color: ${ev.quality === 'Good' ? 'var(--success)' : 'var(--danger)'};">${ev.quality || ''}</span></td>
        <td style="color: var(--text-muted); font-size: 11px;">${ev.timestamp || ''}</td>
      </tr>`;
    });
    html += `</tbody>`;
  } else {
    // Generic table for any JSON object
    html += `<thead><tr><th>Property</th><th>Value</th></tr></thead><tbody>`;
    for (const key in data) {
      const val = typeof data[key] === 'object' ? JSON.stringify(data[key]) : data[key];
      html += `<tr><td>${key}</td><td>${val}</td></tr>`;
    }
    html += `</tbody>`;
  }
  html += `</table>`;
  return html;
}

function deleteLog(filename) {
  if (!confirm(`Delete log: ${filename}?`)) return;
  fetch(`/api/log/${filename}`, { method: "DELETE" }).then(() => {
    notify("Log deleted");
    logActivity(`Log deleted: ${filename}`, 'warn');
    if (currentLogFilename === filename) closeLogViewer();
    loadLogs();
  });
}

function clearAllLogs() {
  if (!confirm("Delete ALL log files? This cannot be undone.")) return;
  fetch("/api/logs/clear", { method: "POST" })
    .then(r => r.json())
    .then(data => {
      notify("All logs cleared");
      logActivity(`All logs cleared (${data.deleted || 0} files deleted)`, 'warn');
      closeLogViewer();
      loadLogs();
    });
}

// ── Utilities ───────────────────────────────────────────
function notify(msg, isError = false) {
  const el = document.createElement("div");
  el.className = "notification" + (isError ? " error" : "");
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

// ── Statistics ──────────────────────────────────────────
const TAG_BAR_COLORS = [
  '#3b82f6', '#8b5cf6', '#10b981', '#f59e0b',
  '#ef4444', '#06b6d4', '#ec4899', '#84cc16'
];

function pollStats() {
  fetch('/api/stats')
    .then(r => r.json())
    .then(data => {
      // Card 1: Total events
      const el = (id) => document.getElementById(id);
      el('stat-total-events').textContent = data.totalIngestedEvents.toLocaleString();
      el('stat-throughput').textContent = `${data.throughputPerMin} událostí/min`;

      // Card 2: Log files
      el('stat-log-files').textContent = data.logFilesCount.toLocaleString();
      el('stat-log-size').textContent = data.logFilesSizeReadable;

      // Card 3: Error rate
      el('stat-errors').textContent = data.failedRequests.toLocaleString();
      const errPct = data.totalRequests > 0
        ? ((data.failedRequests / data.totalRequests) * 100).toFixed(1)
        : 0;
      el('stat-error-rate').textContent = `${errPct}% chyb`;

      // Swap icon color on errors
      const errIcon = el('stat-error-icon');
      if (errIcon) {
        if (data.failedRequests > 0) {
          errIcon.style.background = 'var(--danger-glow)';
          errIcon.style.color = 'var(--danger)';
        } else {
          errIcon.style.background = 'var(--success-glow)';
          errIcon.style.color = 'var(--success)';
        }
      }

      // Card 4: Active tags
      el('stat-active-tags').textContent = data.activeTagsCount;

      // Secondary metrics
      el('stat-uptime').textContent = formatUptime(data.serverUptimeStart);
      el('stat-latency').textContent = data.avgLatencyMs > 0 ? `${data.avgLatencyMs} ms` : '— ms';
      el('stat-total-requests').textContent = data.totalRequests.toLocaleString();

      // Last known values table
      renderStatsTagTable(data.lastKnownValues);

      // Tag distribution bars
      renderTagBars(data.tagDistribution);
    })
    .catch(() => {});
}

function formatUptime(startIso) {
  try {
    const started = new Date(startIso);
    const now = new Date();
    let diff = Math.floor((now - started) / 1000);
    if (diff < 0) diff = 0;

    const days = Math.floor(diff / 86400);
    diff %= 86400;
    const hours = Math.floor(diff / 3600);
    diff %= 3600;
    const mins = Math.floor(diff / 60);
    const secs = diff % 60;

    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    parts.push(`${mins}m`);
    parts.push(`${secs}s`);
    return parts.join(' ');
  } catch {
    return '—';
  }
}

function renderStatsTagTable(lastKnownValues) {
  const container = el('stats-tags-table');
  if (!container) return;

  const tags = Object.keys(lastKnownValues || {});
  if (tags.length === 0) {
    container.innerHTML = '<div class="empty-state">Zatím žádná data — čekám na příchozí události...</div>';
    return;
  }

  let html = `<table class="stats-sensor-table">
    <thead><tr>
      <th>Tag / Senzor</th>
      <th>Hodnota</th>
      <th>Kvalita</th>
      <th>Poslední aktualizace</th>
    </tr></thead><tbody>`;

  tags.forEach(tag => {
    const info = lastKnownValues[tag];
    const val = typeof info.value === 'number' ? info.value.toFixed(2) : info.value;
    const qualityClass = info.quality === 'Good' ? 'sensor-quality-good' : 'sensor-quality-bad';
    const ts = info.timestamp ? new Date(info.timestamp).toLocaleString('cs-CZ') : '—';

    html += `<tr>
      <td><span class="source-tag">${tag}</span></td>
      <td class="sensor-value">${val}</td>
      <td><span class="${qualityClass}">${info.quality || '—'}</span></td>
      <td class="sensor-ts">${ts}</td>
    </tr>`;
  });

  html += '</tbody></table>';
  container.innerHTML = html;

  function el(id) { return document.getElementById(id); }
}

function renderTagBars(tagDistribution) {
  const container = document.getElementById('stats-tag-bars');
  if (!container) return;

  const tags = Object.entries(tagDistribution || {});
  if (tags.length === 0) {
    container.innerHTML = '<div class="empty-state">Zatím žádná data...</div>';
    return;
  }

  const maxCount = Math.max(...tags.map(([, c]) => c), 1);

  container.innerHTML = tags.map(([name, count], i) => {
    const pct = Math.max((count / maxCount) * 100, 2);
    const color = TAG_BAR_COLORS[i % TAG_BAR_COLORS.length];
    return `
      <div class="tag-bar-row">
        <span class="tag-bar-name">${name}</span>
        <div class="tag-bar-track">
          <div class="tag-bar-fill" style="width:${pct}%; background:${color};"></div>
        </div>
        <span class="tag-bar-count">${count.toLocaleString()}×</span>
      </div>
    `;
  }).join('');
}

// ── TEST ONLY: CAN BE EASILY DELETED ──
let simulatedOutageEnabled = false;

function updateOutageAndBufferStatus() {
  // Fetch simulated outage status
  fetch('/api/simulate-outage')
    .then(r => r.json())
    .then(data => {
      simulatedOutageEnabled = data.enabled;
      const statusEl = document.getElementById('outage-simulation-status');
      const btnEl = document.getElementById('toggle-outage-btn');
      if (statusEl && btnEl) {
        if (simulatedOutageEnabled) {
          statusEl.textContent = "ACTIVE (Server is Down)";
          statusEl.style.color = "var(--danger)";
          btnEl.textContent = "Restore Server Connection";
          btnEl.className = "btn-success btn-full";
        } else {
          statusEl.textContent = "Inactive (Server is Online)";
          statusEl.style.color = "var(--success)";
          btnEl.textContent = "Simulate Server Outage";
          btnEl.className = "btn-danger btn-full";
        }
      }
    })
    .catch(() => {});

  // Fetch gateway buffer status
  fetch('/api/ehistorian/gateway/buffer-status')
    .then(r => r.json())
    .then(data => {
      const sizeEl = document.getElementById('outage-buffer-size');
      const countEl = document.getElementById('outage-buffer-count');
      const barEl = document.getElementById('outage-buffer-bar');
      const maxBytes = data.maxBytes || 5000;
      const usedBytes = data.bytesSize || 0;
      const pct = Math.min(100, Math.round((usedBytes / maxBytes) * 100));

      if (sizeEl) {
        const formatBytes = (bytes) => {
          if (bytes === 0) return '0 B';
          const k = 1024;
          const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
          const i = Math.floor(Math.log(bytes) / Math.log(k));
          return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        };
        const label = formatBytes(usedBytes);
        const maxLabel = formatBytes(maxBytes);
        sizeEl.textContent = `${label} / ${maxLabel} (${pct}%)`;
        sizeEl.style.color = pct >= 100 ? 'var(--danger)' : pct >= 75 ? 'var(--warning)' : 'var(--success)';
      }
      if (countEl) {
        countEl.textContent = data.pendingCount;
      }
      if (barEl) {
        barEl.style.width = `${pct}%`;
        barEl.style.background = pct >= 100 ? 'var(--danger)' : pct >= 75 ? 'var(--warning)' : 'var(--success)';
      }
    })
    .catch(() => {});
}

function toggleSimulatedOutage() {
  fetch('/api/simulate-outage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: !simulatedOutageEnabled })
  })
  .then(r => r.json())
  .then(data => {
    updateOutageAndBufferStatus();
    notify(data.enabled ? "Server outage simulation started" : "Server connection restored");
  })
  .catch(() => {});
}
// ── END TEST ONLY ──

