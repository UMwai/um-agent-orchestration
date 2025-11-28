#!/usr/bin/env python3
import asyncio
import websockets
import json
import sys


async def test_cli_session(session_id):
    uri = f"ws://localhost:8001/ws/cli/{session_id}"

    async with websockets.connect(uri) as websocket:
        print(f"Connected to WebSocket for session {session_id}")

        # Send a real command with correct format
        message = json.dumps({"type": "command", "data": {"command": "What is 2+2?"}})
        await websocket.send(message)
        print(f"Sent: {message}")

        # Wait for responses
        print("\nWaiting for responses...")
        for i in range(10):
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)

                # Only print output messages, not status
                if data.get("type") == "output":
                    content = data.get("data", {}).get("content", "")
                    if content.strip():
                        print(f"Claude: {content}", end="")
                elif data.get("type") == "error":
                    print(f"Error: {data}")

            except asyncio.TimeoutError:
                if i == 0:
                    print("Timeout - Claude might need more time...")
                continue
            except Exception as e:
                print(f"Error: {e}")
                break

        print("\n\nSession test completed.")


if __name__ == "__main__":
    session_id = (
        sys.argv[1] if len(sys.argv) > 1 else "948d768e-02f5-4e92-9377-c18cd0e3cd74"
    )
    asyncio.run(test_cli_session(session_id))
