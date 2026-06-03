eHistorian Gateway - Linux Deployment Guide (Docker)
=====================================================

This folder contains a fully self-contained containerized client for the eHistorian system. It collects data from OPC UA and SQL sources, stores it in a local SQLite queue buffer, and forwards it to the central server.

System Requirements:
- Linux OS (or Windows/macOS running Docker Desktop)
- Docker & Docker Compose

Deployment Instructions:
------------------------

1. Copy/Extract this folder onto your target server.

2. Open your terminal and change to this directory:
   $ cd eHistorian.Gateway

3. Edit the bootstrap configuration file to set your gateway's identifier and central API endpoint URL:
   $ nano bootstrap.config.json

   Example:
   {
     "gatewayId": "line-01-gateway",
     "apiUrl": "http://your-central-ehistorian-server-ip:5000"
   }

4. Build and start the container in detached (background) mode:
   $ docker compose up -d

   This will build the Python image, install the required Microsoft ODBC Driver 18, and start the gateway service.

5. Verify that the gateway is running and check output logs:
   $ docker compose logs -f

6. Query the container's built-in health check endpoint:
   $ curl http://localhost:8088/health

Directory Structure:
--------------------
- ehistorian_gateway/ : Core Python codebase of the client.
- Dockerfile          : Configures python-slim image + msodbcsql18 compiler environments.
- docker-compose.yml  : Configures container services, port maps, and volumes.
- requirements.txt    : Required Python libraries (aiosqlite, asyncua, pyodbc).
- data/               : Mount directory for local offline-buffer SQLite database persistence.
- cache/              : Mount directory for local log backups and configuration history cache.
