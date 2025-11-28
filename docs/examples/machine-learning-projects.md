# Machine Learning Project Examples

## End-to-End ML System for Production

### Scenario
Build a complete ML system for customer churn prediction with real-time scoring, A/B testing, and monitoring.

### Interactive Planning

```bash
./orchestrate plan "Build production ML system for customer churn prediction with real-time inference"
```

#### Planning Session
```
Claude: Let's design your ML system. Key questions:
1. Data volume and velocity?
2. Latency requirements for predictions?
3. Model retraining frequency?
4. Existing infrastructure?

User: 1M customers, <100ms latency, weekly retraining, AWS infrastructure

Claude: Excellent. Here's my comprehensive plan:

Phase 1: Data Foundation (Day 1-2)
- Feature engineering pipeline
- Training/validation/test splits
- Feature store implementation

Phase 2: Model Development (Day 3-4)
- Baseline model (logistic regression)
- Advanced models (XGBoost, Neural Network)
- Hyperparameter optimization
- Model evaluation framework

Phase 3: Production Infrastructure (Day 5-6)
- Model serving with SageMaker endpoints
- A/B testing framework
- Real-time feature computation

Phase 4: Monitoring & Operations (Day 7)
- Model drift detection
- Performance monitoring dashboards
- Automated retraining pipeline
- Alerting system

Would you like to modify any phase? [a]dd, [m]odify, [p]roceed
```

### Execution

```bash
# Execute with multiple specialized agents
./orchestrate execute-plan ml-churn-system

# Run with optimal parallelism
./orchestrate run --max-agents 4
```

### Expected Architecture

```
ml-system/
├── feature-engineering/
│   ├── pipelines/
│   │   ├── user_features.py
│   │   ├── transaction_features.py
│   │   └── engagement_features.py
│   └── feature_store/
│       ├── offline_features.py
│       └── online_features.py
├── models/
│   ├── training/
│   │   ├── baseline_model.py
│   │   ├── xgboost_model.py
│   │   └── neural_network.py
│   ├── evaluation/
│   │   └── metrics.py
│   └── serving/
│       └── inference_pipeline.py
├── infrastructure/
│   ├── sagemaker/
│   │   ├── endpoints.yaml
│   │   └── training_jobs.yaml
│   └── monitoring/
│       ├── model_monitor.py
│       └── dashboards/
└── tests/
    ├── unit/
    ├── integration/
    └── load/
```

## Computer Vision Pipeline

### Scenario
Build an image classification system for quality control in manufacturing with edge deployment.

### Task Submission

```bash
# Submit with decomposition for complex CV project
./orchestrate submit "Build defect detection system using computer vision for manufacturing QC with edge deployment" --decompose
```

### Automated Task Breakdown
1. **Data pipeline setup** (data-pipeline-engineer)
   - Image ingestion from cameras
   - Data labeling workflow
   - Augmentation pipeline

2. **Model development** (ml-systems-architect)
   - CNN architecture design
   - Transfer learning implementation
   - Model optimization for edge

3. **Training infrastructure** (data-science-analyst)
   - Distributed training setup
   - Experiment tracking with MLflow
   - Hyperparameter tuning

4. **Edge deployment** (aws-cloud-architect)
   - Model quantization
   - Edge device setup
   - OTA update mechanism

### Monitoring Progress

```bash
# Check specialist progress
./orchestrate agents

# Output:
# 🤖 Active Agents:
# [ml-systems-architect]: Implementing EfficientNet with transfer learning
# [data-pipeline-engineer]: Setting up image augmentation pipeline
# [aws-cloud-architect]: Configuring IoT Greengrass for edge deployment
```

## NLP System for Document Processing

### Scenario
Create an intelligent document processing system using transformer models for contract analysis.

### Phased Development

```bash
# Interactive planning for NLP project
./orchestrate plan "Build NLP system for legal contract analysis with entity extraction and risk scoring"
```

### Implementation Phases

```python
# Phase 1: Document Processing Pipeline
# - PDF text extraction
# - Document preprocessing
# - Section identification

# Phase 2: NLP Models
# - Named entity recognition (NER)
# - Clause classification
# - Risk assessment scoring

# Phase 3: Fine-tuning
# - Domain-specific BERT fine-tuning
# - Custom entity training
# - Validation on legal corpus

# Phase 4: API Development
# - REST API for document upload
# - Async processing queue
# - Results storage and retrieval
```

### Execution with Specialists

```bash
# Run with ML and backend specialists
./orchestrate run --max-agents 3

# Agents collaborate:
# - ml-systems-architect: Designs transformer architecture
# - data-science-analyst: Prepares training data and evaluates models
# - backend-systems-engineer: Builds serving infrastructure
```

## Recommendation System

### Scenario
Build a hybrid recommendation system combining collaborative filtering, content-based, and deep learning approaches.

