# Web Application Development Examples

## Full-Stack E-Commerce Platform

### Scenario
You need to build a complete e-commerce platform with product catalog, shopping cart, payment processing, and admin dashboard.

### Approach

```bash
# Start with interactive planning
./orchestrate plan "Build e-commerce platform with Stripe payments and admin dashboard"
```

#### Planning Session Example
```
Claude: I'll help you build an e-commerce platform. Let me understand your requirements:
- Payment provider: Stripe
- Frontend framework preference?
- Database: PostgreSQL recommended for transactional data
- Need inventory management?

User: Yes, use React for frontend, PostgreSQL, and include inventory tracking

Claude: Great! Here's my proposed task breakdown:

Phase 1: Foundation (Day 1)
- Set up PostgreSQL schema for products, users, orders
- Create authentication system with JWT
- Initialize React app with routing

Phase 2: Core Features (Day 2-3)
- Product catalog API endpoints
- Shopping cart functionality
- React components for product listing and details

Phase 3: Payment & Checkout (Day 4)
- Stripe integration for payments
- Order processing workflow
- Email notifications

Phase 4: Admin Dashboard (Day 5)
- Admin authentication and authorization
- Product management interface
- Order management and reporting

[a] to add tasks, [m] to modify, [p] to proceed
```

### Execution

```bash
# After planning approval, execute with multiple agents
./orchestrate execute-plan ecommerce-project

# Run with 5 parallel agents for faster development
./orchestrate run --max-agents 5
```

### Expected Output Structure
```
project/
├── backend/
│   ├── app.py                 # FastAPI application
│   ├── models/
│   │   ├── product.py
│   │   ├── user.py
│   │   └── order.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── products.py
│   │   ├── cart.py
│   │   └── payments.py
│   └── services/
│       ├── stripe_service.py
│       └── email_service.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ProductList.jsx
│   │   │   ├── Cart.jsx
│   │   │   └── Checkout.jsx
│   │   ├── pages/
│   │   └── services/
│   └── package.json
└── database/
    └── migrations/
```

## SaaS Application with Multi-Tenancy

### Scenario
Building a project management SaaS with team collaboration, real-time updates, and subscription billing.

### Task Submission

```bash
# Submit with automatic decomposition
./orchestrate submit "Create multi-tenant SaaS project management tool with real-time collaboration" --decompose
```

### Automated Task Breakdown
The system will create tasks like:
1. **Database Architecture** (data-architect-governance)
   - Design multi-tenant schema
   - Plan data isolation strategy
   - Create tenant provisioning system

2. **Backend Development** (backend-systems-engineer)
   - Build tenant-aware API middleware
   - Implement WebSocket for real-time updates
   - Create subscription management

3. **Frontend Development** (frontend-ui-engineer)
   - Build responsive dashboard
   - Implement real-time collaboration UI
   - Create onboarding flow

4. **Infrastructure** (aws-cloud-architect)
   - Set up auto-scaling groups
   - Configure CloudFront CDN
   - Implement backup strategies

### Monitoring Progress

```bash
# Check which agents are working on what
./orchestrate agents

# Output:
# 🤖 Active Agents:
# [backend-systems-engineer] Working on: Implement WebSocket server for real-time updates
# [frontend-ui-engineer] Working on: Create Kanban board component with drag-and-drop
# [data-architect-governance] Working on: Design row-level security for multi-tenancy

# View specific task details
./orchestrate task websocket-implementation
```

## Progressive Web App (PWA)

### Scenario
Convert existing web app to PWA with offline support, push notifications, and app-like experience.

### Quick Implementation

```bash
# For focused enhancement, specify the agent
./orchestrate submit "Convert React app to PWA with offline support and push notifications" \
  --agent frontend-ui-engineer \
  --priority high

# Run single agent for this specialized task
./orchestrate run --max-agents 1
```

### Expected Deliverables
- Service worker implementation
- Manifest.json configuration
- Offline caching strategy
- Push notification setup
- Installation prompt handling
- App shell architecture

## API Gateway and Microservices

### Scenario
Decompose monolithic application into microservices with API gateway.

### Phased Approach

```bash
# Plan the decomposition strategy
./orchestrate plan "Decompose monolithic Django app into microservices: auth, products, orders, notifications"
```

### Execution Phases
```bash
# Phase 1: Architecture and Planning
# All architecture tasks run in parallel
# Agents: specifications-engineer, data-architect-governance

# Phase 2: Service Implementation
# Each microservice developed in parallel
# Agents: 3x backend-systems-engineer

# Phase 3: API Gateway
# Sequential implementation after services
# Agent: backend-systems-engineer

# Phase 4: Integration Testing
# Parallel testing of all services
# Agents: backend-systems-engineer + frontend-ui-engineer
```

### Real-Time Monitoring
```bash
# Watch progress in real-time
watch -n 5 './orchestrate status'

# Get detailed logs from specific agent
./orchestrate task auth-service-impl --verbose
```

## Best Practices

### 1. Start with Planning
Always begin with interactive planning for complex projects:
```bash
./orchestrate plan "Your project description"
```

### 2. Use Appropriate Parallelism
- **2-3 agents**: For small to medium projects
- **4-5 agents**: For large projects with independent components
- **6-8 agents**: For massive projects over weekends

### 3. Priority Management
```bash
# High priority for critical path items
./orchestrate submit "Fix authentication bug" --priority high

# Normal priority for features
./orchestrate submit "Add user profile page" --priority normal

# Low priority for nice-to-haves
./orchestrate submit "Add animated transitions" --priority low
```

### 4. Context Sharing
Agents automatically share context through `/tmp/agent_orchestrator/`. Ensure tasks that depend on each other are properly phased.

### 5. Regular Checkpoints
```bash
# Morning routine
./orchestrate status
git diff HEAD~1
./orchestrate agents

# Before leaving
./orchestrate submit "Continue tomorrow" --decompose
./orchestrate run --max-agents 3
```