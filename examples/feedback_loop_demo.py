#!/usr/bin/env python3
"""
Demonstration of Feedback Loop System

This script shows how to use the feedback loop system for iterative task refinement.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.feedback_orchestrator import FeedbackOrchestrator, SuccessCriteria
import time


def demo_financial_trading():
    """Demo: Trading algorithm optimization with feedback loop"""
    print("=" * 60)
    print("DEMO: Financial Trading Algorithm with Feedback Loop")
    print("=" * 60)

    orchestrator = FeedbackOrchestrator()

    # Define success criteria for trading algorithm
    criteria = SuccessCriteria(
        criteria_type="multi_objective",
        parameters={
            "objectives": [
                {"metric": "roi", "target": 15, "weight": 2.0, "higher_better": True},
                {
                    "metric": "sharpe",
                    "target": 2.0,
                    "weight": 1.5,
                    "higher_better": True,
                },
                {
                    "metric": "max_drawdown",
                    "target": -10,
                    "weight": 1.0,
                    "higher_better": False,
                },
            ],
            "success_threshold": 0.85,  # 85% of weighted objectives
            "partial_threshold": 0.60,
        },
        domain="financial",
        description="Achieve ROI>15%, Sharpe>2.0, MaxDD<10%",
    )

    # Submit task with feedback loop
    task = orchestrator.submit_validated_task(
        description="""
        Develop a momentum-based trading strategy for S&P 500 stocks with the following requirements:
        - Use 20-day and 50-day moving averages for signals
        - Implement position sizing based on volatility
        - Include stop-loss at 2% and take-profit at 5%
        - Backtest on 2023 data
        - Report key metrics: ROI, Sharpe ratio, Max Drawdown, Win Rate
        """,
        success_criteria=criteria,
        agent_type="data-science-analyst",
        max_iterations=4,
        refinement_strategy="adaptive",
    )

    print(f"\n📋 Task ID: {task.task_id}")
    print(f"🎯 Success Criteria: {criteria.description}")
    print("🔄 Max Iterations: 4")
    print("🎨 Strategy: Adaptive Refinement")

    print("\n" + "-" * 40)
    print("Starting Feedback Loop...")
    print("-" * 40)

    # Simulate processing
    results = simulate_feedback_loop(orchestrator, task.task_id)

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total Iterations: {results['iterations']}")
    print(f"Final Status: {results['final_status']}")

    return results


def demo_ml_model_optimization():
    """Demo: ML model optimization with feedback loop"""
    print("\n" * 2)
    print("=" * 60)
    print("DEMO: ML Model Optimization with Feedback Loop")
    print("=" * 60)

    orchestrator = FeedbackOrchestrator()

    # Define success criteria for ML model
    criteria = SuccessCriteria(
        criteria_type="threshold",
        parameters={"accuracy": 0.92, "f1_score": 0.90, "precision": 0.88},
        domain="data_science",
        description="Accuracy>0.92, F1>0.90, Precision>0.88",
    )

    # Submit task with feedback loop
    task = orchestrator.submit_validated_task(
        description="""
        Build a customer churn prediction model with the following:
        - Use gradient boosting (XGBoost or LightGBM)
        - Perform feature engineering on customer behavior data
        - Implement cross-validation with stratified splits
        - Handle class imbalance with SMOTE or class weights
        - Report metrics: Accuracy, Precision, Recall, F1, AUC
        """,
        success_criteria=criteria,
        agent_type="data-science-analyst",
        max_iterations=5,
        refinement_strategy="adaptive",
    )

    print(f"\n📋 Task ID: {task.task_id}")
    print(f"🎯 Success Criteria: {criteria.description}")
    print("🔄 Max Iterations: 5")
    print("🎨 Strategy: Adaptive Refinement")

    print("\n" + "-" * 40)
    print("Starting Feedback Loop...")
    print("-" * 40)

    # Simulate processing
    results = simulate_feedback_loop(orchestrator, task.task_id)

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total Iterations: {results['iterations']}")
    print(f"Final Status: {results['final_status']}")

    return results


def demo_grid_search_optimization():
    """Demo: Grid search parameter optimization"""
    print("\n" * 2)
    print("=" * 60)
    print("DEMO: Grid Search Parameter Optimization")
    print("=" * 60)

    orchestrator = FeedbackOrchestrator()

    # Define success criteria
    criteria = SuccessCriteria(
        criteria_type="range",
        parameters={"rmse": {"min": 0, "max": 0.05}, "mae": {"min": 0, "max": 0.03}},
        domain="data_science",
        description="RMSE in [0, 0.05], MAE in [0, 0.03]",
    )

    # Parameter grid for systematic exploration
    parameter_grid = {
        "learning_rate": [0.01, 0.05, 0.1],
        "max_depth": [3, 5, 7],
        "n_estimators": [100, 200, 300],
    }

    task = orchestrator.submit_validated_task(
        description="""
        Optimize regression model hyperparameters:
        - Test different combinations of learning_rate, max_depth, n_estimators
        - Use time series cross-validation
        - Report RMSE and MAE for each combination
        """,
        success_criteria=criteria,
        agent_type="data-science-analyst",
        max_iterations=9,  # 3x3x1 grid
        refinement_strategy="grid_search",
    )

    print(f"\n📋 Task ID: {task.task_id}")
    print(f"🎯 Success Criteria: {criteria.description}")
    print(f"🔄 Parameter Grid: {parameter_grid}")
    print("🎨 Strategy: Grid Search")

    # Simulate processing
    results = simulate_feedback_loop(orchestrator, task.task_id)

    return results


def simulate_feedback_loop(orchestrator, task_id):
    """Simulate the feedback loop execution"""
    # This simulates what would happen when agents actually run

    # Mock results for demonstration
    mock_iterations = [
        {
            "iteration": 1,
            "evaluation": "failure",
            "metrics": {
                "details": {
                    "roi": {"value": 8.5, "target": 15, "met": False},
                    "sharpe": {"value": 1.2, "target": 2.0, "met": False},
                    "max_drawdown": {"value": -18, "target": -10, "met": False},
                }
            },
        },
        {
            "iteration": 2,
            "evaluation": "partial",
            "metrics": {
                "details": {
                    "roi": {"value": 12.3, "target": 15, "met": False},
                    "sharpe": {"value": 1.8, "target": 2.0, "met": False},
                    "max_drawdown": {"value": -12, "target": -10, "met": False},
                }
            },
        },
        {
            "iteration": 3,
            "evaluation": "partial",
            "metrics": {
                "details": {
                    "roi": {"value": 16.2, "target": 15, "met": True},
                    "sharpe": {"value": 2.1, "target": 2.0, "met": True},
                    "max_drawdown": {"value": -11, "target": -10, "met": False},
                }
            },
        },
        {
            "iteration": 4,
            "evaluation": "success",
            "metrics": {
                "details": {
                    "roi": {"value": 17.5, "target": 15, "met": True},
                    "sharpe": {"value": 2.3, "target": 2.0, "met": True},
                    "max_drawdown": {"value": -8.5, "target": -10, "met": True},
                }
            },
        },
    ]

    for i, iteration_result in enumerate(mock_iterations, 1):
        print(f"\n🔄 Iteration {i}")
        print(f"   📊 Evaluation: {iteration_result['evaluation'].upper()}")

        if "details" in iteration_result["metrics"]:
            for metric, data in iteration_result["metrics"]["details"].items():
                status = "✅" if data.get("met", False) else "❌"
                print(
                    f"   {status} {metric}: {data['value']} (target: {data['target']})"
                )

        time.sleep(0.5)  # Simulate processing time

        if iteration_result["evaluation"] == "success":
            print(f"\n🎉 SUCCESS! Achieved all targets in {i} iterations")
            break

    return {
        "iterations": len(mock_iterations),
        "final_status": "completed",
        "results": mock_iterations,
    }


def main():
    """Run all demonstrations"""
    print("\n" + "🚀 " * 20)
    print("FEEDBACK LOOP SYSTEM DEMONSTRATION")
    print("🚀 " * 20)

    # Demo 1: Financial Trading
    financial_results = demo_financial_trading()

    # Demo 2: ML Model Optimization
    ml_results = demo_ml_model_optimization()

    # Demo 3: Grid Search
    # grid_results = demo_grid_search_optimization()

    print("\n" * 2)
    print("=" * 60)
    print("ALL DEMOS COMPLETED")
    print("=" * 60)

    print("\n📊 Summary:")
    print(f"   Financial Trading: {financial_results['final_status']}")
    print(f"   ML Model: {ml_results['final_status']}")
    # print(f"   Grid Search: {grid_results['final_status']}")

    print("\n💡 Key Features Demonstrated:")
    print("   ✅ Multi-objective optimization (weighted goals)")
    print("   ✅ Threshold-based criteria")
    print("   ✅ Range-based validation")
    print("   ✅ Adaptive refinement strategy")
    print("   ✅ Domain-specific evaluators (Financial & ML)")
    print("   ✅ Automatic iteration and convergence")

    print("\n🎯 Usage:")
    print("   ./orchestrate submit-validated 'Your task' -d financial")
    print("   ./orchestrate feedback-run <task-id>")
    print("   ./orchestrate feedback-status")


if __name__ == "__main__":
    main()
