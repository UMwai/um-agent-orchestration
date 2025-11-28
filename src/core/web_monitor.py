#!/usr/bin/env python3
"""
Minimal web monitoring interface for agent orchestration
"""

from flask import Flask, jsonify, render_template_string
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.task_queue import TaskQueue
from src.core.agent_spawner import AgentSpawner
from src.core.context_manager import ContextManager


class WebMonitor:
    """Simple web interface for monitoring orchestrator"""

    def __init__(
        self,
        db_path: str = "tasks.db",
        base_dir: str = "/tmp/agent_orchestrator",
        port: int = 3091,
    ):
        self.queue = TaskQueue(db_path)
        self.spawner = AgentSpawner(base_dir)
        self.context = ContextManager(f"{base_dir}/context")
        self.port = port

        self.app = Flask(__name__)
        self.setup_routes()

    def setup_routes(self):
        """Setup Flask routes"""

        @self.app.route("/")
        def index():
            """Main dashboard"""
            return render_template_string(HTML_TEMPLATE)

        @self.app.route("/api/status")
        def api_status():
            """Get overall status"""
            stats = self.queue.get_stats()
            agents = self.spawner.get_all_agents()

            return jsonify(
                {
                    "timestamp": datetime.now().isoformat(),
                    "task_stats": stats,
                    "active_agents": len(agents),
                    "agents": agents,
                }
            )

        @self.app.route("/api/tasks")
        def api_tasks():
            """Get all tasks"""
            tasks = self.queue.get_all_tasks()
            return jsonify(
                [
                    {
                        "id": task.id,
                        "description": task.description[:100]
                        + ("..." if len(task.description) > 100 else ""),
                        "full_description": task.description,
                        "status": task.status,
                        "agent_type": task.agent_type,
                        "priority": task.priority,
                        "created_at": task.created_at,
                        "assigned_to": task.assigned_to,
                        "result": task.result[:200]
                        + ("..." if task.result and len(task.result) > 200 else "")
                        if task.result
                        else None,
                    }
                    for task in tasks[:50]
                ]
            )  # Limit to 50 recent tasks

        @self.app.route("/api/agents")
        def api_agents():
            """Get all agents"""
            return jsonify(self.spawner.get_all_agents())

        @self.app.route("/api/task/<task_id>")
        def api_task_detail(task_id):
            """Get task details"""
            task = self.queue.get_task(task_id)
            if not task:
                return jsonify({"error": "Task not found"}), 404

            # Get agent outputs
            outputs = self.context.get_agent_outputs(task_id)

            return jsonify(
                {
                    "id": task.id,
                    "description": task.description,
                    "status": task.status,
                    "agent_type": task.agent_type,
                    "priority": task.priority,
                    "created_at": task.created_at,
                    "assigned_to": task.assigned_to,
                    "result": task.result,
                    "error": task.error,
                    "outputs": outputs,
                }
            )

    def run(self, debug=False):
        """Run the web server"""
        print(f"🌐 Starting web monitor on http://localhost:{self.port}")
        print("📊 Available endpoints:")
        print(f"   Dashboard: http://localhost:{self.port}")
        print(f"   API Status: http://localhost:{self.port}/api/status")
        self.app.run(host="127.0.0.1", port=self.port, debug=debug)


