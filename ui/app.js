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
  loadConfig();
  loadLogs();
  fetchDeviceIp();
});

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
}

// ── Status ──────────────────────────────────────────────
function updateStatus() {
  fetch("/api/status")
    .then((r) => r.json())
    .then((data) => {
      setDot("gateway", data.gateway);
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

// ── Process Controls ────────────────────────────────────
function processAction(name, action) {
  fetch(`/api/processes/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  }).then(() => {
    notify(
      action === "start"
        ? `${capitalize(name)} starting...`
        : `${capitalize(name)} stopping...`,
    );
    setTimeout(updateStatus, action === "start" ? 1500 : 500);
  });
}


const startGateway = () => processAction("gateway", "start");
const stopGateway = () => processAction("gateway", "stop");

// ── Test ────────────────────────────────────────────────
function runTest() {
  fetch("/api/test", { method: "POST" })
    .then((r) => r.json())
    .then((data) => {
      if (data.status === "ok") {
        notify("Event sent successfully");
        setTimeout(loadLogs, 1000);
      } else {
        notify("Error: " + data.message, true);
      }
    })
    .catch(() => notify("Control server not running", true));
}

// ── Config Load/Save ────────────────────────────────────
function loadConfig() {
  fetch("/api/config")
    .then((r) => r.json())
    .then((config) => {
      currentConfig = config;
      document.getElementById("gatewayId").value = config.gatewayId || "";
      document.getElementById("apiUrl").value = config.apiUrl || "";
      renderSources();
    })
    .catch(() => {});
}

function saveConfig() {
  currentConfig.gatewayId = document.getElementById("gatewayId").value;
  currentConfig.apiUrl = document.getElementById("apiUrl").value;

  fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentConfig),
  }).then(() => notify("Configuration saved"));
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
        <div class="grid-2">
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
  fetch(`/api/log/${filename}`)
    .then(r => r.json())
    .then(data => {
      currentLogData = data;
      currentLogFilename = filename;
      document.getElementById("log-viewer-card").style.display = "block";
      document.getElementById("log-viewer-subtitle").textContent = filename;
      setLogViewMode('json');
    })
    .catch(() => notify("Failed to load log details", true));
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
    loadLogs();
  });
}

function clearAllLogs() {
  if (!confirm("Delete ALL log files? This cannot be undone.")) return;
  fetch("/api/logs/clear", { method: "POST" }).then(() => {
    notify("All logs cleared");
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
