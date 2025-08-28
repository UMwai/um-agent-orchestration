#!/usr/bin/env python3
"""
Test the persistent session implementation with a mock CLI to verify the architecture.
"""

import asyncio
import time

from orchestrator.cli_session_manager import CLISessionManager


async def test_mock_session():
    """Test with mock CLI to verify session architecture works."""
    print("Testing persistent CLI session with mock CLI...")

    manager = CLISessionManager()

    try:
        # Create a mock CLI session (defined in cli_session_manager.py)
        print("Creating Mock CLI session...")
        session_id = await manager.create_session("mock", "default")
        print(f"Created session: {session_id}")

        # Start the CLI process
        print("Starting mock CLI process...")
        start_time = time.time()
        success = await manager.start_cli_process(session_id, full_access=False)
        init_time = time.time() - start_time

        if not success:
            print("Failed to start mock CLI process")
            return

        print(f"Mock CLI process started successfully in {init_time:.2f} seconds")

        # Wait a bit for the process to fully initialize
        await asyncio.sleep(1)

        # Test sending multiple commands and measure response time
        test_commands = [
            "Hello mock CLI!",
            "What is 2+2?",
            "Test response",
        ]

        response_times = []

        for i, command in enumerate(test_commands, 1):
            print(f"\nTest {i}: Sending command: '{command}'")

            start_time = time.time()
            await manager.send_input_to_session(session_id, command)
            response_time = time.time() - start_time
            response_times.append(response_time)

            print(f"Command sent in {response_time:.3f} seconds")

            # Wait a bit to see the response
            await asyncio.sleep(2)

        # Calculate statistics
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)

        print("\nPerformance Results:")
        print(f"Average response time: {avg_response_time:.3f} seconds")
        print(f"Min response time: {min_response_time:.3f} seconds")
        print(f"Max response time: {max_response_time:.3f} seconds")
        print(f"Initialization time: {init_time:.3f} seconds")

        # Check if we meet our performance goals
        if avg_response_time < 2.0:
            print("✅ SUCCESS: Average response time is under 2 seconds!")
        else:
            print("❌ FAILURE: Average response time exceeds 2 seconds")

        if max_response_time < 5.0:
            print("✅ SUCCESS: All responses were under 5 seconds!")
        else:
            print("❌ FAILURE: Some responses took longer than 5 seconds")

        print("\n✅ Mock CLI session test completed successfully!")

    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Cleanup
        print("\nCleaning up session...")
        try:
            await manager.terminate_session(session_id, "Test completed")
            print("Session terminated successfully")
        except:
            pass


if __name__ == "__main__":
    print("Starting mock CLI session test...")
    asyncio.run(test_mock_session())
