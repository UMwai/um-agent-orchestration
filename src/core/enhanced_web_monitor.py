#!/usr/bin/env python3
"""
Enhanced web monitoring interface with feedback loop support
"""

from flask import Flask, jsonify, render_template_string
import json
import sys
from pathlib import Path
from datetime import datetime
import sqlite3

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.task_queue import TaskQueue
from src.core.agent_spawner import AgentSpawner
from src.core.context_manager import ContextManager
from src.core.feedback_orchestrator import FeedbackOrchestrator


class EnhancedWebMonitor:
    """Enhanced web interface with feedback loop monitoring"""

    def __init__(
        self,
        db_path: str = "tasks.db",
        base_dir: str = "/tmp/agent_orchestrator",
        port: int = 3091,
    ):
        self.db_path = db_path
        self.queue = TaskQueue(db_path)
        self.spawner = AgentSpawner(base_dir)
        self.context = ContextManager(f"{base_dir}/context")
        self.feedback_orchestrator = FeedbackOrchestrator(db_path)
        self.port = port

        self.app = Flask(__name__)
        self.setup_routes()

    def setup_routes(self):
        """Setup Flask routes"""

        @self.app.route("/")
        def index():
            """Enhanced dashboard"""
            return render_template_string(ENHANCED_HTML_TEMPLATE)

        @self.app.route("/api/status")
        def api_status():
            """Get overall status including feedback loops"""
            stats = self.queue.get_stats()
            agents = self.spawner.get_all_agents()

            # Get feedback loop stats
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN status = 'running' THEN 1 END) as running,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                    COUNT(*) as total
                FROM validated_tasks
            """)

            feedback_stats = cursor.fetchone()
            conn.close()

            return jsonify(
                {
                    "timestamp": datetime.now().isoformat(),
                    "task_stats": stats,
                    "feedback_stats": {
                        "pending": feedback_stats[0] if feedback_stats else 0,
                        "running": feedback_stats[1] if feedback_stats else 0,
                        "completed": feedback_stats[2] if feedback_stats else 0,
                        "total": feedback_stats[3] if feedback_stats else 0,
                    },
                    "active_agents": len(agents),
                    "agents": agents,
                }
            )

        @self.app.route("/api/tasks")
        def api_tasks():
            """Get all regular tasks"""
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
            )

        @self.app.route("/api/feedback-tasks")
        def api_feedback_tasks():
            """Get all feedback loop tasks"""
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    task_id, description, agent_type, success_criteria,
                    max_iterations, iteration_count, refinement_strategy,
                    status, created_at, updated_at
                FROM validated_tasks
                ORDER BY updated_at DESC
                LIMIT 20
            """)

            rows = cursor.fetchall()

            tasks = []
            for row in rows:
                criteria = json.loads(row[3])
                tasks.append(
                    {
                        "task_id": row[0],
                        "description": row[1][:100]
                        + ("..." if len(row[1]) > 100 else ""),
                        "agent_type": row[2],
                        "criteria": criteria.get("description", "Custom"),
                        "progress": f"{row[5]}/{row[4]}",
                        "iterations": row[5],
                        "max_iterations": row[4],
                        "strategy": row[6],
                        "status": row[7],
                        "created_at": row[8],
                        "updated_at": row[9],
                    }
                )

            conn.close()
            return jsonify(tasks)

        @self.app.route("/api/feedback-task/<task_id>")
        def api_feedback_task_detail(task_id):
            """Get detailed feedback task with history"""
            status = self.feedback_orchestrator.get_feedback_status(task_id)

            if "error" in status:
                return jsonify(status), 404

            # Get full feedback history
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT iteration, timestamp, evaluation_result, metrics, refinement_applied
                FROM feedback_history
                WHERE task_id = ?
                ORDER BY iteration
            """,
                (task_id,),
            )

            history = []
            for row in cursor.fetchall():
                metrics = json.loads(row[3])
                history.append(
                    {
                        "iteration": row[0],
                        "timestamp": row[1],
                        "result": row[2],
                        "metrics": metrics,
                        "refinement": row[4][:200] if row[4] else None,
                    }
                )

            conn.close()

            status["detailed_history"] = history
            return jsonify(status)

        @self.app.route("/api/agents")
        def api_agents():
            """Get all agents"""
            return jsonify(self.spawner.get_all_agents())

        @self.app.route("/api/metrics-chart/<task_id>")
        def api_metrics_chart(task_id):
            """Get metrics data for charting"""
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT iteration, metrics
                FROM feedback_history
                WHERE task_id = ?
                ORDER BY iteration
            """,
                (task_id,),
            )

            chart_data = {"iterations": [], "series": {}}

            for row in cursor.fetchall():
                iteration = row[0]
                metrics = json.loads(row[1])

                chart_data["iterations"].append(iteration)

                # Extract numeric metrics for charting
                if "details" in metrics:
                    for metric_name, metric_data in metrics["details"].items():
                        if metric_name not in chart_data["series"]:
                            chart_data["series"][metric_name] = []

                        value = metric_data.get("value", 0)
                        chart_data["series"][metric_name].append(value)

            conn.close()
            return jsonify(chart_data)

        @self.app.route("/api/kill-agent/<agent_id>", methods=["POST"])
        def api_kill_agent(agent_id):
            """Kill a specific agent"""
            try:
                self.spawner.kill_agent(agent_id)
                return jsonify({"success": True, "message": f"Agent {agent_id} killed"})
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500

    def run(self, debug=False):
        """Run the web server"""
        print(f"🌐 Starting enhanced web monitor on http://localhost:{self.port}")
        print("📊 Dashboard features:")
        print("   - Real-time task monitoring")
        print("   - Feedback loop tracking")
        print("   - Metrics visualization")
        print("   - Agent management")
        print(f"\n🔗 URL: http://localhost:{self.port}")
        self.app.run(host="127.0.0.1", port=self.port, debug=debug)


