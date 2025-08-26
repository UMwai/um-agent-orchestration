#!/bin/bash

# AutoDev Full Access Mode Initialization Script
# This script initializes the repository with Claude Code or Codex in full access mode

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 AutoDev Full Access Mode Initialization"
echo "Repository: $REPO_ROOT"
echo

# Check if Claude Code or Codex is available
check_cli_availability() {
    local cli_name="$1"
    local binary="$2"
    
    if command -v "$binary" &> /dev/null; then
        echo "✅ $cli_name CLI available: $(which $binary)"
        return 0
    else
        echo "❌ $cli_name CLI not found: $binary"
        return 1
    fi
}

echo "Checking CLI availability:"
CLAUDE_AVAILABLE=false
CODEX_AVAILABLE=false

if check_cli_availability "Claude Code" "claude"; then
    CLAUDE_AVAILABLE=true
fi

if check_cli_availability "Codex" "codex"; then
    CODEX_AVAILABLE=true
fi

if [ "$CLAUDE_AVAILABLE" = false ] && [ "$CODEX_AVAILABLE" = false ]; then
    echo
    echo "❌ No supported CLI tools found!"
    echo "Please install one of the following:"
    echo "  - Claude Code CLI: https://docs.anthropic.com/en/docs/claude-code"
    echo "  - Codex CLI: https://openai.com/terminal"
    exit 1
fi

echo

# Prompt user to select CLI
if [ "$CLAUDE_AVAILABLE" = true ] && [ "$CODEX_AVAILABLE" = true ]; then
    echo "Multiple CLIs available. Which would you like to use?"
    echo "1) Claude Code (recommended for full access)"
    echo "2) Codex"
    read -p "Enter choice (1 or 2): " choice
    
    case $choice in
        1)
            SELECTED_CLI="claude"
            PROVIDER="claude_interactive"
            ;;
        2)
            SELECTED_CLI="codex"
            PROVIDER="codex_interactive"
            ;;
        *)
            echo "Invalid choice. Defaulting to Claude Code."
            SELECTED_CLI="claude"
            PROVIDER="claude_interactive"
            ;;
    esac
elif [ "$CLAUDE_AVAILABLE" = true ]; then
    SELECTED_CLI="claude"
    PROVIDER="claude_interactive"
    echo "Using Claude Code CLI"
else
    SELECTED_CLI="codex"
    PROVIDER="codex_interactive"
    echo "Using Codex CLI"
fi

echo

# Test the selected CLI with full access parameters
echo "Testing $SELECTED_CLI with full access parameters..."

if [ "$SELECTED_CLI" = "claude" ]; then
    echo "Testing: claude --dangerously-skip-permissions -p 'test'"
    if claude --dangerously-skip-permissions -p "Hello, this is a test of full access mode" > /dev/null 2>&1; then
        echo "✅ Claude full access mode working"
    else
        echo "⚠️  Claude full access test failed. You may need to grant permissions."
        echo "   Run: claude --dangerously-skip-permissions -p 'test' manually to check"
    fi
elif [ "$SELECTED_CLI" = "codex" ]; then
    echo "Testing: codex --ask-for-approval never --sandbox danger-full-access exec 'test'"
    if codex --ask-for-approval never --sandbox danger-full-access exec "Hello, this is a test of full access mode" > /dev/null 2>&1; then
        echo "✅ Codex full access mode working"
    else
        echo "⚠️  Codex full access test failed. Check your configuration."
        echo "   Run: codex --ask-for-approval never --sandbox danger-full-access exec 'test' manually"
    fi
fi

echo

# Initialize the repository with the selected CLI
echo "Initializing AutoDev system with $SELECTED_CLI..."

cd "$REPO_ROOT"

# Check if already initialized
if [ -f ".env" ]; then
    echo "✅ Environment file exists"
else
    echo "Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your API keys before running tasks"
fi

# Install dependencies if needed
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
    echo "Installing dependencies..."
    make install
else
    echo "✅ Dependencies already installed"
fi

# Create a test task for the full access mode
TEST_TASK_FILE="examples/test-full-access-task.yaml"
echo "Creating test task at $TEST_TASK_FILE..."

cat > "$TEST_TASK_FILE" << EOF
id: FULL-ACCESS-TEST-001
title: "Test Full Access Mode"
description: >
  Test that the selected CLI ($SELECTED_CLI) can operate in full access mode.
  This task should:
  - Read the repository structure
  - Create a simple test file
  - Run basic system commands
  - Report on the repository status
role: generic
provider_override: "$PROVIDER"
acceptance:
  tests: []
  lint: false
  typecheck: false
target_dir: "."
EOF

echo "✅ Test task created at $TEST_TASK_FILE"

# Provide instructions
echo
echo "🎉 Full Access Mode Initialization Complete!"
echo
echo "Next steps:"
echo "1. Start the orchestrator system:"
echo "   Terminal 1: make dev"
echo "   Terminal 2: make run"
echo
echo "2. Test full access mode by submitting the test task:"
echo "   curl -X POST http://localhost:8000/tasks \\"
echo "        -H 'Content-Type: application/json' \\"
echo "        -d @$TEST_TASK_FILE"
echo
echo "3. Monitor the task execution:"
echo "   curl http://localhost:8000/tasks/FULL-ACCESS-TEST-001"
echo
echo "The selected provider ($PROVIDER) will be used with full access:"
if [ "$SELECTED_CLI" = "claude" ]; then
    echo "  - Claude Code with --dangerously-skip-permissions"
else
    echo "  - Codex with --ask-for-approval never --sandbox danger-full-access"
fi
echo
echo "⚠️  SECURITY WARNING: Full access mode bypasses safety restrictions."
echo "   Only use in trusted environments and for trusted tasks."