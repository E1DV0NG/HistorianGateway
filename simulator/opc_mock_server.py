import asyncio
from random import uniform
from asyncua import Server

async def main():
    server = Server()
    await server.init()
    
    # Nastavení lokální adresy
    server.set_endpoint("opc.tcp://127.0.0.1:4840/free-simulator/")
    server.set_server_name("Muj Free Simulator")

    # Registrace jmenného prostoru
    idx = await server.register_namespace("http://muj.simulator.cz")

    # Vytvoření složky v hierarchii OPC UA
    sim_folder = await server.nodes.objects.add_folder(idx, "Simulace")

    # Přidání dvou testovacích tagů s explicitním string NodeId
    teplota_node = await sim_folder.add_variable(f"ns={idx};s=Teplota", "Teplota", 20.0)
    tlak_node = await sim_folder.add_variable(f"ns={idx};s=Tlak", "Tlak", 1.0)
    
    await teplota_node.set_writable()
    await tlak_node.set_writable()

    print("\n🚀 OPC UA SIMULÁTOR BĚŽÍ!")
    print("URL pro gateway: opc.tcp://127.0.0.1:4840/free-simulator/")
    print("Tagy k zapsání do JSONu:")
    print(f"  - ns={idx};s=Teplota")
    print(f"  - ns={idx};s=Tlak\n")

    async with server:
        while True:
            await asyncio.sleep(5)
            # Simulace neustálé změny hodnot pro test "onChange"
            t_val = round(uniform(19.0, 25.0), 2)
            p_val = round(uniform(0.9, 1.5), 2)
            await teplota_node.write_value(t_val)
            await tlak_node.write_value(p_val)
            print(f"[MOCK] Aktualizovány hodnoty -> Teplota: {t_val} °C | Tlak: {p_val} bar")

if __name__ == "__main__":
    asyncio.run(main())