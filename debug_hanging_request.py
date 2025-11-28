#!/usr/bin/env python3
"""
Debug script to figure out where the request is hanging.
"""

import requests
import threading
import time


def make_request():
    """Make the request in a separate thread."""
    print("Making request...")
    try:
        response = requests.post(
            "http://localhost:8001/api/cli/sessions",
            json={"cli_tool": "mock", "mode": "interactive"},
            timeout=5,
        )
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
    except requests.exceptions.Timeout:
        print("❌ Request timed out after 5 seconds")
    except Exception as e:
        print(f"❌ Request failed: {e}")


def check_server_health():
    """Check if server is responding to other endpoints."""
    try:
        response = requests.get("http://localhost:8001/health", timeout=2)
        print(f"✅ Server health check: {response.status_code}")
        return True
    except:
        print("❌ Server health check failed")
        return False


def main():
    print("Debugging hanging CLI session creation request...")

    # First check if server is responding
    print("\n1. Checking server health...")
    if not check_server_health():
        print("Server is not responding. Exiting.")
        return

    # Try a simple endpoint first
    print("\n2. Testing simple endpoint...")
    try:
        response = requests.get("http://localhost:8001/tasks", timeout=2)
        print(f"✅ Tasks endpoint: {response.status_code}")
    except Exception as e:
        print(f"❌ Tasks endpoint failed: {e}")

    # Now try the CLI endpoint
    print("\n3. Testing CLI session creation (will timeout after 5s)...")

    # Start request in a separate thread so we can monitor it
    request_thread = threading.Thread(target=make_request)
    request_thread.start()

    # Monitor the thread
    start_time = time.time()
    while request_thread.is_alive():
        elapsed = time.time() - start_time
        if elapsed > 10:
            print(f"⚠️  Request has been running for {elapsed:.1f} seconds...")
            break
        time.sleep(0.5)

    # Wait for thread to complete
    request_thread.join(timeout=1)

    if request_thread.is_alive():
        print("❌ Request thread is still alive after timeout")
    else:
        print("✅ Request thread completed")


if __name__ == "__main__":
    main()
