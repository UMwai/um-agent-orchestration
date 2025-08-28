#!/usr/bin/env python3
"""
Simple test using bash instead of Claude to validate PTY functionality.
"""

import asyncio
import time

import requests


async def test_with_simple_bash():
    """Test PTY functionality using bash instead of Claude."""
    print("Testing PTY functionality with mock CLI...")

    base_url = "http://localhost:8001"

    try:
        # Test with mock CLI as a simple alternative
        print("\n1. Creating mock CLI PTY session...")
        create_response = requests.post(
            f"{base_url}/api/cli/sessions",
            json={
                "cli_tool": "mock",  # Use mock CLI for testing
                "mode": "interactive",
                "full_access": False,  # Don't need full access for mock
                "cwd": "/home/umwai/um-agent-orchestration",
            },
            timeout=15,
        )

        if create_response.status_code != 200:
            print(
                f"Failed to create session: {create_response.status_code} - {create_response.text}"
            )
            return

        session_data = create_response.json()
        session_id = session_data.get("session_id")
        print(f"Created session: {session_id}")

        # Wait for initialization
        print("Waiting for initialization...")
        await asyncio.sleep(3)

        # Test simple commands
        commands = ["Hello World", "What is 2+2?", "Testing response time", "Goodbye"]

        response_times = []

        for i, command in enumerate(commands, 1):
            print(f"\nTest {i}: '{command}'")

            start_time = time.time()

            send_response = requests.post(
                f"{base_url}/api/cli/sessions/{session_id}/input",
                json={"input_text": command},
                timeout=10,
            )

            response_time = time.time() - start_time
            response_times.append(response_time)

            if send_response.status_code == 200:
                print(f"✅ Command sent in {response_time:.3f} seconds")
            else:
                print(f"❌ Failed: {send_response.status_code}")

            await asyncio.sleep(1)

        # Results
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            print(f"\nAverage response time: {avg_time:.3f} seconds")
            if avg_time < 1.0:
                print("✅ PTY functionality working well!")
            else:
                print("⚠️  Response times are higher than expected")

        # Cleanup
        print("\nTerminating session...")
        requests.post(f"{base_url}/api/cli/sessions/{session_id}/terminate")
        print("Session terminated")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_with_simple_bash())
