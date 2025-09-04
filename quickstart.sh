#!/bin/bash
# Agent Orchestrator - One-Click Setup & Launch
# This script handles complete setup and provides launch options

set -e

# Colors for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Agent Orchestrator - Setup & Launch${NC}"
echo "========================================"
echo ""

# Check Python version
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed.${NC}"
    echo "   Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${GREEN}✅ Python $PYTHON_VERSION found${NC}"

# Check if virtual environment exists
if [ ! -d "venv_orchestrator" ]; then
    echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
    python3 -m venv venv_orchestrator
fi

# Activate virtual environment
echo -e "${YELLOW}🔧 Activating virtual environment...${NC}"
source venv_orchestrator/bin/activate

# Install dependencies
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
pip install -q --upgrade pip
pip install -q click pyyaml anthropic python-dotenv flask
echo -e "${GREEN}✅ Dependencies installed${NC}"

# Check for .env file and API key
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}📝 Creating .env file from template...${NC}"
        cp .env.example .env
    else
        echo -e "${YELLOW}📝 Creating .env file...${NC}"
        cat > .env << EOF
# Agent Orchestrator Configuration
ANTHROPIC_API_KEY=your-api-key-here
USE_API_MODE=true
MAX_AGENTS=3
ORCHESTRATOR_BASE_DIR=/tmp/agent_orchestrator
EOF
    fi
fi

# Check if API key is configured
if grep -q "ANTHROPIC_API_KEY=replace_me\|ANTHROPIC_API_KEY=your-api-key-here" .env 2>/dev/null; then
    echo ""
    echo -e "${RED}⚠️  API Key Required${NC}"
    echo -e "${YELLOW}Please add your Anthropic API key to continue.${NC}"
    echo ""
    echo -e "Option 1: Edit manually"
    echo -e "  ${BLUE}nano .env${NC}  (then update ANTHROPIC_API_KEY)"
    echo ""
    echo -e "Option 2: Enter now"
    read -p "Enter your Anthropic API key (or press Enter to skip): " api_key
    if [ ! -z "$api_key" ]; then
        sed -i.bak "s/ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$api_key/" .env
        echo -e "${GREEN}✅ API key saved${NC}"
    fi
fi

# Make orchestrate executable
chmod +x orchestrate

# Check system readiness
echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${BLUE}System Status:${NC}"
if grep -q "ANTHROPIC_API_KEY=replace_me\|ANTHROPIC_API_KEY=your-api-key-here" .env 2>/dev/null; then
    echo -e "  ${YELLOW}⚠️  API key not configured (demo mode only)${NC}"
else
    echo -e "  ${GREEN}✅ API key configured${NC}"
fi

if command -v claude &> /dev/null; then
    echo -e "  ${GREEN}✅ Claude CLI available${NC}"
else
    echo -e "  ${YELLOW}ℹ️  Claude CLI not found (API mode recommended)${NC}"
fi

echo ""
echo -e "${BLUE}🚀 Launch Options:${NC}"
echo "=================="
echo ""
echo -e "${GREEN}1. Interactive Planning (Recommended)${NC}"
echo "   Start a planning session with Claude:"
echo -e "   ${BLUE}./orchestrate plan \"Build a REST API with authentication\"${NC}"
echo ""
echo -e "${GREEN}2. Quick Demo${NC}"
echo "   Try the system with example tasks:"
echo -e "   ${BLUE}./orchestrate demo${NC}"
echo ""
echo -e "${GREEN}3. Direct Task Submission${NC}"
echo "   Submit and auto-decompose a task:"
echo -e "   ${BLUE}./orchestrate submit \"Create a blog platform\" --decompose${NC}"
echo -e "   ${BLUE}./orchestrate run${NC}"
echo ""
echo -e "${GREEN}4. View Examples${NC}"
echo -e "   ${BLUE}cat examples/simple_workflow.sh${NC}"
echo -e "   ${BLUE}cat examples/overnight_development.sh${NC}"
echo ""
echo "────────────────────────────────────"
echo ""
read -p "Would you like to start with a demo? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n${GREEN}Starting demo...${NC}\n"
    ./orchestrate demo
else
    echo -e "\n${BLUE}Quick Reference:${NC}"
    echo "  ./orchestrate plan <goal>    - Interactive planning"
    echo "  ./orchestrate submit <task>  - Submit task"
    echo "  ./orchestrate run            - Process tasks"
    echo "  ./orchestrate status         - Check progress"
    echo ""
    echo -e "${GREEN}Ready to orchestrate! Try: ./orchestrate plan \"Your goal here\"${NC}"
fi