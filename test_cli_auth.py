#!/usr/bin/env python3
"""Test script to verify CLI authentication is working properly"""

import json
import threading
import time

import requests
import websocket

BASE_URL = "http://localhost:8001"


def test_cli_auth(provider="claude"):
    """Test CLI authentication for specified provider"""
    print(f"\n🔐 Testing {provider} CLI authentication...")

    # Create session
    response = requests.post(
        f"{BASE_URL}/api/cli/sessions",
        json={"provider": provider, "mode": "cli", "full_access": False},
    )

    if response.status_code != 200:
        print(f"❌ Failed to create session: {response.status_code}")
        return False

    session_data = response.json()
    session_id = session_data["session_id"]
    print(f"✅ Created session: {session_id}")

    # Check session status
    time.sleep(1)
    response = requests.get(f"{BASE_URL}/api/cli/sessions/{session_id}")

    if response.status_code != 200:
        print("❌ Failed to get session status")
        return False

    status_data = response.json()

    # Check authentication status
    auth_required = status_data.get("authentication_required", True)
    auth_prompt = status_data.get("auth_prompt", "")

    if auth_required:
        print("❌ Authentication still required!")
        print(f"   Auth prompt: {auth_prompt}")
        return False
    else:
        print("✅ No authentication required - using existing CLI auth!")
        print(f"   PID: {status_data.get('pid')}")
        print(f"   State: {status_data.get('state')}")

    # Test sending a simple command via WebSocket
    ws_url = f"ws://localhost:8001/ws/cli/{session_id}"
    success = False

    def on_message(ws, message):
        nonlocal success
        try:
            data = json.loads(message)
            if data.get("type") == "output":
                content = data.get("data", {}).get("content", "")
                if content:
                    print(f"   📨 Output: {content[:100]}")
                    success = True
        except:
            pass

    def on_open(ws):
        # Send test command
        test_msg = {
            "type": "command",
            "session_id": session_id,
            "data": {"prompt": "echo 'Authentication test successful!'"},
        }
        ws.send(json.dumps(test_msg))
        print("   📤 Sent test command")

    def on_error(ws, error):
        print(f"   ❌ WebSocket error: {error}")

    def on_close(ws, code, msg):
        pass

    try:
        ws = websocket.WebSocketApp(
            ws_url, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close
        )

        # Run for a few seconds
        wst = threading.Thread(target=lambda: ws.run_forever())
        wst.daemon = True
        wst.start()

        time.sleep(3)
        ws.close()

        if success:
            print(f"✅ {provider} CLI is working with inherited authentication!")
            return True
        else:
            print(f"⚠️  No output received from {provider} CLI")
            return False

    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False
    finally:
        # Clean up session
        requests.delete(f"{BASE_URL}/api/cli/sessions/{session_id}")


if __name__ == "__main__":
    print("=" * 60)
    print("🔐 CLI AUTHENTICATION TEST")
    print("=" * 60)

    # Test Claude
    claude_ok = test_cli_auth("claude")

    # Test Codex if available
    providers_resp = requests.get(f"{BASE_URL}/api/cli/providers")
    if providers_resp.status_code == 200:
        providers = providers_resp.json()["providers"]
        if providers.get("codex", {}).get("available"):
            codex_ok = test_cli_auth("codex")
        else:
            print("\n⚠️  Codex not available, skipping test")
            codex_ok = None

    print("\n" + "=" * 60)
    print("📊 RESULTS")
    print("=" * 60)

    if claude_ok:
        print("✅ Claude CLI authentication: WORKING")
    else:
        print("❌ Claude CLI authentication: FAILED")

    if codex_ok is not None:
        if codex_ok:
            print("✅ Codex CLI authentication: WORKING")
        else:
            print("❌ Codex CLI authentication: FAILED")

    if claude_ok:
        print("\n🎉 Authentication inheritance is working correctly!")
        print("The CLI tools are using your existing local authentication.")
    else:
        print("\n⚠️  Authentication issues remain. Check the logs for details.")
