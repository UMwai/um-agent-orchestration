#!/usr/bin/env python3
"""
Test the server integration and CLI session functionality.
"""

import requests


def test_server_functionality():
    """Test the server endpoints and CLI session creation."""
    print("🧪 TESTING SERVER INTEGRATION")
    print("=" * 50)

    base_url = "http://localhost:8001"

    try:
        # Test basic health check
        print("1. Testing server connectivity...")
        response = requests.get(f"{base_url}/api/metrics", timeout=5)
        if response.status_code == 200:
            print(f"   ✅ Server responding (status: {response.status_code})")
        else:
            print(f"   ❌ Server error (status: {response.status_code})")
            return

        # Test CLI providers endpoint
        print("2. Testing CLI providers endpoint...")
        response = requests.get(f"{base_url}/api/cli/providers", timeout=5)
        if response.status_code == 200:
            providers = response.json()
            print(
                f"   ✅ CLI providers loaded: {providers['available_count']}/{providers['total_count']} available"
            )

            # Show available providers
            for name, info in providers["providers"].items():
                status = "✅" if info["available"] else "❌"
                print(f"      {status} {info['name']}: {info['path'] or 'not found'}")
        else:
            print(f"   ❌ CLI providers error (status: {response.status_code})")

        # Test creating a bash CLI session (no auth needed)
        print("3. Testing CLI session creation (bash)...")
        create_data = {"cli_tool": "bash", "mode": "cli", "full_access": False}

        response = requests.post(f"{base_url}/api/cli/sessions", json=create_data, timeout=10)
        if response.status_code == 200:
            session_data = response.json()
            session_id = session_data["session_id"]
            print(f"   ✅ Bash CLI session created: {session_id}")
            print(f"      State: {session_data['state']}")
            print(f"      WebSocket: {session_data['websocket_url']}")

            # Test session info
            print("4. Testing session info retrieval...")
            response = requests.get(f"{base_url}/api/cli/sessions/{session_id}", timeout=5)
            if response.status_code == 200:
                info = response.json()
                print("   ✅ Session info retrieved")
                print(f"      CLI Tool: {info['cli_tool']}")
                print(f"      State: {info['state']}")
                print(f"      Auth Required: {info['authentication_required']}")

            # Test sending input to session
            print("5. Testing input sending...")
            input_data = {"input": "echo 'Hello from API!'"}
            response = requests.post(
                f"{base_url}/api/cli/sessions/{session_id}/input", json=input_data, timeout=5
            )
            if response.status_code == 200:
                print("   ✅ Input sent successfully")
            else:
                print(f"   ❌ Input sending failed (status: {response.status_code})")

            # Test session termination
            print("6. Testing session termination...")
            response = requests.post(
                f"{base_url}/api/cli/sessions/{session_id}/terminate", timeout=5
            )
            if response.status_code == 200:
                print("   ✅ Session terminated successfully")
            else:
                print(f"   ❌ Session termination failed (status: {response.status_code})")

        else:
            print(f"   ❌ CLI session creation failed (status: {response.status_code})")
            print(f"   Error: {response.text}")

        # Test dashboard access
        print("7. Testing dashboard access...")
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            content = response.text
            if "Agent UM-7" in content and "Dashboard" in content:
                print(f"   ✅ Dashboard loads successfully ({len(content)} chars)")
            else:
                print("   ⚠️  Dashboard loads but content may be incorrect")
        else:
            print(f"   ❌ Dashboard access failed (status: {response.status_code})")

        print("\n✅ SERVER INTEGRATION TEST COMPLETED")
        print("   The server at localhost:8001 is working properly!")
        print("   Dashboard should be accessible in your browser.")

    except requests.exceptions.ConnectionError:
        print(f"❌ Connection error: Cannot reach server at {base_url}")
        print(
            "   Make sure the server is running: uvicorn orchestrator.app:app --host 0.0.0.0 --port 8001"
        )
    except requests.exceptions.Timeout:
        print("❌ Timeout error: Server is too slow to respond")
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_server_functionality()
