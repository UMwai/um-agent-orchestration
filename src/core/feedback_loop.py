"""
Feedback Loop System for Iterative Task Refinement
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime
from abc import ABC, abstractmethod


class EvaluationResult(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    ERROR = "error"


@dataclass
class SuccessCriteria:
    """Defines measurable success conditions for a task"""

    criteria_type: str  # 'threshold', 'range', 'multi_objective', 'custom'
    parameters: Dict[str, Any]
    domain: str  # 'financial', 'data_science', 'general', etc.
    description: str

    def to_dict(self):
        return {
            "criteria_type": self.criteria_type,
            "parameters": self.parameters,
            "domain": self.domain,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class FeedbackEntry:
    """Records a single iteration's results"""

    iteration: int
    timestamp: datetime
    evaluation_result: EvaluationResult
    metrics: Dict[str, Any]
    refinement_applied: Optional[str]
    agent_output: str

    def to_dict(self):
        return {
            "iteration": self.iteration,
            "timestamp": self.timestamp.isoformat(),
            "evaluation_result": self.evaluation_result.value,
            "metrics": self.metrics,
            "refinement_applied": self.refinement_applied,
            "agent_output": self.agent_output,
        }


@dataclass
class ValidatedTask:
    """Task with success validation and feedback capabilities"""

    task_id: str
    description: str
    agent_type: str
    success_criteria: SuccessCriteria
    max_iterations: int = 5
    iteration_count: int = 0
    feedback_history: List[FeedbackEntry] = field(default_factory=list)
    refinement_strategy: str = (
        "adaptive"  # 'adaptive', 'grid_search', 'bayesian', 'manual'
    )
    parent_task_id: Optional[str] = None
    status: str = "pending"

    def should_continue(self) -> bool:
        """Check if we should continue iterating"""
        if self.iteration_count >= self.max_iterations:
            return False
        if self.feedback_history:
            last_result = self.feedback_history[-1].evaluation_result
            return last_result not in [EvaluationResult.SUCCESS, EvaluationResult.ERROR]
        return True

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "description": self.description,
            "agent_type": self.agent_type,
            "success_criteria": self.success_criteria.to_dict(),
            "max_iterations": self.max_iterations,
            "iteration_count": self.iteration_count,
            "feedback_history": [f.to_dict() for f in self.feedback_history],
            "refinement_strategy": self.refinement_strategy,
            "parent_task_id": self.parent_task_id,
            "status": self.status,
        }


class Evaluator(ABC):
    """Base class for success evaluators"""

    @abstractmethod
    def evaluate(
        self, output: str, criteria: SuccessCriteria
    ) -> tuple[EvaluationResult, Dict[str, Any]]:
        """Evaluate task output against success criteria"""
        pass

    @abstractmethod
    def supports_domain(self, domain: str) -> bool:
        """Check if this evaluator handles the given domain"""
        pass


class FinancialEvaluator(Evaluator):
    """Evaluator for financial metrics"""

    def supports_domain(self, domain: str) -> bool:
        return domain in ["financial", "trading", "investment"]

    def evaluate(
        self, output: str, criteria: SuccessCriteria
    ) -> tuple[EvaluationResult, Dict[str, Any]]:
        """Evaluate financial metrics like ROI, Sharpe ratio, etc."""
        metrics = self._extract_metrics(output)

        if criteria.criteria_type == "threshold":
            return self._evaluate_threshold(metrics, criteria.parameters)
        elif criteria.criteria_type == "multi_objective":
            return self._evaluate_multi_objective(metrics, criteria.parameters)

        return EvaluationResult.ERROR, {"error": "Unsupported criteria type"}

    def _extract_metrics(self, output: str) -> Dict[str, float]:
        """Extract financial metrics from agent output"""
        metrics = {}

        # Parse common financial metrics from output
        import re

        patterns = {
            "roi": r"ROI[:\s]+([+-]?\d+\.?\d*)%?",
            "sharpe": r"Sharpe[:\s]+([+-]?\d+\.?\d*)",
            "max_drawdown": r"Max Drawdown[:\s]+([+-]?\d+\.?\d*)%?",
            "win_rate": r"Win Rate[:\s]+(\d+\.?\d*)%?",
            "profit_factor": r"Profit Factor[:\s]+(\d+\.?\d*)",
            "annual_return": r"Annual Return[:\s]+([+-]?\d+\.?\d*)%?",
        }

        for metric, pattern in patterns.items():
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                value = match.group(1).replace("%", "")
                metrics[metric] = float(value)

        return metrics

    def _evaluate_threshold(
        self, metrics: Dict, params: Dict
    ) -> tuple[EvaluationResult, Dict]:
        """Evaluate threshold-based criteria"""
        results = {}
        all_met = True

        for metric_name, threshold in params.items():
            if metric_name in metrics:
                value = metrics[metric_name]
                operator = threshold.get("operator", ">")
                target = threshold.get("value")

                if operator == ">":
                    met = value > target
                elif operator == ">=":
                    met = value >= target
                elif operator == "<":
                    met = value < target
                elif operator == "<=":
                    met = value <= target
                else:
                    met = False

                results[metric_name] = {"value": value, "target": target, "met": met}
                all_met = all_met and met
            else:
                results[metric_name] = {"error": "Metric not found in output"}
                all_met = False

        if all_met:
            return EvaluationResult.SUCCESS, results
        elif any(r.get("met", False) for r in results.values()):
            return EvaluationResult.PARTIAL, results
        else:
            return EvaluationResult.FAILURE, results

    def _evaluate_multi_objective(
        self, metrics: Dict, params: Dict
    ) -> tuple[EvaluationResult, Dict]:
        """Evaluate multiple objectives with weights"""
        results = {}
        total_score = 0
        total_weight = 0

        for objective in params["objectives"]:
            metric_name = objective["metric"]
            weight = objective.get("weight", 1.0)

            if metric_name in metrics:
                value = metrics[metric_name]
                target = objective["target"]

                # Normalize score (0-1)
                if objective.get("higher_better", True):
                    score = min(value / target, 1.0) if target > 0 else 0
                else:
                    score = min(target / value, 1.0) if value > 0 else 0

                results[metric_name] = {
                    "value": value,
                    "target": target,
                    "score": score,
                    "weight": weight,
                }

                total_score += score * weight
                total_weight += weight

        final_score = total_score / total_weight if total_weight > 0 else 0

        if final_score >= params.get("success_threshold", 0.8):
            return EvaluationResult.SUCCESS, {"score": final_score, "details": results}
        elif final_score >= params.get("partial_threshold", 0.5):
            return EvaluationResult.PARTIAL, {"score": final_score, "details": results}
        else:
            return EvaluationResult.FAILURE, {"score": final_score, "details": results}