# Simple HTML template for monitoring dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Orchestrator Monitor</title>
    <style>
        body { font-family: -apple-system, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .stat-number { font-size: 24px; font-weight: bold; color: #2563eb; }
        .stat-label { color: #64748b; font-size: 14px; margin-top: 5px; }
        .section { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .task-item, .agent-item { padding: 12px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: between; align-items: center; }
        .task-item:last-child, .agent-item:last-child { border-bottom: none; }
        .status-badge { padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .status-pending { background: #fef3c7; color: #d97706; }
        .status-running { background: #dbeafe; color: #2563eb; }
        .status-completed { background: #dcfce7; color: #16a34a; }
        .status-failed { background: #fee2e2; color: #dc2626; }
        .task-desc { flex: 1; margin-right: 15px; }
        .task-id { font-family: monospace; color: #64748b; font-size: 12px; }
        .agent-running { color: #16a34a; }
        .agent-stopped { color: #64748b; }
        .refresh-btn { background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
        .refresh-btn:hover { background: #1d4ed8; }
        .loading { opacity: 0.6; }
        .task-details { font-size: 12px; color: #64748b; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Agent Orchestrator Monitor</h1>
            <button class="refresh-btn" onclick="refreshData()">Refresh</button>
            <span id="last-update" style="margin-left: 15px; color: #64748b; font-size: 14px;"></span>
        </div>
        
        <div class="stats" id="stats">
            <!-- Stats will be populated by JavaScript -->
        </div>
        
        <div class="section">
            <h2>🎯 Recent Tasks</h2>
            <div id="tasks">
                <div class="loading">Loading tasks...</div>
            </div>
        </div>
        
        <div class="section">
            <h2>⚙️ Active Agents</h2>
            <div id="agents">
                <div class="loading">Loading agents...</div>
            </div>
        </div>
    </div>

    <script>
        let autoRefresh = true;
        
        function refreshData() {
            loadStatus();
            loadTasks();
            loadAgents();
        }
        
        function loadStatus() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('last-update').textContent = 
                        'Last update: ' + new Date(data.timestamp).toLocaleTimeString();
                    
                    const stats = data.task_stats;
                    const statsHtml = `
                        <div class="stat-card">
                            <div class="stat-number">${stats.pending || 0}</div>
                            <div class="stat-label">Pending Tasks</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${stats.running || 0}</div>
                            <div class="stat-label">Running Tasks</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${stats.completed || 0}</div>
                            <div class="stat-label">Completed Tasks</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.active_agents}</div>
                            <div class="stat-label">Active Agents</div>
                        </div>
                    `;
                    document.getElementById('stats').innerHTML = statsHtml;
                });
        }
        
        function loadTasks() {
            fetch('/api/tasks')
                .then(r => r.json())
                .then(tasks => {
                    const tasksHtml = tasks.length ? tasks.map(task => `
                        <div class="task-item">
                            <div class="task-desc">
                                <div>${task.description}</div>
                                <div class="task-details">
                                    <span class="task-id">${task.id}</span> • 
                                    ${task.agent_type} • 
                                    Priority: ${task.priority} • 
                                    ${new Date(task.created_at).toLocaleString()}
                                    ${task.assigned_to ? ' • Assigned to: ' + task.assigned_to : ''}
                                </div>
                            </div>
                            <div class="status-badge status-${task.status}">${task.status}</div>
                        </div>
                    `).join('') : '<div style="color: #64748b; text-align: center; padding: 20px;">No tasks found</div>';
                    
                    document.getElementById('tasks').innerHTML = tasksHtml;
                });
        }
        
        function loadAgents() {
            fetch('/api/agents')
                .then(r => r.json())
                .then(agents => {
                    const agentsHtml = agents.length ? agents.map(agent => `
                        <div class="agent-item">
                            <div class="task-desc">
                                <div><strong>${agent.agent_id}</strong></div>
                                <div class="task-details">
                                    Type: ${agent.agent_type} • 
                                    Task: ${agent.task_id} • 
                                    Duration: ${agent.duration}s
                                </div>
                            </div>
                            <div class="status-badge status-${agent.running ? 'running' : 'completed'}">
                                ${agent.running ? 'Running' : 'Stopped'}
                            </div>
                        </div>
                    `).join('') : '<div style="color: #64748b; text-align: center; padding: 20px;">No active agents</div>';
                    
                    document.getElementById('agents').innerHTML = agentsHtml;
                });
        }
        
        // Auto refresh every 5 seconds
        setInterval(() => {
            if (autoRefresh) {
                refreshData();
            }
        }, 5000);
        
        // Initial load
        refreshData();
        
        // Pause auto-refresh when window is not visible
        document.addEventListener('visibilitychange', () => {
            autoRefresh = !document.hidden;
        });
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    monitor = WebMonitor()
    monitor.run(debug=True)
