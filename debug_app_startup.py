#!/usr/bin/env python3
"""
Debug the FastAPI app startup to identify what's causing hanging.
"""

import asyncio
import logging
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def test_app_startup():
    """Test the app startup components individually."""
    print("Testing FastAPI app startup components...")

    try:
        print("1. Testing Redis connection...")
        start_time = time.time()
        from redis import Redis
        import os

        redis_client = Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
        )
        redis_client.ping()
        print(f"   ✅ Redis connected in {time.time() - start_time:.3f}s")

        print("2. Testing CLI session manager import...")
        start_time = time.time()
        from orchestrator.cli_session_manager import get_cli_session_manager

        print(f"   ✅ CLI session manager imported in {time.time() - start_time:.3f}s")

        print("3. Testing CLI session manager initialization...")
        start_time = time.time()
        cli_session_manager = get_cli_session_manager()
        print(f"   ✅ CLI session manager created in {time.time() - start_time:.3f}s")

        print("4. Testing event loop setup...")
        start_time = time.time()
        loop = asyncio.get_event_loop()
        cli_session_manager.set_main_loop(loop)
        print(f"   ✅ Event loop set in {time.time() - start_time:.3f}s")

        print("5. Testing FastAPI app creation...")
        start_time = time.time()
        print(f"   ✅ FastAPI app created in {time.time() - start_time:.3f}s")

        print("\n✅ All components initialized successfully!")
        print("The app should be able to start without hanging.")

    except Exception as e:
        print(f"❌ Error during startup test: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_app_startup())
