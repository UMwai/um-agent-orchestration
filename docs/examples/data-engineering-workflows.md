# Data Engineering Workflow Examples

## Real-Time Data Pipeline

### Scenario
Build a real-time data pipeline that ingests streaming data from Kafka, processes it with Spark Streaming, and stores results in both a data lake (S3) and data warehouse (Snowflake).

### Interactive Planning Session

```bash
./orchestrate plan "Build real-time pipeline: Kafka → Spark Streaming → S3/Snowflake"
```

#### Planning Dialogue
```
Claude: Let's design your real-time data pipeline. I need to understand:
1. What's your data volume (events/second)?
2. What transformations are needed?
3. Any data quality requirements?
4. Latency requirements?

User: 10K events/sec, need deduplication and enrichment, <5 min latency

Claude: Perfect. Here's my approach:

Phase 1: Infrastructure Setup
- Set up Kafka cluster with proper partitioning
- Configure S3 buckets with lifecycle policies
- Set up Snowflake warehouse and staging areas

Phase 2: Spark Streaming Application
- Implement Kafka consumer with checkpointing
- Build deduplication using watermarking
- Create enrichment logic with reference data

Phase 3: Data Quality & Monitoring
- Implement data quality checks
- Set up CloudWatch metrics
- Create data lineage tracking

Phase 4: Optimization & Testing
- Performance tuning for 10K events/sec
- Implement exactly-once semantics
- Load testing and failover scenarios
```

### Task Execution

```bash
# Execute the plan with specialized agents
./orchestrate execute-plan realtime-pipeline

# Use more agents for parallel development
./orchestrate run --max-agents 4
```

### Expected Deliverables

```
data-pipeline/
├── infrastructure/
│   ├── terraform/
│   │   ├── kafka.tf
│   │   ├── s3.tf
│   │   └── emr.tf
│   └── docker/
│       └── spark-streaming/
├── spark-jobs/
│   ├── src/main/scala/
│   │   ├── StreamProcessor.scala
│   │   ├── Deduplicator.scala
│   │   └── Enricher.scala
│   └── build.sbt
├── monitoring/
│   ├── cloudwatch-dashboards.json
│   └── alerts.yaml
└── tests/
    ├── integration/
    └── load-tests/
```

## ETL Pipeline with dbt

### Scenario
Modernize legacy ETL processes using dbt for transformation, Airflow for orchestration, and implement comprehensive data quality checks.

### Quick Start

```bash
# Submit with automatic task decomposition
./orchestrate submit "Modernize ETL: migrate stored procedures to dbt, add Airflow orchestration, implement Great Expectations" --decompose
```

### Generated Task List
1. **Analyze existing stored procedures** (data-architect-governance)
2. **Design dbt project structure** (data-pipeline-engineer)
3. **Convert SQL procedures to dbt models** (data-pipeline-engineer)
4. **Create Airflow DAGs** (data-pipeline-engineer)
5. **Implement data quality with Great Expectations** (data-science-analyst)
6. **Set up CI/CD for dbt** (aws-cloud-architect)

### Progress Monitoring

```bash
# Watch the transformation progress
./orchestrate status

# Example output:
# 📊 Task Queue Status:
# Completed (3):
#   ✅ Analyze existing stored procedures
#   ✅ Design dbt project structure
#   ✅ Convert customer dimension to dbt
# In Progress (2):
#   🔄 Convert sales facts to dbt (75% complete)
#   🔄 Create main Airflow DAG
# Pending (4):
#   ⏳ Implement Great Expectations suite
#   ⏳ Set up dbt documentation
#   ⏳ Create CI/CD pipeline
#   ⏳ Performance testing
```

## Data Lake Implementation

### Scenario
Build a modern data lake with bronze/silver/gold architecture using Delta Lake format.

### Structured Approach

```bash
# Start planning session
./orchestrate plan "Implement medallion architecture data lake with Delta Lake on S3"
```

### Implementation Phases

