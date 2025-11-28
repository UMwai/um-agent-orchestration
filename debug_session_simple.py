#!/usr/bin/env python3
"""
Simple debug session to test the prompt detection.
"""

import asyncio
import logging
import time
from orchestrator.cli_session_manager import CLISessionManager

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_simple_session():
    """Simple test to debug the session initialization."""
    print("Testing simple session initialization...")

    manager = CLISessionManager()

    try:
        # Create session
        print("Creating session...")
        session_id = await manager.create_session("claude", "default")
        print(f"Session created: {session_id}")

        # Start process with debug output
        print("Starting CLI process...")
        start_time = time.time()
        success = await manager.start_cli_process(session_id, full_access=True)
        init_time = time.time() - start_time

        print(f"Process start result: {success}, took {init_time:.2f} seconds")

        if success:
            print("SUCCESS: CLI process started and ready!")

            # Try one simple command
            print("Sending test command...")
            cmd_start = time.time()
            await manager.send_input_to_session(
                session_id, "Hello! Can you say hi back?"
            )
            cmd_time = time.time() - cmd_start
            print(f"Command sent in {cmd_time:.3f} seconds")

            # Wait a bit to see the response
            await asyncio.sleep(5)
        else:
            print("FAILED: CLI process did not start properly")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Cleanup
        try:
            await manager.terminate_session(session_id, "Test completed")
            print("Session terminated")
        except:
            pass


if __name__ == "__main__":
    asyncio.run(test_simple_session())
