import asyncio
import iroh
import threading
from flask import Flask, jsonify
import time
from flask import request

from iroh import Iroh, MessageType, GossipMessageCallback

# Global variable to store node ID
node_id = None
sender_node_id = None
last_recieved_message = None
app = Flask(__name__)


@app.route('/get_node_id', methods=['GET'])
def get_node_id():
    while node_id is None:
        time.sleep(0.1)  # Wait until node_id is available
    return jsonify({"node_id": node_id})


@app.route('/get_node_id', methods=['POST'])
def post_node_id():
    global sender_node_id
    sender_node_id = request.json["node_id"]
    return jsonify({"node_id": sender_node_id})


@app.route('/last_message', methods=['GET'])
def get_last_message():
    global last_recieved_message
    return jsonify({"last_message": last_recieved_message})


class Callback(GossipMessageCallback):
    def __init__(self, name):
        print("init", name)
        self.name = name
        self.chan = asyncio.Queue()

    async def on_message(self, msg):
        print(self.name, msg.type())
        await self.chan.put(msg)


def run_flask():
    app.run(host='0.0.0.0', port=5000)


async def goss_f():
    global node_id
    # setup event loop, to ensure async callbacks work
    iroh.iroh_ffi.uniffi_set_event_loop(asyncio.get_running_loop())

    n1 = await Iroh.memory()
    n1_id = await n1.net().node_id()
    node_id = n1_id  # Store node ID in global variable
    print(f"My node ID: {n1_id}")
    print("REST API server started on port 5000. Waiting for sender to connect...")

    # Create a topic
    topic = bytearray([1] * 32)

    cb1 = Callback("n1")

    print("subscribe n1")
    global sender_node_id
    # sender_node_id = input(
    #     "Enter sender node id (or just press Enter if using the REST API): ")
    sender_node_id = ""
    while (sender_node_id.strip() == ""):
        print("Waiting for sender to connect via REST API...")
        time.sleep(1)

    sink1 = await n1.gossip().subscribe(topic, [sender_node_id], cb1)

    # Wait for the message on node 1
    while (True):
        try:
            event = await cb1.chan.get()
            if (event.type() == MessageType.RECEIVED):
                msg = event.as_received()
                print("Received message")
                print(msg.content.decode('utf-8'))
                global last_recieved_message
                last_recieved_message = msg.content.decode('utf-8')
        except Exception as e:
            print(e)
            break

    await sink1.cancel()
    await n1.node().shutdown()

if __name__ == "__main__":
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    asyncio.run(goss_f())
