#!/usr/bin/env python3
"""
Standalone script for processing the merge queue.
Can be run manually or via systemd timer.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path  
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def main():
    """Process the merge queue once"""
    print("🔄 Processing merge queue...")

    try:
        from gitops.merge_coordinator import get_merge_coordinator
        merge_coordinator = get_merge_coordinator()
        result = await merge_coordinator.process_merge_queue()

        if result["status"] == "idle":
            print("✅ No items in merge queue")
        elif result["status"] == "busy":
            print(f"⏳ Merge in progress: {result['active_merge']}")
        elif result["status"] == "conflict_unresolved":
            print(f"⚠️  Conflicts in PR {result['pr_id']}: {result['conflicts']}")
        else:
            print(f"✅ Processed merge queue: {result}")

    except Exception as e:
        print(f"❌ Error processing merge queue: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