```bash
# Phase 1: Foundation (2 agents in parallel)
# - Set up S3 bucket structure
# - Configure Delta Lake tables
# - Implement data ingestion framework

# Phase 2: Bronze Layer (3 agents in parallel)
# - Raw data ingestion from multiple sources
# - Schema inference and evolution
# - Partition strategy implementation

# Phase 3: Silver Layer (2 agents in parallel)
# - Data cleansing and validation
# - Standardization and deduplication
# - Slowly changing dimensions (SCD Type 2)

# Phase 4: Gold Layer (2 agents working together)
# - Business-level aggregations
# - Pre-computed metrics
# - Serving layer optimization
```

### Execution

```bash
# Run with higher parallelism for faster delivery
./orchestrate run --max-agents 5

# Monitor specific layer development
./orchestrate task silver-layer-implementation
```

## CDC Pipeline with Debezium

### Scenario
Implement Change Data Capture from PostgreSQL to create real-time data warehouse synchronization.

### Direct Submission

```bash
# Submit specialized task to data pipeline engineer
./orchestrate submit "Set up CDC pipeline: PostgreSQL → Debezium → Kafka → Snowflake" \
  --agent data-pipeline-engineer \
  --priority high
```

### Expected Implementation
- Debezium connector configuration
- Kafka topic management
- Schema registry setup
- Snowflake Kafka connector
- Monitoring and alerting
- Failure recovery procedures

## Machine Learning Feature Store

### Scenario
Build a feature store for ML models with both batch and real-time features.

### Collaborative Development

```bash
# Plan with both data and ML perspectives
./orchestrate plan "Build feature store with Feast for batch and streaming features"

# Multiple specialists work together:
# - data-pipeline-engineer: Pipeline infrastructure
# - ml-systems-architect: Feature engineering design
# - data-science-analyst: Feature validation and monitoring
```

### Parallel Execution Example

```bash
# Agents work on different aspects simultaneously
./orchestrate run --max-agents 3

# Real-time status shows coordination:
# 🤖 [data-pipeline-engineer]: Building Spark jobs for batch features
# 🤖 [ml-systems-architect]: Implementing feature versioning system
# 🤖 [data-science-analyst]: Creating feature importance analysis
```

## Data Quality Framework

### Scenario
Implement comprehensive data quality monitoring across all pipelines.

### Quick Implementation

```bash
# Submit focused task
./orchestrate submit "Implement data quality checks: completeness, uniqueness, timeliness, validity, consistency" \
  --agent data-science-analyst

# Run and monitor
./orchestrate run --max-agents 1
```

### Deliverables
```python
# data_quality/checks.py
class DataQualityFramework:
    def check_completeness(self, df, required_columns):
        """Check for null values in required columns"""

    def check_uniqueness(self, df, unique_columns):
        """Verify unique constraints"""

    def check_timeliness(self, df, date_column, max_delay):
        """Ensure data freshness"""

    def check_validity(self, df, validation_rules):
        """Apply business rule validation"""

    def check_consistency(self, df1, df2, join_keys):
        """Cross-dataset consistency checks"""
```

## Best Practices for Data Engineering

### 1. Phased Approach
Always design in phases - infrastructure first, then implementation, then optimization:
```bash
./orchestrate plan "Your data project"  # Use interactive planning
```

### 2. Appropriate Agent Selection
- **data-architect-governance**: Schema design, data models
- **data-pipeline-engineer**: ETL/ELT implementation
- **aws-cloud-architect**: Infrastructure and deployment
- **data-science-analyst**: Data quality and analysis

### 3. Testing Strategy
```bash
# Always include testing tasks
./orchestrate submit "Create unit tests for ETL pipeline" --priority high
./orchestrate submit "Implement integration tests" --priority high
./orchestrate submit "Load testing with production volume" --priority normal
```

### 4. Documentation
```bash
# Ensure documentation is created
./orchestrate submit "Document data lineage and dependencies"
./orchestrate submit "Create runbook for pipeline operations"
```

### 5. Monitoring Setup
```bash
# Don't forget observability
./orchestrate submit "Set up DataDog monitoring for all pipelines"
./orchestrate submit "Create PagerDuty alerts for critical failures"
```