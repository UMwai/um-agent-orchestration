#!/usr/bin/env python3
"""Debug script to test CLI session creation and identify the error."""

import asyncio
import sys
import traceback

sys.path.insert(0, "/home/umwai/um-agent-orchestration")


async def test_create_session():
    """Test creating a CLI session to identify the error."""
    try:
        from orchestrator.cli_session_manager import get_cli_session_manager

        print("Getting CLI session manager...")
        manager = get_cli_session_manager()

        print("Creating session...")
        session_id = await manager.create_session(
            cli_tool="claude",
            mode="cli",
            cwd=None,
            user_id="default",
            start_immediately=True,
        )

        print(f"Session created with ID: {session_id}")

        print("Starting CLI process...")
        success = await manager.start_cli_process(session_id, full_access=False)

        if success:
            print("CLI process started successfully!")
        else:
            print("Failed to start CLI process")

        # Check session info
        session_info = manager.get_session_info(session_id)
        if session_info:
            print(f"Session state: {session_info.state}")

        # Clean up
        await manager.terminate_session(session_id)
        print("Session terminated")

    except Exception as e:
        print(f"Error occurred: {e}")
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    print("Testing CLI session creation...")
    success = asyncio.run(test_create_session())
    sys.exit(0 if success else 1)