### Quick Start

```bash
# Direct submission for recommendation system
./orchestrate submit "Create recommendation system with collaborative filtering, content-based, and neural collaborative filtering" \
  --agent ml-systems-architect \
  --priority high
```

### Expected Implementation

```python
# recommendation_system/models.py

class HybridRecommender:
    def __init__(self):
        self.collaborative_filter = CollaborativeFiltering()
        self.content_based = ContentBasedFiltering()
        self.neural_cf = NeuralCollaborativeFiltering()

    def train(self, interactions, item_features, user_features):
        # Train all components
        self.collaborative_filter.fit(interactions)
        self.content_based.fit(item_features)
        self.neural_cf.fit(interactions, user_features)

    def predict(self, user_id, candidate_items):
        # Ensemble predictions
        cf_scores = self.collaborative_filter.predict(user_id, candidate_items)
        cb_scores = self.content_based.predict(user_id, candidate_items)
        ncf_scores = self.neural_cf.predict(user_id, candidate_items)

        # Weighted ensemble
        return self.ensemble(cf_scores, cb_scores, ncf_scores)
```

## Time Series Forecasting

### Scenario
Implement multi-variate time series forecasting for demand prediction across multiple products and locations.

### Planning Session

```bash
./orchestrate plan "Build time series forecasting system for demand prediction with Prophet, LSTM, and ensemble methods"
```

### Parallel Development

```bash
# Multiple agents work on different approaches
./orchestrate run --max-agents 3

# Simultaneous development:
# Agent 1: Implements Prophet for trend/seasonality
# Agent 2: Builds LSTM for complex patterns
# Agent 3: Creates ensemble framework
```

### Output Structure

```
forecasting/
├── data_preparation/
│   ├── feature_engineering.py
│   ├── lag_features.py
│   └── external_data.py
├── models/
│   ├── prophet_model.py
│   ├── lstm_model.py
│   ├── arima_model.py
│   └── ensemble.py
├── evaluation/
│   ├── backtesting.py
│   ├── metrics.py
│   └── visualization.py
└── serving/
    ├── batch_predictions.py
    └── api_server.py
```

## A/B Testing Framework for ML

### Scenario
Build a comprehensive A/B testing framework for ML model deployment with statistical significance testing.

### Task Submission

```bash
# Submit specific A/B testing task
./orchestrate submit "Create A/B testing framework with traffic splitting, metrics collection, and statistical analysis" \
  --agent ml-systems-architect
```

### Implementation Components

1. **Traffic Splitter**
   - User assignment logic
   - Consistent hashing
   - Gradual rollout support

2. **Metrics Collection**
   - Real-time metrics aggregation
   - Custom metric definitions
   - Event streaming

3. **Statistical Analysis**
   - Significance testing
   - Power analysis
   - Bayesian inference

4. **Dashboard**
   - Real-time experiment monitoring
   - Decision support tools
   - Automated reports

## MLOps Pipeline

### Scenario
Establish complete MLOps pipeline with CI/CD for model deployment.

### Comprehensive Setup

```bash
# Plan MLOps implementation
./orchestrate plan "Setup MLOps pipeline with model versioning, CI/CD, monitoring, and automated retraining"
```

### Pipeline Components

```yaml
# mlops/pipeline.yaml
stages:
  - name: data_validation
    steps:
      - check_data_quality
      - validate_schema
      - detect_drift

  - name: model_training
    steps:
      - feature_engineering
      - hyperparameter_tuning
      - model_validation

  - name: model_evaluation
    steps:
      - performance_metrics
      - bias_detection
      - explainability_analysis

  - name: deployment
    steps:
      - canary_deployment
      - smoke_tests
      - gradual_rollout

  - name: monitoring
    steps:
      - performance_tracking
      - drift_detection
      - alert_configuration
```

## Best Practices for ML Projects

### 1. Start with Baseline
```bash
# Always implement simple baseline first
./orchestrate submit "Implement logistic regression baseline for comparison" --priority high
```

### 2. Experiment Tracking
```bash
# Set up experiment tracking early
./orchestrate submit "Configure MLflow for experiment tracking and model registry"
```

### 3. Data Versioning
```bash
# Version your datasets
./orchestrate submit "Implement DVC for data versioning and reproducibility"
```

### 4. Model Monitoring
```bash
# Don't forget production monitoring
./orchestrate submit "Set up model performance monitoring and drift detection"
```

### 5. Documentation
```bash
# Document model decisions
./orchestrate submit "Create model cards documenting assumptions, limitations, and biases"
```

### 6. Testing Strategy
```bash
# Comprehensive testing
./orchestrate submit "Write unit tests for feature engineering pipeline"
./orchestrate submit "Create integration tests for inference pipeline"
./orchestrate submit "Implement model validation tests"
```