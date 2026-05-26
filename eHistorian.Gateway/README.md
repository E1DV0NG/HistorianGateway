# eHistorian Gateway

`eHistorian Gateway` is a standalone async edge gateway for OPC UA subscriptions, SQL Server polling, local offline buffering, and batched forwarding into `eFactory.Api`.

Each configured source is bound to an `assetId`, so a single gateway instance can collect data for multiple assets without any extra plugin or mapping layer.

## Features

- Async OPC UA subscriptions with reconnect and `Security=None`
- Async SQL snapshot polling via `pyodbc` wrapped in `asyncio.to_thread`
- Unified event normalization across OPC UA and SQL
- Bounded in-memory queue with backpressure
- SQLite-backed offline batch persistence with replay after restart
- Batch REST sender with exponential backoff and jitter
- Hot-reload configuration from `GET /api/ehistorian/gateway/config/{gatewayId}` every 30 seconds
- JSON structured logging
- Built-in health endpoint on `GET /health`

## Bootstrap configuration

The gateway needs a local bootstrap JSON file with at least `gatewayId` and `apiUrl`. The same file can also contain a full fallback runtime config for cold start when the API is unavailable.

For multi-asset operation, every OPC UA and SQL source entry must include `assetId`. Reuse the same OPC UA server URL multiple times when one gateway serves several assets.

OPC UA sampling is configured per source with `samplingMs`. Example: `samplingMs: 1000` means sampling every 1 second. If omitted, the default is `1000` ms.

SQL polling frequency is configured per SQL source with `pollingMs`. Example: `pollingMs: 5000` means polling every 5 seconds. If omitted, the default is `2000` ms.

Example: [example.config.json](example.config.json)

## Run on Windows

```powershell
cd eHistorian.Gateway
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:EHG_BOOTSTRAP_CONFIG = (Resolve-Path .\example.config.json)
python -m ehistorian_gateway.main
```

## Run on Linux

```bash
cd eHistorian.Gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export EHG_BOOTSTRAP_CONFIG=$(pwd)/example.config.json
python -m ehistorian_gateway.main
```

## systemd example

```ini
[Unit]
Description=eHistorian Gateway
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/opt/ehistorian-gateway
Environment=EHG_BOOTSTRAP_CONFIG=/opt/ehistorian-gateway/config/bootstrap.json
Environment=EHG_SQLITE_PATH=/var/lib/ehistorian-gateway/offline-buffer.db
ExecStart=/opt/ehistorian-gateway/.venv/bin/python -m ehistorian_gateway.main
Restart=always
RestartSec=5
User=emonitor
Group=emonitor

[Install]
WantedBy=multi-user.target
```

## Docker

```bash
cd eHistorian.Gateway
docker build -t ehistorian-gateway .
docker run --rm -p 8088:8088 \
  -e EHG_BOOTSTRAP_CONFIG=/app/example.config.json \
  -e EHG_SQLITE_PATH=/data/offline-buffer.db \
  -v $(pwd)/example.config.json:/app/example.config.json:ro \
  -v ehistorian_gateway_data:/data \
  ehistorian-gateway
```

## REST contracts used

- Config: `GET {apiUrl}/api/ehistorian/gateway/config/{gatewayId}`
- Ingest: `POST {apiUrl}/api/ehistorian/gateway/ingest`

## Ingest payload

The gateway sends batched events to `POST {apiUrl}/api/ehistorian/gateway/ingest`.

Request body:

```json
{
  "gatewayId": "line-01-secret",
  "events": [
    {
      "gatewayId": "line-01-secret",
      "assetId": 101,
      "source": "opcua",
      "sourceId": "opcua-0:asset-101",
      "tag": "ns=2;s=Temperature",
      "value": 24.7,
      "timestamp": "2026-05-25T10:15:30Z",
      "quality": "Good"
    },
    {
      "gatewayId": "line-01-secret",
      "assetId": 201,
      "source": "sql",
      "sourceId": "sql-0:asset-201:CurrentValues",
      "tag": "PumpState",
      "value": true,
      "timestamp": "2026-05-25T10:15:31Z",
      "quality": "Good"
    }
  ]
}
```

Field meaning:

- `gatewayId`: identifier of the gateway instance.
- `events`: batch of normalized historian events.
- `assetId`: target asset for this event. This is the routing key on the API side.
- `source`: `opcua` or `sql`.
- `sourceId`: unique source instance inside the gateway.
- `tag`: measurement point name or OPC UA node id.
- `value`: scalar value sent as JSON number, string, boolean, or timestamp string.
- `timestamp`: UTC event time.
- `quality`: `Good`, `Bad`, or `Uncertain`.

Behavior:

- The gateway sends batches, not single events.
- API rejects the request if `gatewayId` is missing, `events` is empty, batch size is over `1000`, or any event has invalid `assetId`.
- Unknown tags are auto-created as measurement points for the given `assetId` when auto-create is enabled on the API.
- The gateway retries failed batches and keeps them in local SQLite storage until delivery succeeds.

Successful response example:

```json
{
  "gatewayId": "line-01-secret",
  "acceptedCount": 2,
  "rejectedCount": 0,
  "status": "Accepted",
  "timestamp": "2026-05-25T10:15:32Z"
}
```

## Notes

- SQL identifiers are intentionally restricted to simple table/column names to keep deployment and validation predictable.
- `assetId` is the routing key for historian writes. Gateway config owns the asset assignment; the server-side `tbEmGatewayConfig` row is now only the tenant-scoped container for the config document.
- `quality` is preserved end-to-end in the gateway payload and stored server-side as event metadata by the API implementation added in this repo.
