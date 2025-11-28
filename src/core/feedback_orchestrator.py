"""
Feedback Orchestrator - Manages iterative task refinement
"""

import json
import uuid
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
import time

from .feedback_loop import (
    ValidatedTask,
    SuccessCriteria,
    FeedbackEntry,
    EvaluationResult,
    FinancialEvaluator,
    DataScienceEvaluator,
    GeneralEvaluator,
)
from .task_queue import TaskQueue
from .agent_spawner import AgentSpawner
from .context_manager import ContextManager


class RefinementStrategy:
    """Base class for refinement strategies"""

    def generate_refinement(
        self, task: ValidatedTask, last_feedback: FeedbackEntry
    ) -> str:
        """Generate refined task description based on feedback"""
        raise NotImplementedError


class AdaptiveRefinementStrategy(RefinementStrategy):
    """Adapts task based on performance metrics"""

    def generate_refinement(
        self, task: ValidatedTask, last_feedback: FeedbackEntry
    ) -> str:
        """Generate adaptive refinement based on metrics"""
        base_desc = task.description
        metrics = last_feedback.metrics

        refinement_prompt = f"""
Previous attempt #{last_feedback.iteration}:
{base_desc}

Results:
{json.dumps(metrics, indent=2)}

Evaluation: {last_feedback.evaluation_result.value}

Please refine the approach based on these results. Focus on:
"""

        # Add specific guidance based on evaluation
        if last_feedback.evaluation_result == EvaluationResult.FAILURE:
            refinement_prompt += """
- Significant changes to the approach
- Address the failing metrics specifically
- Consider alternative algorithms or methods
"""
        elif last_feedback.evaluation_result == EvaluationResult.PARTIAL:
            refinement_prompt += """
- Fine-tune the parameters that are underperforming
- Maintain what's working while improving weak areas
- Make incremental improvements
"""

        # Add domain-specific hints
        if task.success_criteria.domain == "financial":
            refinement_prompt += self._add_financial_hints(metrics)
        elif task.success_criteria.domain == "data_science":
            refinement_prompt += self._add_ml_hints(metrics)

        return refinement_prompt

    def _add_financial_hints(self, metrics: Dict) -> str:
        hints = "\nFinancial optimization suggestions:\n"

        roi = metrics.get("details", {}).get("roi", {}).get("value")
        sharpe = metrics.get("details", {}).get("sharpe", {}).get("value")

        if roi is not None and roi < 10:
            hints += "- Consider more aggressive position sizing or entry signals\n"
        if sharpe is not None and sharpe < 1:
            hints += "- Focus on risk-adjusted returns, reduce volatility\n"

        max_dd = metrics.get("details", {}).get("max_drawdown", {}).get("value")
        if max_dd is not None and abs(max_dd) > 20:
            hints += "- Implement better risk management and stop-loss strategies\n"

        return hints

    def _add_ml_hints(self, metrics: Dict) -> str:
        hints = "\nML optimization suggestions:\n"

        accuracy = metrics.get("details", {}).get("accuracy", {}).get("value")
        if accuracy is not None and accuracy < 0.8:
            hints += "- Try feature engineering or different model architectures\n"

        precision = metrics.get("details", {}).get("precision", {}).get("value")
        recall = metrics.get("details", {}).get("recall", {}).get("value")

        if precision and recall:
            if precision < recall:
                hints += "- Adjust threshold to reduce false positives\n"
            elif recall < precision:
                hints += "- Adjust threshold to reduce false negatives\n"

        return hints


class GridSearchRefinementStrategy(RefinementStrategy):
    """Systematic parameter exploration"""

    def __init__(self, parameter_grid: Dict[str, List[Any]]):
        self.parameter_grid = parameter_grid
        self.current_combination = 0

    def generate_refinement(
        self, task: ValidatedTask, last_feedback: FeedbackEntry
    ) -> str:
        """Generate next parameter combination"""
        # Calculate total combinations
        import itertools

        combinations = list(itertools.product(*self.parameter_grid.values()))

        if self.current_combination >= len(combinations):
            return task.description  # Exhausted grid

        params = dict(
            zip(self.parameter_grid.keys(), combinations[self.current_combination])
        )
        self.current_combination += 1

        return f"{task.description}\n\nUse these parameters:\n{json.dumps(params, indent=2)}"