class DataScienceEvaluator(Evaluator):
    """Evaluator for data science and ML metrics"""

    def supports_domain(self, domain: str) -> bool:
        return domain in ["data_science", "machine_learning", "ml", "ai"]

    def evaluate(
        self, output: str, criteria: SuccessCriteria
    ) -> tuple[EvaluationResult, Dict[str, Any]]:
        """Evaluate ML metrics like accuracy, F1, AUC, etc."""
        metrics = self._extract_metrics(output)

        if criteria.criteria_type == "threshold":
            return self._evaluate_threshold(metrics, criteria.parameters)
        elif criteria.criteria_type == "range":
            return self._evaluate_range(metrics, criteria.parameters)

        return EvaluationResult.ERROR, {"error": "Unsupported criteria type"}

    def _extract_metrics(self, output: str) -> Dict[str, float]:
        """Extract ML metrics from agent output"""
        metrics = {}

        import re

        patterns = {
            "accuracy": r"Accuracy[:\s]+(\d+\.?\d*)%?",
            "precision": r"Precision[:\s]+(\d+\.?\d*)",
            "recall": r"Recall[:\s]+(\d+\.?\d*)",
            "f1_score": r"F1[:\s]+(\d+\.?\d*)",
            "auc": r"AUC[:\s]+(\d+\.?\d*)",
            "rmse": r"RMSE[:\s]+(\d+\.?\d*)",
            "mae": r"MAE[:\s]+(\d+\.?\d*)",
            "r2": r"R2[:\s]+(\d+\.?\d*)",
            "mse": r"MSE[:\s]+(\d+\.?\d*)",
        }

        for metric, pattern in patterns.items():
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                value = match.group(1).replace("%", "")
                metrics[metric] = float(value)

        return metrics

    def _evaluate_threshold(
        self, metrics: Dict, params: Dict
    ) -> tuple[EvaluationResult, Dict]:
        """Similar to FinancialEvaluator but for ML metrics"""
        results = {}
        all_met = True

        for metric_name, threshold in params.items():
            if metric_name in metrics:
                value = metrics[metric_name]
                met = (
                    value >= threshold if isinstance(threshold, (int, float)) else False
                )

                results[metric_name] = {"value": value, "target": threshold, "met": met}
                all_met = all_met and met

        if all_met:
            return EvaluationResult.SUCCESS, results
        elif any(r.get("met", False) for r in results.values()):
            return EvaluationResult.PARTIAL, results
        else:
            return EvaluationResult.FAILURE, results

    def _evaluate_range(
        self, metrics: Dict, params: Dict
    ) -> tuple[EvaluationResult, Dict]:
        """Evaluate if metrics fall within acceptable ranges"""
        results = {}
        all_met = True

        for metric_name, range_spec in params.items():
            if metric_name in metrics:
                value = metrics[metric_name]
                min_val = range_spec.get("min", float("-inf"))
                max_val = range_spec.get("max", float("inf"))

                met = min_val <= value <= max_val

                results[metric_name] = {
                    "value": value,
                    "range": [min_val, max_val],
                    "met": met,
                }
                all_met = all_met and met

        if all_met:
            return EvaluationResult.SUCCESS, results
        else:
            return EvaluationResult.FAILURE, results


class GeneralEvaluator(Evaluator):
    """Evaluator for general success criteria using LLM judgment"""

    def supports_domain(self, domain: str) -> bool:
        return True  # Can handle any domain as fallback

    def evaluate(
        self, output: str, criteria: SuccessCriteria
    ) -> tuple[EvaluationResult, Dict[str, Any]]:
        """Use LLM to evaluate against custom criteria"""
        # This would use Claude to evaluate if custom criteria are met
        # For now, returning a placeholder
        return EvaluationResult.PARTIAL, {
            "note": "General evaluation requires LLM judgment",
            "criteria": criteria.description,
        }
