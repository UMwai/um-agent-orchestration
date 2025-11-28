#!/usr/bin/env python3
"""
Test script for AutoDev 24/7 agent orchestration with full access mode.
This script demonstrates how agents can be launched with full access permissions
to perform autonomous coding tasks.
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any

import httpx
import yaml


def load_config() -> Dict[str, Any]:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def test_claude_full_access():
    """Test Claude CLI with full access mode"""
    print("🧪 Testing Claude Full Access Mode...")

    # Test command that would normally be restricted
    test_prompt = """
    Analyze this repository structure and create a simple test file in the tests/ directory.
    The test should validate that the FastAPI server can start successfully.
    Use full access mode to create the file directly.
    """

    try:
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "-p", test_prompt],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("✅ Claude full access test succeeded")
            print(f"Output: {result.stdout[:200]}...")
        else:
            print("❌ Claude full access test failed")
            print(f"Error: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("⏰ Claude full access test timed out")
    except FileNotFoundError:
        print(
            "⚠️  Claude CLI not found - install via: curl -fsSL https://claude.ai/cli | sh"
        )


def test_codex_full_access():
    """Test Codex CLI with full access mode"""
    print("🧪 Testing Codex Full Access Mode...")

    test_prompt = """
    exec "Review the FastAPI app.py file and suggest one optimization"
    """

    try:
        result = subprocess.run(
            [
                "codex",
                "--ask-for-approval",
                "never",
                "--sandbox",
                "danger-full-access",
                "exec",
                "Review the FastAPI app.py file and suggest one optimization",
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("✅ Codex full access test succeeded")
            print(f"Output: {result.stdout[:200]}...")
        else:
            print("❌ Codex full access test failed")
            print(f"Error: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("⏰ Codex full access test timed out")
    except FileNotFoundError:
        print("⚠️  Codex CLI not found - install from OpenAI")


async def test_api_endpoints():
    """Test the orchestrator API endpoints"""
    print("🧪 Testing API Endpoints...")

    base_url = "http://localhost:8001"

    async with httpx.AsyncClient() as client:
        try:
            # Test health check
            response = await client.get(f"{base_url}/")
            if response.status_code == 200:
                print("✅ Dashboard endpoint accessible")
            else:
                print(f"❌ Dashboard endpoint failed: {response.status_code}")

            # Test metrics endpoint
            response = await client.get(f"{base_url}/api/metrics")
            if response.status_code == 200:
                metrics = response.json()
                print(f"✅ Metrics endpoint working: {metrics}")
            else:
                print(f"❌ Metrics endpoint failed: {response.status_code}")

            # Test task submission
            task_spec = {
                "id": f"test-{int(time.time())}",
                "title": "Test task submission",
                "description": "Verify the task submission endpoint works correctly",
                "role": "generic",
                "full_access": True,
            }

            response = await client.post(f"{base_url}/tasks", json=task_spec)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Task submission successful: {result}")

                # Test task retrieval
                task_id = result["task_id"]
                response = await client.get(f"{base_url}/tasks/{task_id}")
                if response.status_code == 200:
                    task_status = response.json()
                    print(f"✅ Task retrieval successful: {task_status}")
                else:
                    print(f"❌ Task retrieval failed: {response.status_code}")
            else:
                print(f"❌ Task submission failed: {response.status_code}")

        except httpx.ConnectError:
            print(
                "❌ Cannot connect to API server - make sure it's running with 'make dev'"
            )


def test_git_worktrees():
    """Test git worktree functionality"""
    print("🧪 Testing Git Worktrees...")

    try:
        # Check if we're in a git repo
        result = subprocess.run(["git", "status"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Git repository detected")

            # Test creating a worktree
            worktree_path = Path(__file__).parent.parent / "worktrees" / "test-branch"
            if worktree_path.exists():
                subprocess.run(
                    ["git", "worktree", "remove", str(worktree_path)],
                    capture_output=True,
                )

            result = subprocess.run(
                [
                    "git",
                    "worktree",
                    "add",
                    str(worktree_path),
                    "-b",
                    "test/worktree-demo",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                print("✅ Git worktree creation successful")

                # Cleanup
                subprocess.run(
                    ["git", "worktree", "remove", str(worktree_path)],
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "branch", "-D", "test/worktree-demo"], capture_output=True
                )
                print("✅ Git worktree cleanup completed")
            else:
                print(f"❌ Git worktree creation failed: {result.stderr}")
        else:
            print("❌ Not in a git repository")

    except FileNotFoundError:
        print("❌ Git not found")


def check_prerequisites():
    """Check if all prerequisites are installed"""
    print("🔍 Checking Prerequisites...")

    checks = [
        ("Python", [sys.executable, "--version"]),
        ("Git", ["git", "--version"]),
        ("Redis CLI", ["redis-cli", "--version"]),
    ]

    for name, cmd in checks:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                version = (
                    result.stdout.strip().split()[-1] if result.stdout else "unknown"
                )
                print(f"✅ {name}: {version}")
            else:
                print(f"❌ {name}: Failed to get version")
        except FileNotFoundError:
            print(f"⚠️  {name}: Not installed")


async def main():
    """Main test function"""
    print("🚀 AutoDev 24/7 Agent Orchestration Test Suite")
    print("=" * 50)

    # Check prerequisites
    check_prerequisites()
    print()

    # Test git worktrees
    test_git_worktrees()
    print()

    # Test CLI tools
    test_claude_full_access()
    print()
    test_codex_full_access()
    print()

    # Test API endpoints
    await test_api_endpoints()
    print()

    print("🎉 Test suite completed!")
    print()
    print("📊 Next steps:")
    print("1. Start the orchestrator: make dev")
    print("2. Start Redis and workers: make run")
    print("3. Open dashboard: http://localhost:8001")
    print("4. Submit tasks via API or dashboard UI")
    print("5. Monitor with: make monitoring (Prometheus + Grafana)")


if __name__ == "__main__":
    asyncio.run(main())
