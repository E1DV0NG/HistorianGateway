import asyncio
import random
import json
import os
import logging
from asyncua import Server

def load_config() -> dict:
    """Načte konfiguraci z JSON souboru (cesta z env) nebo vrátí výchozí hodnoty."""
    config_path = os.environ.get("FAKEGEN_OPCUA_CONFIG")
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "endpoint": "opc.tcp://0.0.0.0:4840/freeopcua/server/",
        "namespace": "http://historian.gateway.demo",
        "intervalSeconds": 3,
        "sensors": {
            "Temperature": {"base": 22.0, "noise": 1.5},
            "Pressure": {"base": 1013.25, "noise": 10.0},
            "Flow": {"base": 50.0, "noise": 5.0},
            "Level": {"base": 75.0, "noise": 2.0}
        }
    }

def generate_value(base: float, noise: float) -> float:
    return round(base + random.uniform(-noise, noise), 2)

async def main():
    print("=" * 60)
    print("  eHistorian OPC UA Fake Data Generator")
    print("=" * 60)
    
    cfg = load_config()
    endpoint = cfg.get("endpoint", "opc.tcp://0.0.0.0:4840/freeopcua/server/")
    namespace = cfg.get("namespace", "http://historian.gateway.demo")
    interval = cfg.get("intervalSeconds", 5)
    
    print(f"  Endpoint : {endpoint}")
    print(f"  Interval : {interval}s")
    print(f"  Sensors  : {', '.join(cfg.get('sensors', {}).keys())}\n")
    
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    
    # Registrace jmenného prostoru (namespace)
    idx = await server.register_namespace(namespace)
    
    # Přístup k uzlu "Objects"
    objects = server.nodes.objects
    
    # Vytvoření nového objektu pro naše senzory
    myobj = await objects.add_object(idx, "Sensors")
    
    # Vytvoření proměnných pro každý senzor (tag)
    sensor_vars = {}
    for tag, sensor_cfg in cfg.get("sensors", {}).items():
        base_val = generate_value(sensor_cfg["base"], sensor_cfg["noise"])
        var = await myobj.add_variable(idx, tag, base_val)
        await var.set_writable()
        sensor_vars[tag] = var
    
    print("Spouštím OPC UA server... (Ukončete pomocí Ctrl+C)")
    
    async with server:
        while True:
            # Opětovné načtení konfigurace, aby se změny projevily bez restartu
            cfg = load_config()
            interval = cfg.get("intervalSeconds", 5)
            
            for tag, sensor_cfg in cfg.get("sensors", {}).items():
                if tag in sensor_vars:
                    var = sensor_vars[tag]
                    new_val = generate_value(sensor_cfg["base"], sensor_cfg["noise"])
                    await var.write_value(new_val)
                    print(f"[{asyncio.get_event_loop().time():.0f}] {tag} = {new_val}")
                    
            await asyncio.sleep(interval)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGenerování ukončeno.")
