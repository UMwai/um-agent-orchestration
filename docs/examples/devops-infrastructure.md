# DevOps and Infrastructure Examples

## Kubernetes Migration

### Scenario
Migrate monolithic application running on EC2 instances to Kubernetes with zero downtime.

### Interactive Planning

```bash
./orchestrate plan "Migrate production app from EC2 to EKS with zero downtime"
```

#### Planning Session
```
Claude: Let's plan your Kubernetes migration. I need to understand:
1. Current architecture (how many EC2 instances)?
2. Database setup (RDS, self-managed)?
3. Traffic volume and patterns?
4. Acceptable maintenance window?

User: 5 EC2 instances, RDS PostgreSQL, 10K req/min peak, no downtime allowed

Claude: Perfect. Here's my zero-downtime migration strategy:

Phase 1: Preparation (Week 1)
- Containerize application with Docker
- Create Kubernetes manifests (deployments, services, ingress)
- Set up EKS cluster with proper networking
- Implement health checks and readiness probes

Phase 2: Parallel Deployment (Week 2)
- Deploy to Kubernetes alongside EC2
- Set up shared RDS access
- Configure service mesh for traffic management
- Implement distributed tracing

Phase 3: Traffic Migration (Week 3)
- Set up weighted routing in ALB
- Gradually shift traffic (10% → 25% → 50% → 100%)
- Monitor performance metrics
- Implement instant rollback capability

Phase 4: Cleanup (Week 4)
- Decommission EC2 instances
- Optimize Kubernetes resources
- Set up auto-scaling policies
- Document runbooks

[p] Proceed with this plan?
```

### Execution

```bash
# Execute migration plan
./orchestrate execute-plan k8s-migration

# Run with infrastructure specialists
./orchestrate run --max-agents 3
```

### Expected Deliverables

```
kubernetes-migration/
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── .dockerignore
├── k8s/
│   ├── base/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   └── secrets.yaml
│   ├── overlays/
│   │   ├── staging/
│   │   └── production/
│   └── ingress/
│       └── alb-ingress.yaml
├── terraform/
│   ├── eks-cluster.tf
│   ├── vpc.tf
│   ├── iam.tf
│   └── monitoring.tf
├── helm/
│   └── app-chart/
└── scripts/
    ├── deploy.sh
    ├── rollback.sh
    └── health-check.sh
```

## CI/CD Pipeline Implementation

### Scenario
Build a complete CI/CD pipeline with GitOps practices for multiple environments.

### Task Submission

```bash
# Submit comprehensive CI/CD task
./orchestrate submit "Implement CI/CD pipeline with GitHub Actions, ArgoCD, and multi-environment deployment" --decompose
```

### Generated Tasks
1. **GitHub Actions Workflows** (aws-cloud-architect)
   - Build and test automation
   - Docker image creation
   - Security scanning

2. **ArgoCD Setup** (aws-cloud-architect)
   - GitOps configuration
   - Application definitions
   - Sync policies

3. **Environment Management** (backend-systems-engineer)
   - Dev/staging/prod configurations
   - Secret management
   - Environment promotion

4. **Monitoring Integration** (aws-cloud-architect)
   - Pipeline metrics
   - Deployment tracking
   - Alerting setup

### Real-Time Progress

```bash
# Monitor pipeline development
./orchestrate status

# Example output:
# 🚀 CI/CD Pipeline Progress:
# ✅ GitHub Actions workflow created
# ✅ Docker build optimized with layer caching
# 🔄 Setting up ArgoCD application sets
# ⏳ Configuring Prometheus monitoring
# ⏳ Creating deployment dashboards
```

## Infrastructure as Code (IaC)

### Scenario
Convert manually configured AWS infrastructure to Terraform with proper state management.

### Structured Approach

```bash
# Plan IaC conversion
./orchestrate plan "Convert existing AWS infrastructure to Terraform with remote state"
```

### Implementation Strategy

```bash
# Phase 1: Discovery and Import
./orchestrate submit "Audit existing AWS resources and create import scripts" \
  --agent aws-cloud-architect

# Phase 2: Terraform Modules
./orchestrate submit "Create reusable Terraform modules for common patterns" \
  --agent aws-cloud-architect

# Phase 3: State Management
./orchestrate submit "Set up Terraform Cloud with workspaces for each environment" \
  --agent aws-cloud-architect

# Phase 4: Validation
./orchestrate submit "Implement terraform plan validation in CI pipeline" \
  --agent aws-cloud-architect
```

### Module Structure

```
terraform/
├── modules/
│   ├── networking/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── compute/
│   │   ├── ec2/
│   │   ├── ecs/
│   │   └── lambda/
│   ├── data/
│   │   ├── rds/
│   │   ├── elasticache/
│   │   └── s3/
│   └── monitoring/
├── environments/
│   ├── dev/
│   ├── staging/
│   └── production/
└── global/
    ├── iam/
    └── route53/
```

