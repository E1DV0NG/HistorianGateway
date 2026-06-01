import asyncio
from asyncua import Client

async def main():
    url = "opc.tcp://127.0.0.1:4840/freeopcua/server/"
    print(f"Connecting to {url} ...")
    async with Client(url=url) as client:
        print("Connected!")
        # Let's find the namespace index
        ns_idx = await client.get_namespace_index("http://historian.gateway.demo")
        print(f"Namespace index: {ns_idx}")
        
        objects = client.nodes.objects
        print("Children of Objects:")
        for child in await objects.get_children():
            name = await child.read_browse_name()
            print(f" - {name} (NodeId: {child.nodeid})")
            if name.Name == "Sensors":
                print("   Children of Sensors:")
                for s_child in await child.get_children():
                    s_name = await s_child.read_browse_name()
                    val = await s_child.read_value()
                    print(f"     - {s_name.Name} = {val} (NodeId: {s_child.nodeid})")

if __name__ == "__main__":
    asyncio.run(main())
