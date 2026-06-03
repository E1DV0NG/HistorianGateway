eHistorian Gateway — Deployment & Run Guide
===========================================

Purpose
-------
This document explains how to deploy and run the eHistorian Gateway release provided as a ZIP, and includes quick PowerShell and Docker commands for smoke tests, monitoring guidance, and rollback steps.

Prerequisites
-------------
- Target host (Windows or Linux) with network access to required endpoints.
- Python 3.11+ (recommended) or Docker.
- Ports: default HTTP 5000 (changeable via config).
- Permissions to create directories and write logs.

Contents of the release
-----------------------
The ZIP release contains:
- `server.py` (entry point) and package `ehistorian_gateway/`
- `requirements.txt`
- `configs/` folder with `default.json`
- `logs/` folder (runtime)
- `Dockerfile` (optional — buildable image)

Unpack and run (Windows, PowerShell)
-----------------------------------
1) Extract the ZIP to the target folder.
2) Create and activate a virtual environment and install dependencies:

```powershell
cd C:\path\to\eHistorian.Gateway
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3) Configure `configs/default.json` as needed (DB, cache, ports). You can also mount external `configs/` and `logs/` directories.

4) Start the gateway (dev/test):

```powershell
# From repo root
python server.py
# or
python -m ehistorian_gateway.main
```

5) Verify health and smoke test (PowerShell):

```powershell
# simple smoke payload
$payload = @{ gatewayId='smoke'; events=@(@{gatewayId='smoke'; assetId=1; tag='T1'; value=1.23; timestamp=(Get-Date).ToString('o'); quality='Good'}) } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri http://localhost:5000/api/ehistorian/gateway/ingest -Method Post -Body $payload -ContentType 'application/json'
```

Docker: build & run (preferred for production)
---------------------------------------------
1) Build the image from the included `Dockerfile`:

```bash
docker build -t ehistorian-gateway:latest eHistorian.Gateway/
```

2) Run the container with mounted host dirs for logs/configs:

```bash
docker run -d --name ehist -p 5000:5000 \
  -v /host/path/logs:/app/logs \
  -v /host/path/configs:/app/configs \
  ehistorian-gateway:latest
```

3) Verify the container is healthy and respond to the smoke test as above.

Running as a service (Windows)
------------------------------
For production on Windows, use an installer like `nssm` or Windows Service wrapper to run `python server.py` as a service under a dedicated account. Example with `nssm`:

```powershell
nssm install eHistorianGateway "C:\path\to\.venv\Scripts\python.exe" "C:\path\to\server.py"
nssm set eHistorianGateway AppDirectory C:\path\to
nssm start eHistorianGateway
```

Monitoring & Logging
--------------------
- Logs: write to `logs/` (rotate or ship to central log store).
- Metrics to collect: RPS, throughput (events/sec), p95 latency, total_ingested_events, failed_requests, memory usage.
- Suggested stack: Prometheus (metrics) + Grafana (dashboards) and filebeat/ELK or another centralized log shipper.
- Alerts: failed_requests > 0, p95 latency above SLA, steady memory increase.

Rollback & Releases
-------------------
- Keep versioned ZIPs or Docker image tags.
- For ZIP deploy: stop service/container, restore previous folder (or re-extract previous ZIP), restart.
- For Docker: `docker stop ehist && docker rm ehist && docker run <previous-image-tag>`

Security & Hardening
--------------------
- Run under a dedicated low-privilege user.
- Limit network ingress to required endpoints and port(s).
- Secure config files that contain credentials.

Troubleshooting checklist
-------------------------
- Gateway not listening: check `server.py` logs; confirm port binding and firewall rules.
- Requests failing: inspect `logs/ingest_*.json` and `stats_snapshot.json`.
- High latency: check CPU, memory, and I/O; look for GC pauses or blocking I/O.

Notes
-----
- The included test scripts were used for validation; production release has tests removed from `tests/` to keep the package clean. If you want the original stress tests preserved, consider keeping them in a separate `tests-release/` archive or CI job.

Contact
-------
For deployment assistance, monitoring dashboards, or to build a production Docker image, ask me and I can create the image and a simple systemd/Service manifest for your environment.