## Disaster Recovery Setup

### Scenario
Implement comprehensive disaster recovery with automated failover and backup strategies.

### Planning Session

```bash
./orchestrate plan "Design and implement disaster recovery with RTO <1 hour, RPO <15 minutes"
```

### Key Components

1. **Multi-Region Setup**
   - Active-passive configuration
   - Database replication
   - S3 cross-region replication

2. **Backup Strategy**
   - Automated EBS snapshots
   - RDS automated backups
   - Application state backup

3. **Failover Automation**
   - Route53 health checks
   - Automated DNS failover
   - Lambda-based orchestration

4. **Testing Framework**
   - Chaos engineering tests
   - Regular DR drills
   - Recovery validation

### Execution

```bash
# Run DR implementation
./orchestrate run --max-agents 2

# Agents collaborate:
# [aws-cloud-architect]: Setting up multi-region infrastructure
# [backend-systems-engineer]: Implementing failover logic
```

## Monitoring and Observability

### Scenario
Implement comprehensive observability with metrics, logs, and distributed tracing.

### Quick Implementation

```bash
# Submit observability task
./orchestrate submit "Set up observability stack: Prometheus, Grafana, Loki, Jaeger" \
  --agent aws-cloud-architect \
  --priority high
```

### Stack Components

```yaml
# monitoring/docker-compose.yml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    ports:
      - "3000:3000"

  loki:
    image: grafana/loki
    ports:
      - "3100:3100"

  jaeger:
    image: jaegertracing/all-in-one
    ports:
      - "16686:16686"
      - "14268:14268"
```

## Security Hardening

### Scenario
Implement security best practices and compliance requirements (SOC2, HIPAA).

### Comprehensive Security Plan

```bash
# Plan security implementation
./orchestrate plan "Implement SOC2 compliance with security scanning, SIEM, and audit logging"
```

### Security Tasks

```bash
# Multiple security implementations
./orchestrate submit "Set up AWS GuardDuty and Security Hub" --agent aws-cloud-architect
./orchestrate submit "Implement WAF rules and DDoS protection" --agent aws-cloud-architect
./orchestrate submit "Configure SIEM with CloudTrail and VPC Flow Logs" --agent backend-systems-engineer
./orchestrate submit "Set up Vault for secrets management" --agent backend-systems-engineer

# Run all security tasks
./orchestrate run --max-agents 4
```

## Service Mesh Implementation

### Scenario
Implement Istio service mesh for microservices communication, security, and observability.

### Task Breakdown

```bash
# Submit service mesh task
./orchestrate submit "Implement Istio service mesh with mTLS, traffic management, and observability" --decompose
```

### Implementation Phases

1. **Istio Installation**
   - Control plane setup
   - Sidecar injection
   - Gateway configuration

2. **Security Policies**
   - mTLS enforcement
   - Authorization policies
   - JWT validation

3. **Traffic Management**
   - Virtual services
   - Destination rules
   - Circuit breakers

4. **Observability**
   - Kiali dashboard
   - Distributed tracing
   - Metrics collection

## Cost Optimization

### Scenario
Reduce AWS costs by 40% through resource optimization and automation.

### Optimization Strategy

```bash
# Plan cost optimization
./orchestrate plan "Reduce AWS costs through rightsizing, spot instances, and resource scheduling"
```

### Implementation

```bash
# Cost optimization tasks
./orchestrate submit "Analyze and rightsize EC2 instances" --agent aws-cloud-architect
./orchestrate submit "Implement spot instance strategy for non-critical workloads" --agent aws-cloud-architect
./orchestrate submit "Set up automated resource scheduling for dev/test environments" --agent aws-cloud-architect
./orchestrate submit "Optimize S3 storage with lifecycle policies" --agent aws-cloud-architect

# Execute optimization
./orchestrate run --max-agents 2
```

## Best Practices for DevOps/Infrastructure

### 1. Infrastructure Testing
```bash
# Always test infrastructure changes
./orchestrate submit "Create Terraform testing with Terratest"
./orchestrate submit "Implement InSpec for compliance testing"
```

### 2. Documentation
```bash
# Document everything
./orchestrate submit "Create runbooks for common operations"
./orchestrate submit "Document disaster recovery procedures"
./orchestrate submit "Create architecture diagrams with draw.io"
```

### 3. Security First
```bash
# Security should be built-in
./orchestrate submit "Implement security scanning in CI pipeline"
./orchestrate submit "Set up automated compliance checks"
```

### 4. Monitoring Coverage
```bash
# Comprehensive monitoring
./orchestrate submit "Ensure 100% coverage of critical services with monitoring"
./orchestrate submit "Set up SLO/SLI tracking with error budgets"
```

### 5. Automation
```bash
# Automate everything possible
./orchestrate submit "Automate certificate renewal with cert-manager"
./orchestrate submit "Create self-healing systems with auto-remediation"
```