#!/bin/bash
# Simple workflow example for getting started with Agent Orchestrator

echo "🚀 Simple Workflow Example"
echo "========================="
echo ""
echo "This demonstrates basic task submission and execution."
echo ""

# Check if system is set up
if [ ! -f ".env" ]; then
    echo "⚠️  System not set up. Run './quickstart.sh' first!"
    exit 1
fi

# Step 1: Submit a simple task with decomposition
echo "Step 1: Submitting a task with auto-decomposition..."
echo "Task: 'Build a simple REST API for todo management'"
echo ""
./orchestrate submit "Build a simple REST API for todo management with CRUD operations" --decompose

echo ""
echo "The system automatically breaks this into subtasks like:"
echo "  - Design API endpoints and data structure"
echo "  - Implement the backend with proper error handling"  
echo "  - Add input validation and security"
echo "  - Write comprehensive tests"
echo ""

# Step 2: Check the queue
echo "Step 2: Checking task queue..."
./orchestrate status
echo ""

# Step 3: Process the tasks
echo "Step 3: Processing tasks with 2 parallel agents..."
echo "This may take several minutes depending on task complexity."
echo ""
./orchestrate run --max-agents 2

echo ""

# Step 4: View final results
echo "Step 4: Final status check..."
./orchestrate status
echo ""

echo "✅ Simple workflow complete!"
echo ""
echo "🚀 Next steps to try:"
echo "  • Interactive planning: ./orchestrate plan \"Your complex goal\""
echo "  • Quick launcher menu: ./run.sh"
echo "  • Multiple agents: ./orchestrate run --max-agents 5"
echo "  • Overnight workflow: ./examples/overnight_development.sh"
echo ""
echo "💡 Tips:"
echo "  • Use --decompose for automatic task breakdown"
echo "  • Check ./orchestrate status anytime to see progress"  
echo "  • View specific task details with ./orchestrate task <task-id>"