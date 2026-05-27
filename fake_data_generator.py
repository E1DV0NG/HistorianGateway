import time
import random
import pyodbc
from datetime import datetime, timezone

# ── KONFIGURACE PŘIPOJENÍ ────────────────────────────────────────────────────
# Upravte tyto údaje podle vaší hostované SQL databáze.
# Aktuální hodnoty jsou předvyplněny podle example.config.json.
CONNECTION_STRING = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=localhost;"
    "Database=eFactory;"
    "UID=sa;"
    "PWD=YourStrong!Passw0rd;"
    "TrustServerCertificate=yes;"
)

TABLE_NAME = "CurrentValues"
TAG_COLUMN = "TagName"
VALUE_COLUMN = "Value"
TIMESTAMP_COLUMN = "UpdatedAt"

# ── SIMULOVANÁ DATA ──────────────────────────────────────────────────────────
# Tagy, jejich základní hodnoty (base) a maximální šum (noise) pro generování dat.
SENSORS = {
    "Temperature": {"base": 22.0, "noise": 1.5},
    "Pressure": {"base": 1013.25, "noise": 10.0},
    "Flow": {"base": 50.0, "noise": 5.0},
    "Level": {"base": 75.0, "noise": 2.0}
}

def generate_value(base: float, noise: float) -> float:
    """Generuje náhodnou hodnotu s šumem zaokrouhlenou na dvě desetinná místa."""
    return round(base + random.uniform(-noise, noise), 2)

def write_data_to_db():
    try:
        # Navázání asynchronního/synchronního připojení (pyodbc je synchronní)
        conn = pyodbc.connect(CONNECTION_STRING, timeout=5)
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc)
        
        for tag, config in SENSORS.items():
            value = generate_value(config["base"], config["noise"])
            
            # Varianta 1: UPSERT (MERGE) - Aktualizuje řádek pokud tag existuje, jinak vloží nový
            query = f"""
                MERGE [{TABLE_NAME}] AS target
                USING (SELECT ? AS tag_name, ? AS val, ? AS ts) AS source
                ON (target.[{TAG_COLUMN}] = source.tag_name)
                WHEN MATCHED THEN
                    UPDATE SET [{VALUE_COLUMN}] = source.val, [{TIMESTAMP_COLUMN}] = source.ts
                WHEN NOT MATCHED THEN
                    INSERT ([{TAG_COLUMN}], [{VALUE_COLUMN}], [{TIMESTAMP_COLUMN}])
                    VALUES (source.tag_name, source.val, source.ts);
            """
            
            cursor.execute(query, (tag, value, now))
            print(f"[{now.strftime('%H:%M:%S')}] Úspěšně zapsáno: {tag} = {value}")
            
        conn.commit()
        cursor.close()
        conn.close()
        
    except pyodbc.Error as pe:
        print(f"[ODBC CHYBA]: Nepodařilo se komunikovat s databází. Zkontrolujte připojovací řetězec a ovladače. Detaily: {pe}")
    except Exception as e:
        print(f"[CHYBA]: Neočekávaná chyba při zápisu: {e}")

def main():
    print("=" * 60)
    print("  eHistorian SQL Fake Data Generator (Varianta 1: UPSERT)")
    print("=" * 60)
    print(f"  Cílová tabulka : {TABLE_NAME}")
    print(f"  Interval zápisu : 10 sekund")
    print(f"  Ukončení        : Stiskněte Ctrl+C\n")
    
    try:
        while True:
            write_data_to_db()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nGenerování dat bylo ukončeno uživatelem.")

if __name__ == "__main__":
    main()
