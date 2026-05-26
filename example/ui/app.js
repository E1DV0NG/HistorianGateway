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
      setDot("server", data.server);
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

const startServer = () => processAction("server", "start");
const stopServer = () => processAction("server", "stop");
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
    connectionString: "",
    table: "",
    tagColumn: "",
    valueColumn: "",
    timestampColumn: "",
    pollingMs: 5000,
  });
  renderSources();
}

function removeSql(i) {
  currentConfig.sql.splice(i, 1);
  renderSources();
  saveConfig();
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
      .map(
        (src, i) => `
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
        <div class="form-row">
          <label>Connection String</label>
          <input type="text" value="${src.connectionString}"
            onchange="currentConfig.sql[${i}].connectionString=this.value; saveConfig();">
        </div>
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
    `,
      )
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
            <button class="btn-danger" onclick="deleteLog('${log.name}')">Delete</button>
          </div>
        `;
        })
        .join("");
    })
    .catch(() => {});
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
