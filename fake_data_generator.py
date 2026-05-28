import time
import random
import json
import os
import sys
import pyodbc
from datetime import datetime, timezone


def load_config() -> dict:
    """Načte konfiguraci z JSON souboru (cesta z env) nebo vrátí výchozí hodnoty."""
    config_path = os.environ.get("FAKEGEN_CONFIG")
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "connectionString": (
            "Driver={ODBC Driver 18 for SQL Server};"
            "Server=localhost;"
            "Database=eFactory;"
            "UID=sa;"
            "PWD=YourStrong!Passw0rd;"
            "TrustServerCertificate=yes;"
        ),
        "table": "CurrentValues",
        "tagColumn": "TagName",
        "valueColumn": "Value",
        "timestampColumn": "UpdatedAt",
        "intervalSeconds": 10,
        "connectionTimeout": 5,
        "connectRetries": 5,
        "connectRetryBaseSeconds": 2,
        "connectRetryMaxSeconds": 30,
        "sensors": {
            "Temperature": {"base": 22.0, "noise": 1.5},
            "Pressure": {"base": 1013.25, "noise": 10.0},
            "Flow": {"base": 50.0, "noise": 5.0},
            "Level": {"base": 75.0, "noise": 2.0}
        }
    }


def generate_value(base: float, noise: float) -> float:
    return round(base + random.uniform(-noise, noise), 2)


def write_data_to_db(cfg: dict):
    # Connection retry/backoff settings
    max_retries = int(cfg.get("connectRetries", 5))
    base_delay = float(cfg.get("connectRetryBaseSeconds", 2.0))
    max_delay = float(cfg.get("connectRetryMaxSeconds", 30.0))
    conn_timeout = int(cfg.get("connectionTimeout", 5))

    attempt = 0
    conn = None
    while True:
        try:
            conn = pyodbc.connect(cfg["connectionString"], timeout=conn_timeout)
            break
        except Exception as e:
            attempt += 1
            if attempt >= max_retries:
                print(f"[ODBC ERROR]: Connection failed after {attempt} attempts: {e}", flush=True)
                return False
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            print(f"[ODBC ERROR]: Connect attempt {attempt} failed: {e}. Retrying in {delay}s", flush=True)
            time.sleep(delay)

    try:
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)

        table = cfg.get("table", "CurrentValues")
        tag_col = cfg.get("tagColumn", "TagName")
        val_col = cfg.get("valueColumn", "Value")
        ts_col = cfg.get("timestampColumn", "UpdatedAt")

        for tag, sensor_cfg in cfg.get("sensors", {}).items():
            value = generate_value(sensor_cfg["base"], sensor_cfg["noise"])

            query = f"""
                MERGE [{table}] AS target
                USING (SELECT ? AS tag_name, ? AS val, ? AS ts) AS source
                ON (target.[{tag_col}] = source.tag_name)
                WHEN MATCHED THEN
                    UPDATE SET [{val_col}] = source.val, [{ts_col}] = source.ts
                WHEN NOT MATCHED THEN
                    INSERT ([{tag_col}], [{val_col}], [{ts_col}])
                    VALUES (source.tag_name, source.val, source.ts);
            """
            try:
                cursor.execute(query, (tag, value, now))
                print(f"[{now.strftime('%H:%M:%S')}] {tag} = {value}", flush=True)
            except Exception as e:
                print(f"[ODBC ERROR] executing query for tag {tag}: {e}", flush=True)
                raise

        conn.commit()
        cursor.close()
        conn.close()
        return True

    except Exception as e:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
        print(f"[ERROR]: {e}", flush=True)
        return False


def main():
    cfg = load_config()
    interval = cfg.get("intervalSeconds", 10)

    print("=" * 60, flush=True)
    print("  eHistorian SQL Fake Data Generator", flush=True)
    print("=" * 60, flush=True)
    print(f"  Table    : {cfg.get('table')}", flush=True)
    print(f"  Interval : {interval}s", flush=True)
    print(f"  Sensors  : {', '.join(cfg.get('sensors', {}).keys())}", flush=True)
    print(flush=True)

    try:
        while True:
            # Reload config on every cycle so changes apply without restart
            cfg = load_config()
            interval = cfg.get("intervalSeconds", 10)
            success = write_data_to_db(cfg)
            if not success:
                # If writing failed (connection issues), wait a bit longer before retrying
                backoff = min(interval * 2, cfg.get("connectRetryMaxSeconds", 30))
                print(f"[WARN] write failed, backing off for {backoff}s", flush=True)
                time.sleep(backoff)
            else:
                time.sleep(interval)
    except KeyboardInterrupt:
        print("\nGenerování ukončeno.", flush=True)


if __name__ == "__main__":
    main()
