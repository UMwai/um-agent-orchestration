#!/usr/bin/env python3
"""
Test script for CLI integration - verifies end-to-end functionality
"""

import json
import threading
import time

import requests
import websocket

BASE_URL = "http://localhost:8001"


def test_provider_detection():
    """Test that CLI providers are detected correctly"""
    print("\n🔍 Testing provider detection...")
    response = requests.get(f"{BASE_URL}/api/cli/providers")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['available_count']} available CLI providers:")
        for name, info in data["providers"].items():
            status = "✅" if info["available"] else "❌"
            print(f"  {status} {name}: {info['path'] if info['available'] else 'Not installed'}")
        return True
    else:
        print(f"❌ Failed to get providers: {response.status_code}")
        return False


def test_create_session():
    """Test creating a new CLI session"""
    print("\n🚀 Testing CLI session creation...")

    # Try to create a Claude CLI session
    payload = {"provider": "claude", "mode": "cli", "full_access": False}

    response = requests.post(f"{BASE_URL}/api/cli/sessions", json=payload)

    if response.status_code == 200:
        data = response.json()
        session_id = data["session_id"]
        print(f"✅ Created CLI session: {session_id}")
        print(f"   Tool: {data['cli_tool']}")
        print(f"   State: {data['state']}")
        print(f"   WebSocket URL: {data['websocket_url']}")
        return session_id
    else:
        print(f"❌ Failed to create session: {response.status_code}")
        print(f"   Error: {response.text}")
        return None


def test_session_status(session_id: str):
    """Test getting session status"""
    print(f"\n📊 Testing session status for {session_id}...")

    response = requests.get(f"{BASE_URL}/api/cli/sessions/{session_id}")

    if response.status_code == 200:
        data = response.json()
        print("✅ Session status retrieved:")
        print(f"   PID: {data.get('pid', 'N/A')}")
        print(f"   State: {data.get('state', 'N/A')}")
        print(f"   Auth Required: {data.get('authentication_required', False)}")
        if data.get("auth_prompt"):
            print(f"   Auth Prompt: {data['auth_prompt']}")
        return True
    else:
        print(f"❌ Failed to get session status: {response.status_code}")
        return False


def test_websocket_connection(session_id: str):
    """Test WebSocket connection for real-time communication"""
    print(f"\n🔌 Testing WebSocket connection for session {session_id}...")

    ws_url = f"ws://localhost:8001/ws/cli/{session_id}"
    received_messages = []

    def on_message(ws, message):
        try:
            data = json.loads(message)
            print(
                f"   📨 Received: {data.get('type', 'unknown')} - {data.get('data', {}).get('status', '')}"
            )
            received_messages.append(data)
        except json.JSONDecodeError:
            print(f"   📨 Received raw: {message[:100]}")

    def on_error(ws, error):
        print(f"   ❌ WebSocket error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"   🔒 WebSocket closed: {close_status_code} - {close_msg}")

    def on_open(ws):
        print("   ✅ WebSocket connected")

        # Send a test command
        test_message = {
            "type": "command",
            "session_id": session_id,
            "data": {"prompt": "echo 'Hello from CLI integration test'"},
        }
        ws.send(json.dumps(test_message))
        print("   📤 Sent test command")

        # Wait a bit for response
        time.sleep(3)

        # Send status request
        status_message = {"type": "status", "session_id": session_id, "data": {}}
        ws.send(json.dumps(status_message))
        print("   📤 Sent status request")

    try:
        ws = websocket.WebSocketApp(
            ws_url, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close
        )

        # Run WebSocket in thread for 5 seconds
        wst = threading.Thread(target=lambda: ws.run_forever())
        wst.daemon = True
        wst.start()

        time.sleep(5)
        ws.close()

        if received_messages:
            print(f"   ✅ Received {len(received_messages)} messages")
            return True
        else:
            print("   ⚠️  No messages received")
            return False

    except Exception as e:
        print(f"   ❌ WebSocket test failed: {e}")
        return False


def test_list_sessions():
    """Test listing all active sessions"""
    print("\n📋 Testing session listing...")

    response = requests.get(f"{BASE_URL}/api/cli/sessions")

    if response.status_code == 200:
        data = response.json()
        sessions = data.get("sessions", [])
        print(f"✅ Found {len(sessions)} active session(s)")
        for session in sessions:
            print(f"   - {session['session_id']}: {session['cli_tool']} ({session['state']})")
        return True
    else:
        print(f"❌ Failed to list sessions: {response.status_code}")
        return False


def test_terminate_session(session_id: str):
    """Test terminating a CLI session"""
    print(f"\n🛑 Testing session termination for {session_id}...")

    response = requests.delete(f"{BASE_URL}/api/cli/sessions/{session_id}")

    if response.status_code == 200:
        print("✅ Session terminated successfully")
        return True
    else:
        print(f"⚠️  Failed to terminate session: {response.status_code}")
        return False


def main():
    """Run all integration tests"""
    print("=" * 60)
    print("🧪 CLI INTEGRATION TEST SUITE")
    print("=" * 60)

    results = []

    # Test 1: Provider Detection
    results.append(("Provider Detection", test_provider_detection()))

    # Test 2: Create Session
    session_id = test_create_session()
    results.append(("Session Creation", session_id is not None))

    if session_id:
        # Test 3: Session Status
        results.append(("Session Status", test_session_status(session_id)))

        # Test 4: WebSocket Connection
        results.append(("WebSocket Communication", test_websocket_connection(session_id)))

        # Test 5: List Sessions
        results.append(("List Sessions", test_list_sessions()))

        # Test 6: Terminate Session
        results.append(("Session Termination", test_terminate_session(session_id)))

    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\n🎯 Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! CLI integration is working correctly.")
        return 0
    else:
        print(f"⚠️  {total - passed} test(s) failed. Please check the logs.")
        return 1


if __name__ == "__main__":
    exit(main())
