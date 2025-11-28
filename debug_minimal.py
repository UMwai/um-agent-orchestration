#!/usr/bin/env python3
"""
Minimal debug test.
"""

import asyncio
import logging
from orchestrator.cli_session_manager import CLISessionManager

# Set up logging
logging.basicConfig(level=logging.INFO)


async def test_creation():
    """Test just session creation."""
    print("Testing session creation...")

    try:
        manager = CLISessionManager()
        print("Manager created")

        session_id = await manager.create_session("bash", "default")
        print(f"Session created: {session_id}")

        success = await asyncio.wait_for(
            manager.start_cli_process(session_id, full_access=False), timeout=10
        )
        print(f"Process started: {success}")

    except asyncio.TimeoutError:
        print("Timeout during process start")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_creation())