# Enhanced HTML template with modern UI and charts
ENHANCED_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Orchestrator Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }

        .dashboard {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 25px;
            border-radius: 16px;
            margin-bottom: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header h1 {
            font-size: 28px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.08);
            transition: transform 0.3s;
        }

        .stat-card:hover {
            transform: translateY(-5px);
        }

        .stat-value {
            font-size: 32px;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .stat-label {
            color: #64748b;
            font-size: 14px;
            margin-top: 5px;
        }

        .content-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
            margin-bottom: 25px;
        }

        @media (max-width: 1024px) {
            .content-grid {
                grid-template-columns: 1fr;
            }
        }

        .panel {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.08);
            overflow: hidden;
        }

        .panel-header {
            padding: 20px;
            background: linear-gradient(135deg, #f3f4f6, #e5e7eb);
            border-bottom: 1px solid #e5e7eb;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .panel-title {
            font-size: 18px;
            font-weight: 600;
            color: #1f2937;
        }

        .panel-content {
            padding: 20px;
            max-height: 400px;
            overflow-y: auto;
        }

        .task-item, .agent-item, .feedback-item {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 12px;
            background: #f9fafb;
            transition: all 0.3s;
        }

        .task-item:hover, .agent-item:hover, .feedback-item:hover {
            background: #f3f4f6;
            transform: translateX(5px);
        }

        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 8px;
        }

        .task-desc {
            flex: 1;
            color: #1f2937;
            font-weight: 500;
        }

        .task-meta {
            display: flex;
            gap: 10px;
            font-size: 12px;
            color: #6b7280;
            margin-top: 5px;
        }

        .badge {
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-pending { background: #fef3c7; color: #d97706; }
        .badge-running { background: #dbeafe; color: #2563eb; }
        .badge-completed { background: #dcfce7; color: #16a34a; }
        .badge-failed { background: #fee2e2; color: #dc2626; }

        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.5s ease;
        }

        .metrics-display {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }

        .metric-item {
            padding: 8px;
            background: white;
            border-radius: 6px;
            text-align: center;
        }

        .metric-name {
            font-size: 11px;
            color: #6b7280;
            text-transform: uppercase;
        }

        .metric-value {
            font-size: 18px;
            font-weight: bold;
            color: #1f2937;
        }

        .chart-container {
            position: relative;
            height: 300px;
            padding: 20px;
        }

        .empty-state {
            text-align: center;
            padding: 40px;
            color: #9ca3af;
        }

        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }

        .modal-content {
            background: white;
            border-radius: 16px;
            padding: 30px;
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }

        .close-modal {
            float: right;
            font-size: 24px;
            cursor: pointer;
            color: #6b7280;
        }

        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #e5e7eb;
        }

        .tab {
            padding: 10px 20px;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
            color: #6b7280;
        }

        .tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb {
            background: #888;
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #555;
        }
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>🤖 Agent Orchestrator Dashboard</h1>
            <div class="controls">
                <span id="last-update" style="color: #6b7280; margin-right: 15px;"></span>
                <label style="color: #6b7280;">
                    <input type="checkbox" id="auto-refresh" checked> Auto-refresh
                </label>
                <button class="btn btn-primary" onclick="refreshAll()">Refresh Now</button>
            </div>
        </div>

        <div class="stats-grid" id="stats">
            <!-- Stats cards will be populated here -->
        </div>

        <div class="tabs">
            <div class="tab active" onclick="switchTab('tasks')">Regular Tasks</div>
            <div class="tab" onclick="switchTab('feedback')">Feedback Loops</div>
            <div class="tab" onclick="switchTab('agents')">Active Agents</div>
        </div>

        <div id="tasks-tab" class="tab-content active">
            <div class="content-grid">
                <div class="panel">
                    <div class="panel-header">
                        <h2 class="panel-title">📋 Recent Tasks</h2>
                        <span id="task-count" style="color: #6b7280;"></span>
                    </div>
                    <div class="panel-content" id="tasks-list">
                        <div class="empty-state">Loading tasks...</div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-header">
                        <h2 class="panel-title">📊 Task Distribution</h2>
                    </div>
                    <div class="chart-container">
                        <canvas id="task-chart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <div id="feedback-tab" class="tab-content">
            <div class="content-grid">
                <div class="panel">
                    <div class="panel-header">
                        <h2 class="panel-title">🔄 Feedback Loop Tasks</h2>
                        <span id="feedback-count" style="color: #6b7280;"></span>
                    </div>
                    <div class="panel-content" id="feedback-list">
                        <div class="empty-state">Loading feedback tasks...</div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-header">
                        <h2 class="panel-title">📈 Metrics Progress</h2>
                    </div>
                    <div class="chart-container">
                        <canvas id="metrics-chart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <div id="agents-tab" class="tab-content">
            <div class="panel">
                <div class="panel-header">
                    <h2 class="panel-title">⚙️ Active Agents</h2>
                    <span id="agent-count" style="color: #6b7280;"></span>
                </div>
                <div class="panel-content" id="agents-list">
                    <div class="empty-state">Loading agents...</div>
                </div>
            </div>
        </div>
    </div>

    <div id="task-modal" class="modal">
        <div class="modal-content">
            <span class="close-modal" onclick="closeModal()">&times;</span>
            <h2>Task Details</h2>
            <div id="modal-content"></div>
        </div>
    </div>

    <script>
        let currentTab = 'tasks';
        let autoRefresh = true;
        let taskChart = null;
        let metricsChart = null;
        let selectedFeedbackTask = null;

        // Tab switching
        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            event.target.classList.add('active');
            document.getElementById(`${tab}-tab`).classList.add('active');

            refreshAll();
        }

        // Refresh all data
        function refreshAll() {
            loadStatus();
            loadTasks();
            loadFeedbackTasks();
            loadAgents();
        }

        // Load overall status
        function loadStatus() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('last-update').textContent =
                        'Last update: ' + new Date(data.timestamp).toLocaleTimeString();

                    const stats = data.task_stats;
                    const feedbackStats = data.feedback_stats;

                    const statsHtml = `
                        <div class="stat-card">
                            <div class="stat-value">${stats.pending || 0}</div>
                            <div class="stat-label">Pending Tasks</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.running || 0}</div>
                            <div class="stat-label">Running Tasks</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.completed || 0}</div>
                            <div class="stat-label">Completed Tasks</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${feedbackStats.running || 0}</div>
                            <div class="stat-label">Active Feedback Loops</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${feedbackStats.total || 0}</div>
                            <div class="stat-label">Total Validated Tasks</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${data.active_agents}</div>
                            <div class="stat-label">Active Agents</div>
                        </div>
                    `;
                    document.getElementById('stats').innerHTML = statsHtml;

                    // Update task chart
                    updateTaskChart(stats);
                });
        }

        // Load regular tasks
        function loadTasks() {
            fetch('/api/tasks')
                .then(r => r.json())
                .then(tasks => {
                    document.getElementById('task-count').textContent = `${tasks.length} tasks`;

                    if (tasks.length === 0) {
                        document.getElementById('tasks-list').innerHTML =
                            '<div class="empty-state">No tasks found</div>';
                        return;
                    }

                    const tasksHtml = tasks.map(task => `
                        <div class="task-item" onclick="showTaskDetails('${task.id}')">
                            <div class="task-header">
                                <div class="task-desc">${task.description}</div>
                                <span class="badge badge-${task.status}">${task.status}</span>
                            </div>
                            <div class="task-meta">
                                <span>ID: ${task.id.substring(0, 8)}</span>
                                <span>•</span>
                                <span>${task.agent_type}</span>
                                <span>•</span>
                                <span>Priority: ${task.priority}</span>
                                ${task.assigned_to ? `<span>•</span><span>Agent: ${task.assigned_to}</span>` : ''}
                            </div>
                        </div>
                    `).join('');

                    document.getElementById('tasks-list').innerHTML = tasksHtml;
                });
        }

        // Load feedback tasks
        function loadFeedbackTasks() {
            fetch('/api/feedback-tasks')
                .then(r => r.json())
                .then(tasks => {
                    document.getElementById('feedback-count').textContent = `${tasks.length} feedback tasks`;

                    if (tasks.length === 0) {
                        document.getElementById('feedback-list').innerHTML =
                            '<div class="empty-state">No feedback tasks found</div>';
                        return;
                    }

                    const tasksHtml = tasks.map(task => {
                        const progress = (task.iterations / task.max_iterations) * 100;

                        return `
                            <div class="feedback-item" onclick="showFeedbackDetails('${task.task_id}')">
                                <div class="task-header">
                                    <div class="task-desc">${task.description}</div>
                                    <span class="badge badge-${task.status}">${task.status}</span>
                                </div>
                                <div class="task-meta">
                                    <span>🎯 ${task.criteria}</span>
                                    <span>•</span>
                                    <span>📊 ${task.progress} iterations</span>
                                    <span>•</span>
                                    <span>🔧 ${task.strategy}</span>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${progress}%"></div>
                                </div>
                            </div>
                        `;
                    }).join('');

                    document.getElementById('feedback-list').innerHTML = tasksHtml;

                    // Auto-select first task for metrics if none selected
                    if (!selectedFeedbackTask && tasks.length > 0) {
                        selectedFeedbackTask = tasks[0].task_id;
                        loadMetricsChart(selectedFeedbackTask);
                    }
                });
        }

        // Load agents
        function loadAgents() {
            fetch('/api/agents')
                .then(r => r.json())
                .then(agents => {
                    document.getElementById('agent-count').textContent = `${agents.length} agents`;

                    if (agents.length === 0) {
                        document.getElementById('agents-list').innerHTML =
                            '<div class="empty-state">No active agents</div>';
                        return;
                    }

                    const agentsHtml = agents.map(agent => `
                        <div class="agent-item">
                            <div class="task-header">
                                <div class="task-desc">
                                    <strong>${agent.agent_id}</strong>
                                    <div class="task-meta" style="margin-top: 8px;">
                                        <span>Type: ${agent.agent_type}</span>
                                        <span>•</span>
                                        <span>Task: ${agent.task_id.substring(0, 8)}</span>
                                        <span>•</span>
                                        <span>Duration: ${agent.duration}s</span>
                                    </div>
                                </div>
                                <div>
                                    <span class="badge badge-${agent.running ? 'running' : 'completed'}">
                                        ${agent.running ? 'Running' : 'Stopped'}
                                    </span>
                                    ${agent.running ? `
                                        <button class="btn" style="margin-left: 10px; padding: 4px 8px; font-size: 12px;"
                                                onclick="killAgent('${agent.agent_id}')">Kill</button>
                                    ` : ''}
                                </div>
                            </div>
                        </div>
                    `).join('');

                    document.getElementById('agents-list').innerHTML = agentsHtml;
                });
        }

        // Show task details
        function showTaskDetails(taskId) {
            fetch(`/api/task/${taskId}`)
                .then(r => r.json())
                .then(task => {
                    const modal = document.getElementById('task-modal');
                    const content = `
                        <h3>Task: ${taskId}</h3>
                        <p><strong>Description:</strong> ${task.description}</p>
                        <p><strong>Status:</strong> <span class="badge badge-${task.status}">${task.status}</span></p>
                        <p><strong>Agent Type:</strong> ${task.agent_type}</p>
                        <p><strong>Priority:</strong> ${task.priority}</p>
                        <p><strong>Created:</strong> ${new Date(task.created_at).toLocaleString()}</p>
                        ${task.assigned_to ? `<p><strong>Assigned To:</strong> ${task.assigned_to}</p>` : ''}
                        ${task.result ? `<p><strong>Result:</strong><pre>${task.result}</pre></p>` : ''}
                        ${task.error ? `<p><strong>Error:</strong><pre>${task.error}</pre></p>` : ''}
                    `;

                    document.getElementById('modal-content').innerHTML = content;
                    modal.style.display = 'flex';
                });
        }

        // Show feedback task details
        function showFeedbackDetails(taskId) {
            selectedFeedbackTask = taskId;
            loadMetricsChart(taskId);

            fetch(`/api/feedback-task/${taskId}`)
                .then(r => r.json())
                .then(task => {
                    const modal = document.getElementById('task-modal');

                    let historyHtml = '';
                    if (task.detailed_history && task.detailed_history.length > 0) {
                        historyHtml = '<h4>Iteration History:</h4>';
                        task.detailed_history.forEach(entry => {
                            const metrics = entry.metrics.details || entry.metrics;
                            let metricsHtml = '<div class="metrics-display">';

                            for (const [key, value] of Object.entries(metrics)) {
                                if (typeof value === 'object' && value.value !== undefined) {
                                    const met = value.met ? '✅' : '❌';
                                    metricsHtml += `
                                        <div class="metric-item">
                                            <div class="metric-name">${key} ${met}</div>
                                            <div class="metric-value">${value.value}</div>
                                        </div>
                                    `;
                                }
                            }
                            metricsHtml += '</div>';

                            historyHtml += `
                                <div style="margin: 15px 0; padding: 15px; background: #f9fafb; border-radius: 8px;">
                                    <h5>Iteration ${entry.iteration}:
                                        <span class="badge badge-${entry.result === 'success' ? 'completed' :
                                                                   entry.result === 'partial' ? 'running' : 'failed'}">
                                            ${entry.result}
                                        </span>
                                    </h5>
                                    ${metricsHtml}
                                    ${entry.refinement ? `<p style="margin-top: 10px; font-size: 12px; color: #6b7280;">
                                        <strong>Refinement:</strong> ${entry.refinement}</p>` : ''}
                                </div>
                            `;
                        });
                    }

                    const content = `
                        <h3>Feedback Task: ${taskId.substring(0, 8)}...</h3>
                        <p><strong>Description:</strong> ${task.description}</p>
                        <p><strong>Success Criteria:</strong> ${task.success_criteria}</p>
                        <p><strong>Progress:</strong> ${task.iterations}</p>
                        <p><strong>Status:</strong> <span class="badge badge-${task.status}">${task.status}</span></p>
                        ${historyHtml}
                    `;

                    document.getElementById('modal-content').innerHTML = content;
                    modal.style.display = 'flex';
                });
        }

        // Close modal
        function closeModal() {
            document.getElementById('task-modal').style.display = 'none';
        }

        // Kill agent
        function killAgent(agentId) {
            if (!confirm(`Kill agent ${agentId}?`)) return;

            fetch(`/api/kill-agent/${agentId}`, { method: 'POST' })
                .then(r => r.json())
                .then(result => {
                    if (result.success) {
                        alert(result.message);
                        loadAgents();
                    } else {
                        alert('Error: ' + result.error);
                    }
                });
        }

        // Update task distribution chart
        function updateTaskChart(stats) {
            const ctx = document.getElementById('task-chart');
            if (!ctx) return;

            if (taskChart) {
                taskChart.destroy();
            }

            taskChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Pending', 'Running', 'Completed', 'Failed'],
                    datasets: [{
                        data: [
                            stats.pending || 0,
                            stats.running || 0,
                            stats.completed || 0,
                            stats.failed || 0
                        ],
                        backgroundColor: [
                            '#fbbf24',
                            '#3b82f6',
                            '#10b981',
                            '#ef4444'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }

        // Load metrics chart for feedback task
        function loadMetricsChart(taskId) {
            fetch(`/api/metrics-chart/${taskId}`)
                .then(r => r.json())
                .then(data => {
                    const ctx = document.getElementById('metrics-chart');
                    if (!ctx) return;

                    if (metricsChart) {
                        metricsChart.destroy();
                    }

                    const datasets = [];
                    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];
                    let colorIndex = 0;

                    for (const [metric, values] of Object.entries(data.series)) {
                        datasets.push({
                            label: metric,
                            data: values,
                            borderColor: colors[colorIndex % colors.length],
                            backgroundColor: colors[colorIndex % colors.length] + '20',
                            tension: 0.3
                        });
                        colorIndex++;
                    }

                    metricsChart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: data.iterations.map(i => `Iteration ${i}`),
                            datasets: datasets
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: {
                                    position: 'bottom'
                                },
                                title: {
                                    display: true,
                                    text: 'Metrics Evolution'
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true
                                }
                            }
                        }
                    });
                });
        }

        // Auto-refresh checkbox
        document.getElementById('auto-refresh').addEventListener('change', (e) => {
            autoRefresh = e.target.checked;
        });

        // Auto refresh every 5 seconds
        setInterval(() => {
            if (autoRefresh && !document.hidden) {
                refreshAll();
            }
        }, 5000);

        // Initial load
        refreshAll();

        // Close modal on click outside
        window.onclick = function(event) {
            const modal = document.getElementById('task-modal');
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    monitor = EnhancedWebMonitor()
    monitor.run(debug=True)
