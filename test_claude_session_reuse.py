#!/usr/bin/env python3
"""
Test script to verify Claude session reuse functionality
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator.cli_session_manager import get_cli_session_manager


async def test_claude_session_reuse():
    """Test that multiple Claude sessions reuse the same authenticated process."""

    manager = get_cli_session_manager()

    print("Creating first Claude session...")
    session1_id = await manager.create_session(
        cli_tool="claude", mode="cli", cwd=os.getcwd()
    )
    print(f"Created session 1: {session1_id}")

    print("\nStarting first Claude CLI process with full access...")
    success1 = await manager.start_cli_process(session1_id, full_access=True)
    print(f"Session 1 started: {success1}")

    if not success1:
        print("Failed to start first session")
        return

    # Wait a bit for the first session to fully initialize
    await asyncio.sleep(3)

    print("\nCreating second Claude session...")
    session2_id = await manager.create_session(
        cli_tool="claude", mode="cli", cwd=os.getcwd()
    )
    print(f"Created session 2: {session2_id}")

    print(
        "\nStarting second Claude CLI process - should reuse authenticated session..."
    )
    success2 = await manager.start_cli_process(session2_id, full_access=True)
    print(f"Session 2 started: {success2}")

    if not success2:
        print("Failed to start second session")
        return

    # Check if both sessions are using the same process
    info1 = manager.get_session_info(session1_id)
    info2 = manager.get_session_info(session2_id)

    print(f"\nSession 1 PID: {info1.pid if info1 else 'N/A'}")
    print(f"Session 2 PID: {info2.pid if info2 else 'N/A'}")

    # Test sending a message through the second session
    print("\nSending test message through session 2...")
    success = await manager.send_input_to_session(
        session2_id, "Hello! Can you confirm you're Claude?"
    )
    print(f"Message sent: {success}")

    # Wait for response
    await asyncio.sleep(5)

    print(
        "\n✅ Test complete! Check if both sessions are using the same Claude process."
    )
    print("If authentication was required only once, the reuse is working correctly.")

    # Cleanup
    await manager.terminate_session(session1_id)
    await manager.terminate_session(session2_id)


if __name__ == "__main__":
    asyncio.run(test_claude_session_reuse())