class FeedbackOrchestrator:
    """Orchestrates the feedback loop for iterative task refinement"""

    def __init__(self, db_path: str = "tasks.db"):
        self.db_path = db_path
        self.task_queue = TaskQueue(db_path)
        self.agent_spawner = AgentSpawner()
        self.context_manager = ContextManager()

        # Register evaluators
        self.evaluators = [
            FinancialEvaluator(),
            DataScienceEvaluator(),
            GeneralEvaluator(),
        ]

        # Initialize feedback tables
        self._init_feedback_tables()

    def _init_feedback_tables(self):
        """Create tables for feedback loop data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validated_tasks (
                task_id TEXT PRIMARY KEY,
                description TEXT,
                agent_type TEXT,
                success_criteria TEXT,
                max_iterations INTEGER,
                iteration_count INTEGER,
                refinement_strategy TEXT,
                parent_task_id TEXT,
                status TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                iteration INTEGER,
                timestamp TIMESTAMP,
                evaluation_result TEXT,
                metrics TEXT,
                refinement_applied TEXT,
                agent_output TEXT,
                FOREIGN KEY (task_id) REFERENCES validated_tasks(task_id)
            )
        """)

        conn.commit()
        conn.close()

    def submit_validated_task(
        self,
        description: str,
        success_criteria: SuccessCriteria,
        agent_type: str = "auto",
        max_iterations: int = 5,
        refinement_strategy: str = "adaptive",
        parameter_grid: Optional[Dict] = None,
    ) -> ValidatedTask:
        """Submit a task with success validation"""
        task_id = str(uuid.uuid4())

        task = ValidatedTask(
            task_id=task_id,
            description=description,
            agent_type=agent_type,
            success_criteria=success_criteria,
            max_iterations=max_iterations,
            refinement_strategy=refinement_strategy,
        )

        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO validated_tasks
            (task_id, description, agent_type, success_criteria, max_iterations,
             iteration_count, refinement_strategy, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task.task_id,
                task.description,
                task.agent_type,
                json.dumps(task.success_criteria.to_dict()),
                task.max_iterations,
                0,
                task.refinement_strategy,
                "pending",
                datetime.now(),
                datetime.now(),
            ),
        )

        conn.commit()
        conn.close()

        # Also submit to regular task queue for processing
        self.task_queue.add_task(
            description, agent_type, metadata={"validated_task_id": task_id}
        )

        return task

    def process_feedback_loop(self, task_id: str) -> Dict[str, Any]:
        """Main feedback loop processor"""
        task = self._load_validated_task(task_id)
        if not task:
            return {"error": f"Task {task_id} not found"}

        results = []

        while task.should_continue():
            task.iteration_count += 1

            print(f"\n🔄 Iteration {task.iteration_count}/{task.max_iterations}")

            # Get current task description (may be refined)
            current_description = self._get_current_description(task)

            # Execute task via agent
            print(f"📝 Executing: {current_description[:100]}...")
            output = self._execute_task(current_description, task.agent_type)

            # Evaluate output
            print("🔍 Evaluating results...")
            evaluation, metrics = self._evaluate_output(output, task.success_criteria)

            # Record feedback
            feedback = FeedbackEntry(
                iteration=task.iteration_count,
                timestamp=datetime.now(),
                evaluation_result=evaluation,
                metrics=metrics,
                refinement_applied=None,
                agent_output=output[:1000],  # Truncate for storage
            )

            task.feedback_history.append(feedback)
            self._save_feedback(task.task_id, feedback)

            results.append(
                {
                    "iteration": task.iteration_count,
                    "evaluation": evaluation.value,
                    "metrics": metrics,
                }
            )

            print(f"✅ Evaluation: {evaluation.value}")
            print(f"📊 Metrics: {json.dumps(metrics, indent=2)}")

            # Check if successful
            if evaluation == EvaluationResult.SUCCESS:
                print(f"🎉 Success achieved in {task.iteration_count} iterations!")
                task.status = "completed"
                break

            # Apply refinement if needed
            if task.should_continue():
                print("🔧 Applying refinement strategy...")
                refinement = self._apply_refinement(task, feedback)
                feedback.refinement_applied = refinement[:500]  # Store truncated

        # Update task status
        self._update_task_status(task)

        return {
            "task_id": task_id,
            "iterations": task.iteration_count,
            "final_status": task.status,
            "results": results,
        }

    def _load_validated_task(self, task_id: str) -> Optional[ValidatedTask]:
        """Load task from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM validated_tasks WHERE task_id = ?
        """,
            (task_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        # Load feedback history
        cursor.execute(
            """
            SELECT * FROM feedback_history WHERE task_id = ? ORDER BY iteration
        """,
            (task_id,),
        )

        feedback_rows = cursor.fetchall()
        conn.close()

        # Reconstruct task
        task = ValidatedTask(
            task_id=row[0],
            description=row[1],
            agent_type=row[2],
            success_criteria=SuccessCriteria.from_dict(json.loads(row[3])),
            max_iterations=row[4],
            iteration_count=row[5],
            refinement_strategy=row[6],
            parent_task_id=row[7],
            status=row[8],
        )

        # Add feedback history
        for fb_row in feedback_rows:
            feedback = FeedbackEntry(
                iteration=fb_row[2],
                timestamp=datetime.fromisoformat(fb_row[3]),
                evaluation_result=EvaluationResult(fb_row[4]),
                metrics=json.loads(fb_row[5]),
                refinement_applied=fb_row[6],
                agent_output=fb_row[7],
            )
            task.feedback_history.append(feedback)

        return task

    def _execute_task(self, description: str, agent_type: str) -> str:
        """Execute task through agent and return output"""
        # Create a regular task
        task_id = self.task_queue.add_task(description, agent_type)

        # Spawn agent
        agent_id = self.agent_spawner.spawn_agent(agent_type)

        # Wait for completion (with timeout)
        timeout = 300  # 5 minutes
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if agent completed
            agent_context = self.context_manager.read_agent_context(agent_id)
            if agent_context and agent_context.get("status") == "completed":
                return agent_context.get("output", "")

            time.sleep(5)

        return "Task execution timeout"

    def _evaluate_output(
        self, output: str, criteria: SuccessCriteria
    ) -> tuple[EvaluationResult, Dict]:
        """Evaluate task output using appropriate evaluator"""
        for evaluator in self.evaluators:
            if evaluator.supports_domain(criteria.domain):
                return evaluator.evaluate(output, criteria)

        return EvaluationResult.ERROR, {"error": "No suitable evaluator found"}

    def _get_current_description(self, task: ValidatedTask) -> str:
        """Get task description, possibly refined"""
        if task.iteration_count == 1:
            return task.description

        # Get refinement strategy
        strategy = self._get_refinement_strategy(task)
        if strategy and task.feedback_history:
            return strategy.generate_refinement(task, task.feedback_history[-1])

        return task.description

    def _apply_refinement(self, task: ValidatedTask, feedback: FeedbackEntry) -> str:
        """Apply refinement strategy to generate new task description"""
        strategy = self._get_refinement_strategy(task)
        if strategy:
            return strategy.generate_refinement(task, feedback)
        return ""

    def _get_refinement_strategy(
        self, task: ValidatedTask
    ) -> Optional[RefinementStrategy]:
        """Get appropriate refinement strategy"""
        if task.refinement_strategy == "adaptive":
            return AdaptiveRefinementStrategy()
        elif task.refinement_strategy == "grid_search":
            # Would need parameter grid from task metadata
            return GridSearchRefinementStrategy({})
        return None

    def _save_feedback(self, task_id: str, feedback: FeedbackEntry):
        """Save feedback to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO feedback_history
            (task_id, iteration, timestamp, evaluation_result, metrics,
             refinement_applied, agent_output)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task_id,
                feedback.iteration,
                feedback.timestamp,
                feedback.evaluation_result.value,
                json.dumps(feedback.metrics),
                feedback.refinement_applied,
                feedback.agent_output,
            ),
        )

        conn.commit()
        conn.close()

    def _update_task_status(self, task: ValidatedTask):
        """Update task status in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE validated_tasks
            SET status = ?, iteration_count = ?, updated_at = ?
            WHERE task_id = ?
        """,
            (task.status, task.iteration_count, datetime.now(), task.task_id),
        )

        conn.commit()
        conn.close()

    def get_feedback_status(self, task_id: str) -> Dict[str, Any]:
        """Get current status of feedback loop"""
        task = self._load_validated_task(task_id)
        if not task:
            return {"error": "Task not found"}

        return {
            "task_id": task_id,
            "description": task.description[:100],
            "iterations": f"{task.iteration_count}/{task.max_iterations}",
            "status": task.status,
            "success_criteria": task.success_criteria.description,
            "history": [
                {
                    "iteration": fb.iteration,
                    "result": fb.evaluation_result.value,
                    "metrics": fb.metrics,
                }
                for fb in task.feedback_history
            ],
        }


if __name__ == "__main__":
    # Test the feedback orchestrator
    orchestrator = FeedbackOrchestrator()

    # Example: Submit a trading algorithm task with ROI target
    criteria = SuccessCriteria(
        criteria_type="threshold",
        parameters={
            "roi": {"operator": ">", "value": 15},
            "sharpe": {"operator": ">", "value": 1.5},
        },
        domain="financial",
        description="Achieve ROI > 15% and Sharpe > 1.5",
    )

    task = orchestrator.submit_validated_task(
        description="Develop a momentum trading strategy for S&P 500 stocks",
        success_criteria=criteria,
        agent_type="data-science-analyst",
        max_iterations=3,
    )

    print(f"Created validated task: {task.task_id}")
    print(f"Success criteria: {task.success_criteria.description}")
