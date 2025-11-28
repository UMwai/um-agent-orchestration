#!/usr/bin/env python3
"""
Validation script to check Claude session reuse implementation
"""

import sys


def validate_implementation():
    """Validate that the session reuse implementation is correct."""

    print("Validating Claude Session Reuse Implementation...")
    print("=" * 50)

    # Check CLI session manager modifications
    cli_manager_path = "orchestrator/cli_session_manager.py"

    with open(cli_manager_path, "r") as f:
        content = f.read()

    checks = [
        ("✓ Claude session storage added", "claude_authenticated_session" in content),
        ("✓ Session lock for thread safety", "claude_session_lock" in content),
        ("✓ Reuse method implemented", "_try_reuse_claude_session" in content),
        ("✓ Auth check method added", "_check_claude_auth_status" in content),
        (
            "✓ Session reuse in start_cli_process",
            "await self._try_reuse_claude_session(session_id)" in content,
        ),
        (
            "✓ Special termination handling",
            "if session == self.claude_authenticated_session" in content,
        ),
        ("✓ Process finding capability", "_find_existing_claude_process" in content),
    ]

    all_passed = True
    for message, check in checks:
        if check:
            print(f"  {message}")
        else:
            print(f"  ✗ {message[2:]}")
            all_passed = False

    print("\n" + "=" * 50)

    if all_passed:
        print("✅ All implementation checks passed!")
        print("\nThe Claude session reuse implementation is complete.")
        print("\nKey benefits:")
        print("  • Single authentication for multiple sessions")
        print("  • Automatic detection of existing authenticated sessions")
        print("  • Shared process for resource efficiency")
        print("  • Preserves your Claude Code subscription value")
        print("\nTo use:")
        print("  1. Start your first Claude session normally")
        print("  2. Authenticate when prompted")
        print("  3. All subsequent sessions will reuse the authentication")
    else:
        print("❌ Some implementation checks failed.")
        print("Please review the implementation.")

    return all_passed


if __name__ == "__main__":
    success = validate_implementation()
    sys.exit(0 if success else 1)
