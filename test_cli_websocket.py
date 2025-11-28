import asyncio
import websockets
import json


async def test_cli():
    session_id = "2501dd29-bcfb-44dd-9583-11088b7811bb"
    uri = f"ws://localhost:8001/ws/cli/{session_id}"

    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")

        # Send a test command
        message = json.dumps({"type": "command", "content": "hello"})
        await websocket.send(message)
        print(f"Sent: {message}")

        # Wait for responses
        for _ in range(5):
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                data = json.loads(response)
                print(f"Received: {json.dumps(data, indent=2)}")
            except asyncio.TimeoutError:
                print("Timeout waiting for response")
                break
            except Exception as e:
                print(f"Error: {e}")
                break


asyncio.run(test_cli())
