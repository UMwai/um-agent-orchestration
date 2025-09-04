#!/bin/bash
# Quick launcher for Agent Orchestrator
# This is a convenience wrapper that handles environment setup

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to show help
show_help() {
    echo -e "${BLUE}Agent Orchestrator - Quick Launcher${NC}"
    echo "===================================="
    echo ""
    echo -e "${GREEN}Usage:${NC}"
    echo "  ./run.sh [command] [options]"
    echo ""
    echo -e "${GREEN}Commands:${NC}"
    echo "  plan <goal>           - Start interactive planning"
    echo "  submit <task> [-d]    - Submit task (use -d for decompose)"
    echo "  run [--max-agents N]  - Process tasks"
    echo "  status                - Show queue status"
    echo "  demo                  - Run demo tasks"
    echo "  setup                 - Run full setup (same as ./quickstart.sh)"
    echo ""
    echo -e "${GREEN}Examples:${NC}"
    echo "  ./run.sh plan \"Build a REST API\""
    echo "  ./run.sh submit \"Create a blog\" --decompose"
    echo "  ./run.sh run --max-agents 5"
    echo "  ./run.sh demo"
    echo ""
    echo -e "${YELLOW}Note: Run './run.sh setup' for first-time installation${NC}"
}

# Check if first argument is help
if [[ "$1" == "help" || "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
    exit 0
fi

# Special case for setup
if [[ "$1" == "setup" ]]; then
    echo -e "${BLUE}Running full setup...${NC}"
    ./quickstart.sh
    exit $?
fi

# Check if orchestrate exists
if [ ! -f "./orchestrate" ]; then
    echo -e "${RED}❌ Orchestrator not found!${NC}"
    echo -e "${YELLOW}Run './run.sh setup' to install first.${NC}"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv_orchestrator" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found.${NC}"
    echo -e "${YELLOW}Creating minimal environment...${NC}"
    python3 -m venv venv_orchestrator
    source venv_orchestrator/bin/activate
    pip install -q click pyyaml anthropic python-dotenv
else
    source venv_orchestrator/bin/activate
fi

# Check API key status
if [ -f ".env" ]; then
    if grep -q "ANTHROPIC_API_KEY=replace_me\|ANTHROPIC_API_KEY=your-api-key-here" .env 2>/dev/null; then
        echo -e "${YELLOW}⚠️  API key not configured. Running in demo mode only.${NC}"
        echo -e "   To configure: edit .env or run './run.sh setup'"
        echo ""
    fi
else
    echo -e "${YELLOW}⚠️  No .env file found. Run './run.sh setup' for full configuration.${NC}"
fi

# Check system status quickly
echo -e "${GREEN}System Status:${NC}"
if command -v claude &> /dev/null; then
    echo "  ✅ Claude CLI available"
else
    echo "  ℹ️  Claude CLI not found (API mode will be used)"
fi

if [ -f "tasks.db" ]; then
    task_count=$(sqlite3 tasks.db "SELECT COUNT(*) FROM tasks;" 2>/dev/null || echo "0")
    echo "  📊 Tasks in queue: $task_count"
fi
echo ""

# If no arguments provided, show interactive menu
if [ $# -eq 0 ]; then
    echo -e "${BLUE}🚀 Agent Orchestrator${NC}"
    echo "===================="
    echo ""
    echo "What would you like to do?"
    echo ""
    echo "1) Start interactive planning session"
    echo "2) Submit a task with auto-decomposition"  
    echo "3) Run orchestrator to process tasks"
    echo "4) Check status"
    echo "5) Run demo"
    echo "6) View help"
    echo "7) Exit"
    echo ""
    read -p "Choose (1-7): " choice
    
    case $choice in
        1)
            read -p "Enter your goal: " goal
            if [ ! -z "$goal" ]; then
                ./orchestrate plan "$goal"
            fi
            ;;
        2)
            read -p "Enter task description: " task
            if [ ! -z "$task" ]; then
                ./orchestrate submit "$task" --decompose
                echo ""
                read -p "Run orchestrator now? (y/N): " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    ./orchestrate run
                fi
            fi
            ;;
        3)
            ./orchestrate run
            ;;
        4)
            ./orchestrate status
            ;;
        5)
            ./orchestrate demo
            ;;
        6)
            show_help
            ;;
        7|*)
            echo "Goodbye!"
            exit 0
            ;;
    esac
else
    # Pass all arguments to orchestrate
    ./orchestrate "$@"
fi