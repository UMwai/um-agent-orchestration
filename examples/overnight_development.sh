#!/bin/bash
# Overnight Development Workflow - 23x/7 Autonomous Development
# Submit complex goals and let specialized agents work while you sleep

echo "🌙 Overnight Development Pipeline"
echo "================================="
echo ""
echo "This workflow demonstrates 23x/7 autonomous development:"
echo "Submit complex goals → Agents work overnight → Review results in the morning"
echo ""

# Check if system is set up
if [ ! -f ".env" ]; then
    echo "⚠️  System not set up. Run './quickstart.sh' first!"
    exit 1
fi

echo "🎯 Option 1: Interactive Planning (Recommended)"
echo ""
echo "Start a planning session to collaborate with Claude on task breakdown:"
echo ""
echo "  ./orchestrate plan \"Build a complete e-commerce platform with:"
echo "  - User authentication and profiles"  
echo "  - Product catalog with search and filtering"
echo "  - Shopping cart and checkout with Stripe"
echo "  - Admin dashboard for inventory management"
echo "  - Order tracking and email notifications\""
echo ""
echo "During the session, you can discuss, refine, and approve the plan."
echo "Then execution starts automatically with multiple agents."
echo ""
echo "────────────────────────────────────"
echo ""

echo "🎯 Option 2: Direct Submission"
echo ""
echo "Submit multiple complex tasks with automatic decomposition..."
echo ""

# Submit multiple high-level tasks with decomposition
echo "Submitting Task 1: E-commerce platform..."
./orchestrate submit "Build a complete e-commerce platform with user authentication, product catalog, shopping cart, Stripe checkout, and admin dashboard" --decompose

echo ""
echo "Submitting Task 2: Analytics dashboard..."
./orchestrate submit "Create a real-time analytics dashboard with WebSocket updates, interactive charts, data export, and user behavior tracking" --decompose

echo ""
echo "Submitting Task 3: Authentication system..."
./orchestrate submit "Implement enterprise-grade authentication with JWT, OAuth2, SSO, password policies, two-factor authentication, and audit logging" --decompose

echo ""
echo "Submitting Task 4: API platform..."
./orchestrate submit "Build a RESTful API platform with versioning, rate limiting, documentation, monitoring, caching, and comprehensive error handling" --decompose

echo ""
echo "Submitting Task 5: Test automation..."
./orchestrate submit "Create comprehensive test automation with unit tests, integration tests, E2E tests, performance tests, and CI/CD integration" --decompose

echo ""
echo "✅ All tasks submitted with automatic decomposition!"
echo ""
echo "📊 Current queue status:"
./orchestrate status
echo ""

echo "🚀 Launch Options:"
echo "=================="
echo ""
echo "Option A: Start immediately"
echo "  nohup ./orchestrate run --max-agents 5 > overnight.log 2>&1 &"
echo ""
echo "Option B: Use screen/tmux for session management"
echo "  screen -S orchestrator"
echo "  ./orchestrate run --max-agents 5"
echo "  # Detach with Ctrl+A, D"
echo ""
echo "Option C: Interactive launch"
echo "  ./run.sh"
echo "  # Select option 3 to run orchestrator"
echo ""

echo "📈 Monitoring Commands:"
echo "======================="
echo "  tail -f overnight.log           # View real-time logs"
echo "  ./orchestrate status            # Check queue and agents"
echo "  ./orchestrate agents            # List active agents"
echo "  ./orchestrate task <task-id>    # View specific task details"
echo ""

echo "🛑 Management Commands:"
echo "======================="
echo "  ./orchestrate kill <agent-id>   # Kill stuck agent"
echo "  ./orchestrate cleanup           # Clean old data"
echo "  pkill -f 'orchestrate run'      # Stop background process"
echo ""

echo "💡 Pro Tips:"
echo "============"
echo "• Start with 3 agents, increase to 5+ for faster completion"
echo "• Each agent specializes in different areas (backend, frontend, ML, etc.)"
echo "• Agents share context and coordinate their work automatically"
echo "• Check progress periodically: watch -n 30 './orchestrate status'"
echo "• Morning review: './orchestrate status' to see completed work"
echo ""

echo "🌅 Morning Review Workflow:"
echo "==========================="
echo "  ./orchestrate status                    # Check completion"
echo "  ls /tmp/agent_orchestrator/outputs/     # Review output files"
echo "  git status                              # See created/modified files"
echo "  git diff                                # Review changes"
echo ""

echo "Ready for overnight development! 🚀"