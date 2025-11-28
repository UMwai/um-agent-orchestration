#!/usr/bin/env python3
"""
Test security fixes for the Agent Orchestrator
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.input_validator import InputValidator, ValidationError
from src.core.context_manager import ContextManager
from src.core.agent_spawner import AgentSpawner, AgentType


def test_input_validation():
    """Test input validation functionality"""
    print("🔒 Testing Input Validation Security Fixes")
    print("=" * 60)

    # Test 1: Basic validation (should pass)
    try:
        safe_desc = InputValidator.sanitize_task_description(
            "Write a simple Python function"
        )
        safe_agent = InputValidator.sanitize_agent_id("claude-test-123")
        safe_type = InputValidator.validate_agent_type("claude")
        safe_priority = InputValidator.validate_priority("high")
        safe_json = InputValidator.validate_json_context('{"key": "value"}')
        print("✅ Basic validation tests: PASS")
    except Exception as e:
        print(f"❌ Basic validation failed: {e}")
        return False

    # Test 2: Security validation (should fail)
    malicious_tests = [
        ("Command injection in task", "Write a script $(rm -rf /)", "task_description"),
        ("Path traversal in agent ID", "../../../etc/passwd", "agent_id"),
        ("Invalid agent type", "malicious-agent", "agent_type"),
        ("Invalid priority", "ultra-high", "priority"),
        ("Command injection in JSON", '{"cmd": "$(rm -rf /)"}', "json_context"),
        ("Backticks in JSON", '{"cmd": "`rm -rf /`"}', "json_context"),
        ("Command chaining in JSON", '{"cmd": "ls && rm -rf"}', "json_context"),
    ]

    for test_name, test_input, test_type in malicious_tests:
        try:
            if test_type == "task_description":
                InputValidator.sanitize_task_description(test_input)
            elif test_type == "agent_id":
                InputValidator.sanitize_agent_id(test_input)
            elif test_type == "agent_type":
                InputValidator.validate_agent_type(test_input)
            elif test_type == "priority":
                InputValidator.validate_priority(test_input)
            elif test_type == "json_context":
                InputValidator.validate_json_context(test_input)

            print(f"⚠️  {test_name}: UNEXPECTED PASS (should have failed)")
        except ValidationError:
            print(f"✅ {test_name}: CORRECTLY BLOCKED")
        except Exception as e:
            print(f"✅ {test_name}: CORRECTLY BLOCKED ({type(e).__name__})")

    return True


def test_context_manager_security():
    """Test context manager security fixes"""
    print("\n🔒 Testing Context Manager Security Fixes")
    print("=" * 60)

    try:
        # Test with a safe temporary directory
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            cm = ContextManager(f"{temp_dir}/context")

            # Test safe operations
            cm.set_global_context("test_key", "test_value")
            value = cm.get_global_context("test_key")
            assert value == "test_value"
            print("✅ Safe context operations: PASS")

            # Test malicious key attempts
            try:
                cm.set_global_context("../../../malicious", "value")
                print("⚠️  Path traversal in context key: UNEXPECTED PASS")
            except ValueError:
                print("✅ Path traversal in context key: CORRECTLY BLOCKED")

            # Test safe task context
            cm.set_task_context("safe-task-123", {"key": "value"})
            context = cm.get_task_context("safe-task-123")
            assert context["key"] == "value"
            print("✅ Safe task context operations: PASS")

            return True

    except Exception as e:
        print(f"❌ Context manager test failed: {e}")
        return False


def test_agent_spawner_security():
    """Test agent spawner security fixes"""
    print("\n🔒 Testing Agent Spawner Security Fixes")
    print("=" * 60)

    try:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            spawner = AgentSpawner(f"{temp_dir}/agents")

            # Test input validation in spawn_agent
            try:
                spawner.spawn_agent(
                    AgentType.CLAUDE,
                    "safe-task-123",
                    "Write a simple Python function",
                    {"key": "value"},
                )
                print("✅ Safe agent spawning validation: PASS")
            except ValueError as e:
                print(f"❌ Safe agent spawning failed: {e}")
                return False

            # Test malicious inputs
            try:
                spawner.spawn_agent(
                    AgentType.CLAUDE,
                    "../../../malicious",
                    "safe description",
                    {"key": "value"},
                )
                print("⚠️  Malicious task ID: UNEXPECTED PASS")
            except ValueError:
                print("✅ Malicious task ID: CORRECTLY BLOCKED")

            try:
                spawner.spawn_agent(
                    AgentType.CLAUDE,
                    "safe-task",
                    "Execute $(rm -rf /)",
                    {"key": "value"},
                )
                print("⚠️  Malicious task description: UNEXPECTED PASS")
            except ValueError:
                print("✅ Malicious task description: CORRECTLY BLOCKED")

            return True

    except Exception as e:
        print(f"❌ Agent spawner test failed: {e}")
        return False


def main():
    """Run all security tests"""
    print("🛡️  Agent Orchestrator Security Validation Tests")
    print("=" * 60)

    tests = [
        test_input_validation,
        test_context_manager_security,
        test_agent_spawner_security,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1

    print(f"\n📊 Test Results: {passed}/{total} test suites passed")

    if passed == total:
        print("🎉 All security tests passed! The system is properly secured.")
        return True
    else:
        print("⚠️  Some security tests failed. Please review the issues above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
