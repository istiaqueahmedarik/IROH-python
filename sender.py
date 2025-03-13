import asyncio
import iroh
import requests

from iroh import Iroh, MessageType, GossipMessageCallback


class Callback(GossipMessageCallback):
    def __init__(self, name):
        print("init", name)
        self.name = name
        self.chan = asyncio.Queue()

    async def on_message(self, msg):
        print(self.name, msg.type())
        await self.chan.put(msg)


async def goss_f():
    # setup event loop, to ensure async callbacks work
    iroh.iroh_ffi.uniffi_set_event_loop(asyncio.get_running_loop())

    n0 = await Iroh.memory()
    n0_id = await n0.net().node_id()
    print(f"My node ID: {n0_id}")

    # Create a topic
    topic = bytearray([1] * 32)

    # Setup gossip on node 0
    cb0 = Callback("n0")

    # Get receiver node ID via REST API or manual input
    receiver_node_id = input(
        "Enter receiver node id (or receiver's IP address for REST API): ")

    # If input looks like an IP address or hostname, try to get node ID via REST API
    if '.' in receiver_node_id and not receiver_node_id.startswith('k'):
        receiver_ip = receiver_node_id
        try:
            print(
                f"Fetching node ID from http://{receiver_ip}:5000/get_node_id")
            # response = requests.get(f"http://{receiver_ip}:5000/get_node_id")
            payload = {"node_id": n0_id}
            response = requests.post(
                f"http://{receiver_ip}:5000/get_node_id", json=payload)
            receiver_node_id = response.json()["node_id"]
            print(f"Received node ID: {receiver_node_id}")
        except Exception as e:
            print(f"Failed to get node ID via REST API: {e}")
            return

    sink0 = await n0.gossip().subscribe(topic, [receiver_node_id], cb0)

    # Wait for n1 to show up for n0
    while (True):
        event = await cb0.chan.get()
        print("<<", event.type())
        if (event.type() == MessageType.JOINED):
            break

    # Broadcast message from node 0
    while (True):
        try:
            print("broadcasting message")
            inp = input("Enter message: ")
            if inp.lower() == 'exit':
                break
            msg_content = bytearray(inp.encode("utf-8"))
            await sink0.broadcast(msg_content)
        except Exception as e:
            print(e)
            break

    await sink0.cancel()
    await n0.node().shutdown()

if __name__ == "__main__":
    asyncio.run(goss_f())
