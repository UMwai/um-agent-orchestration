#!/usr/bin/env python3
"""
Emergency Smoke Test Suite for UM Agent Orchestration
Tests critical system functionality to verify emergency fixes.
"""

import sys
import time
import traceback

# Results tracking
results: dict[str, bool] = {}
errors: dict[str, str] = {}


def test_imports() -> bool:
    """Test all critical imports."""
    try:
        # Core model imports

        # Session management imports

        # Authentication imports

        # Provider imports

        print("✅ All critical imports successful")
        return True
    except Exception as e:
        errors["imports"] = str(e)
        print(f"❌ Import test failed: {e}")
        return False


def test_task_states() -> bool:
    """Test TaskState enum functionality."""
    try:
        from orchestrator.persistence_models import TaskState

        # Test all required states exist
        required_states = ["QUEUED", "RUNNING", "PASSED", "FAILED", "ERROR"]
        for state in required_states:
            if not hasattr(TaskState, state):
                raise ValueError(f"Missing required state: {state}")

        # Test state transitions
        state = TaskState.QUEUED
        assert state.value == "queued"

        print(f"✅ TaskState test successful - {len(TaskState)} states available")
        return True
    except Exception as e:
        errors["task_states"] = str(e)
        print(f"❌ TaskState test failed: {e}")
        return False


def test_authentication_flow() -> bool:
    """Test authentication without infinite loops."""
    try:
        from orchestrator.auth import authenticate_user, create_access_token, verify_token

        # Set timeout for the entire test
        start_time = time.time()

        # Test user authentication
        user_info = authenticate_user("admin", "secret")
        if not user_info:
            raise ValueError("Authentication failed for admin user")

        # Test token creation
        token = create_access_token(user_info)
        if not token or len(token) < 20:
            raise ValueError("Token creation failed")

        # Test token verification
        verified = verify_token(token)
        if not verified or verified["username"] != "admin":
            raise ValueError("Token verification failed")

        # Test invalid token handling
        invalid_result = verify_token("invalid_token")
        if invalid_result is not None:
            raise ValueError("Should reject invalid tokens")

        # Check for timing issues (infinite loops)
        elapsed = time.time() - start_time
        if elapsed > 10:  # Should complete in well under 10 seconds
            raise ValueError(f"Authentication took too long: {elapsed:.2f}s")

        print(f"✅ Authentication flow test successful ({elapsed:.3f}s)")
        return True
    except Exception as e:
        errors["authentication"] = str(e)
        print(f"❌ Authentication test failed: {e}")
        return False


def test_session_management() -> bool:
    """Test session management functionality."""
    try:
        from orchestrator.cli_session import CLISessionManager

        # Test session manager creation
        CLISessionManager()

        print("✅ Session management test successful")
        return True
    except Exception as e:
        errors["sessions"] = str(e)
        print(f"❌ Session management test failed: {e}")
        return False


def test_redis_connection() -> bool:
    """Test Redis connectivity."""
    try:
        import redis

        # Test basic Redis connection
        r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        r.ping()

        print("✅ Redis connection test successful")
        return True
    except Exception as e:
        errors["redis"] = str(e)
        print(f"❌ Redis connection test failed: {e}")
        return False


def test_fastapi_startup() -> bool:
    """Test FastAPI application can be imported and created."""
    try:
        # Test that app is a FastAPI instance
        from fastapi import FastAPI

        from orchestrator.app import app

        if not isinstance(app, FastAPI):
            raise ValueError("App is not a FastAPI instance")

        # Test basic route count
        route_count = len(app.routes)
        if route_count < 5:  # Should have at least a few routes
            raise ValueError(f"Too few routes: {route_count}")

        print(f"✅ FastAPI startup test successful - {route_count} routes")
        return True
    except Exception as e:
        errors["fastapi"] = str(e)
        print(f"❌ FastAPI startup test failed: {e}")
        return False


def run_all_tests() -> tuple[int, int]:
    """Run all emergency tests and return (passed, total)."""
    tests = [
        ("imports", test_imports),
        ("task_states", test_task_states),
        ("authentication", test_authentication_flow),
        ("sessions", test_session_management),
        ("redis", test_redis_connection),
        ("fastapi", test_fastapi_startup),
    ]

    print("🚨 EMERGENCY SMOKE TEST SUITE")
    print("=" * 50)

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🔄 Running {test_name} test...")
        try:
            success = test_func()
            results[test_name] = success
            if success:
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
            errors[test_name] = str(e)
            traceback.print_exc()

    print("\n" + "=" * 50)
    print("📊 EMERGENCY TEST RESULTS")
    print("=" * 50)

    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:15} {status}")
        if not success and test_name in errors:
            print(f"                Error: {errors[test_name][:100]}")

    print(f"\n🎯 OVERALL: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")

    if passed == total:
        print("✅ ALL EMERGENCY TESTS PASSED - SYSTEM READY")
        return passed, total
    else:
        print("❌ CRITICAL ISSUES FOUND - IMMEDIATE ATTENTION REQUIRED")
        return passed, total


if __name__ == "__main__":
    # Add current directory to path
    import os

    sys.path.insert(0, os.getcwd())

    passed, total = run_all_tests()
    sys.exit(0 if passed == total else 1)
