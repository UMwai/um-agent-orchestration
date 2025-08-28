# Task Queue Issue Resolution Specifications

## Document Metadata
- **Version**: 1.0.0
- **Created**: 2025-08-28
- **Author**: Specifications Engineer AI Agent
- **Status**: DRAFT
- **Priority**: HIGH
- **Impact**: CRITICAL - System core functionality affected

## Executive Summary

The task orchestration system has three critical issues preventing proper task execution:
1. Tasks remain stuck in "enqueued" state indefinitely
2. Task history is not being displayed/preserved correctly
3. Recovery system fails on startup with TaskState attribute error

## Problem Statements

### ISSUE-001: Tasks Stuck in Enqueued State

**Problem Description:**
Tasks submitted to the system remain in "enqueued" state and never progress to "running" or "passed" states.

**Root Cause Analysis:**
- RQ workers are not running to process the Redis queue
- No automatic worker startup mechanism exists
- The system enqueues tasks to Redis queue `autodev` but without workers, tasks remain unprocessed

**Business Impact:**
- Complete system failure - no tasks can be executed
- User experience severely degraded
- System appears non-functional

### ISSUE-002: Task History Not Preserved/Displayed

**Problem Description:**
Task history is being written to the database but may not be properly queried or displayed in the UI.

**Root Cause Analysis:**
- The `/api/tasks/history/{task_id}` endpoint exists and appears functional
- The persistence layer properly writes history records
- Issue likely in frontend not calling the history endpoint or displaying results
- The `/tasks` endpoint only returns current Redis state, not historical data from SQLite

**Business Impact:**
- Loss of audit trail capability
- Cannot track task progression over time
- Debugging and troubleshooting severely hampered

### ISSUE-003: Recovery System TaskState Attribute Error

**Problem Description:**
System startup fails with error: "type object 'TaskState' has no attribute 'COMPLETED'"

**Root Cause Analysis:**
- File `orchestrator/recovery.py` line 63 incorrectly references `TaskState.COMPLETED`
- The `TaskState` enum uses `PASSED` for successful completion, not `COMPLETED`
- `COMPLETED` exists in `CLISessionState` enum, causing confusion
- Code attempts to check for both `TaskState.PASSED` and `TaskState.COMPLETED` when only `PASSED` exists

**Business Impact:**
- System cannot start properly
- Previously running tasks cannot be recovered
- Data consistency checks fail

## Technical Requirements

### REQ-001: Fix TaskState.COMPLETED Reference

**Requirement ID:** REQ-001
**Type:** Bug Fix
**Component:** orchestrator/recovery.py

**Specification:**
- Remove reference to `TaskState.COMPLETED` from line 63 of `orchestrator/recovery.py`
- Only check for `TaskState.PASSED` as the terminal success state
- Update any other files that incorrectly reference `TaskState.COMPLETED`

**Implementation Details:**
```python
# Current (incorrect):
elif task_record.state in [TaskState.PASSED, TaskState.COMPLETED]:

# Corrected:
elif task_record.state == TaskState.PASSED:
```

**Acceptance Criteria:**
- [ ] System starts without TaskState attribute errors
- [ ] Recovery process correctly identifies completed tasks
- [ ] No references to TaskState.COMPLETED remain in the codebase

### REQ-002: Implement RQ Worker Management

**Requirement ID:** REQ-002
**Type:** Feature Enhancement
**Component:** Worker Management System

**Specification:**
- Create automatic RQ worker startup mechanism
- Implement worker health monitoring
- Add worker status to system metrics
- Provide manual worker control endpoints

**Implementation Options:**

**Option A: Subprocess Management (Recommended)**
```python
class WorkerManager:
    def __init__(self):
        self.worker_processes = []
        
    def start_worker(self, queue_name="autodev"):
        """Start an RQ worker subprocess"""
        process = subprocess.Popen(
            ["rq", "worker", queue_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self.worker_processes.append(process)
        
    def ensure_workers_running(self, min_workers=1):
        """Ensure minimum number of workers are running"""
        active_workers = [p for p in self.worker_processes if p.poll() is None]
        
        while len(active_workers) < min_workers:
            self.start_worker()
            active_workers = [p for p in self.worker_processes if p.poll() is None]
```

**Option B: Thread-based Worker**
```python
import threading
from rq import Worker, Queue, Connection

def run_worker_thread():
    """Run RQ worker in a thread"""
    with Connection(_redis):
        worker = Worker([jobs_q])
        worker.work()

# Start worker thread on app startup
worker_thread = threading.Thread(target=run_worker_thread, daemon=True)
worker_thread.start()
```

**Acceptance Criteria:**
- [ ] At least one RQ worker starts automatically with the application
- [ ] Tasks progress from "enqueued" to "running" to terminal states
- [ ] Worker status is visible via API endpoint
- [ ] System recovers workers if they crash

### REQ-003: Enhanced Task Status API

**Requirement ID:** REQ-003
**Type:** Feature Enhancement
**Component:** Task Status API

**Specification:**
- Create unified task status endpoint combining Redis (current) and SQLite (historical) data
- Add task history to main task listing endpoint
- Implement proper task state aggregation

**Implementation Details:**

```python
@app.get("/api/tasks/full")
async def get_all_tasks_with_history():
    """Get all tasks with current status and history"""
    persistence_manager = get_persistence_manager()
    
    # Get all tasks from persistence
    all_tasks = persistence_manager.get_all_tasks()
    
    # Enhance with current Redis status if available
    for task in all_tasks:
        redis_status = get_redis_task_status(task.id)
        if redis_status:
            task.current_state = redis_status.state
        
        # Add history summary
        task.history_count = len(persistence_manager.get_task_history(task.id))
    
    return all_tasks
```

**Acceptance Criteria:**
- [ ] Single endpoint returns both current and historical task data
- [ ] Task history is accessible for all tasks
- [ ] Performance remains acceptable with large task counts
- [ ] Frontend can display complete task lifecycle

### REQ-004: Worker Configuration and Monitoring

**Requirement ID:** REQ-004
**Type:** Feature Enhancement
**Component:** Configuration System

**Specification:**
- Add worker configuration to settings
- Implement worker health checks
- Add worker metrics to monitoring system

**Configuration Schema:**
```yaml
workers:
  enabled: true
  auto_start: true
  count: 2
  queues:
    - autodev
    - autodev-priority
  health_check_interval: 30
  restart_on_failure: true
  max_restarts: 3
```

**Monitoring Metrics:**
```python
class WorkerMetrics:
    workers_active = Gauge('workers_active', 'Number of active workers')
    workers_idle = Gauge('workers_idle', 'Number of idle workers')
    workers_busy = Gauge('workers_busy', 'Number of busy workers')
    worker_restarts = Counter('worker_restarts', 'Total worker restarts')
    tasks_in_queue = Gauge('tasks_in_queue', 'Number of tasks waiting in queue')
```

**Acceptance Criteria:**
- [ ] Worker configuration is loaded from settings
- [ ] Worker health metrics are exposed via /metrics endpoint
- [ ] Unhealthy workers are automatically restarted
- [ ] Queue depth is monitored and alerted

## Implementation Guidelines

### Phase 1: Critical Bug Fixes (Immediate)
1. Fix TaskState.COMPLETED reference in recovery.py
2. Verify system can start without errors
3. Test task recovery functionality

### Phase 2: Worker Management (Priority)
1. Implement basic worker subprocess management
2. Add automatic worker startup to app lifespan
3. Test task processing end-to-end

### Phase 3: API Enhancements (Enhancement)
1. Create unified task status endpoints
2. Enhance task listing with history data
3. Update frontend to use new endpoints

### Phase 4: Monitoring and Configuration (Optimization)
1. Add worker configuration system
2. Implement health checks and metrics
3. Add alerting for queue depth and worker health

## Testing Requirements

### Unit Tests

```python
def test_task_state_enum_has_no_completed():
    """Verify TaskState enum doesn't have COMPLETED"""
    from orchestrator.persistence_models import TaskState
    assert not hasattr(TaskState, 'COMPLETED')
    assert hasattr(TaskState, 'PASSED')

def test_recovery_handles_passed_state():
    """Test recovery correctly handles PASSED state"""
    recovery_manager = TaskRecoveryManager()
    task = create_test_task(state=TaskState.PASSED)
    result = recovery_manager._recover_single_task(task)
    assert result == True

def test_worker_auto_start():
    """Test worker starts automatically"""
    worker_manager = WorkerManager()
    worker_manager.ensure_workers_running(min_workers=1)
    assert len(worker_manager.get_active_workers()) >= 1

def test_task_progresses_through_states():
    """Test task moves from enqueued to completed"""
    task_id = submit_test_task()
    wait_for_state(task_id, "running", timeout=10)
    wait_for_state(task_id, "passed", timeout=30)
    assert get_task_state(task_id) == "passed"
```

### Integration Tests

```python
def test_full_task_lifecycle():
    """Test complete task lifecycle with history"""
    # Submit task
    task = submit_task(TaskSpec(
        id="test-001",
        title="Test Task",
        description="Integration test",
        role="backend"
    ))
    
    # Verify enqueued
    assert get_task_status(task.id).state == "queued"
    
    # Wait for processing
    time.sleep(5)
    
    # Verify running or completed
    status = get_task_status(task.id)
    assert status.state in ["running", "passed", "failed"]
    
    # Verify history exists
    history = get_task_history(task.id)
    assert len(history) > 0
    assert history[0].state_to == TaskState.QUEUED
```

### Acceptance Tests

```gherkin
Feature: Task Queue Processing
  
  Scenario: Task is processed by worker
    Given the system is running with workers
    When I submit a new task
    Then the task should transition from "queued" to "running"
    And the task should eventually reach a terminal state
    And the task history should be preserved

  Scenario: System recovers from restart
    Given there are tasks in various states
    When the system is restarted
    Then running tasks should be marked as failed
    And queued tasks should remain queued
    And completed tasks should retain their state
    And no TaskState attribute errors should occur

  Scenario: Worker failure recovery
    Given a task is being processed
    When the worker crashes
    Then a new worker should be started automatically
    And the task should be retried or marked as failed
    And the failure should be logged in task history
```

## Risk Analysis

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Worker subprocess management complexity | Medium | High | Use battle-tested subprocess patterns, implement comprehensive error handling |
| Redis/SQLite synchronization issues | Low | Medium | Implement dual-write pattern with eventual consistency checks |
| Memory leaks in long-running workers | Medium | Medium | Implement worker recycling after N tasks |
| Queue backlog during high load | Medium | Low | Implement queue depth monitoring and auto-scaling |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Workers consuming excessive resources | Low | High | Implement resource limits and monitoring |
| Database growth from history records | Medium | Low | Implement history archival/cleanup policies |
| Network issues affecting Redis | Low | High | Implement connection pooling and retry logic |

## Validation Criteria

### System Level
- [ ] System starts without errors
- [ ] Tasks progress through complete lifecycle
- [ ] History is preserved and queryable
- [ ] Workers auto-recover from failures
- [ ] Monitoring shows accurate metrics

### Performance Level
- [ ] Task submission < 100ms
- [ ] Task state transitions < 1s
- [ ] History queries < 500ms for 1000 records
- [ ] Worker startup < 5s
- [ ] System handles 100 concurrent tasks

### User Experience Level
- [ ] Dashboard shows real-time task updates
- [ ] Task history is visible and complete
- [ ] System status indicators are accurate
- [ ] Error messages are clear and actionable

## Dependencies

### Internal Dependencies
- Redis server must be running
- SQLite database must be accessible
- Python RQ library properly installed
- FastAPI application server running

### External Dependencies
- None identified

## Migration Strategy

### Database Migration
No database schema changes required.

### Code Migration
1. Deploy fix for TaskState.COMPLETED first (backwards compatible)
2. Deploy worker management system
3. Deploy API enhancements
4. Update frontend to use new endpoints

### Rollback Plan
1. Keep previous deployment artifacts
2. Monitor error rates post-deployment
3. Rollback if error rate exceeds threshold
4. Worker management can be disabled via configuration

## Success Metrics

### Immediate (Post-deployment)
- Zero TaskState attribute errors
- >95% of tasks progress beyond "enqueued" state
- Task history endpoint returns data for all tasks

### Short-term (1 week)
- Worker uptime >99%
- Average task processing time <30s
- Zero data loss incidents

### Long-term (1 month)
- System processes >10,000 tasks successfully
- Worker auto-recovery triggered <10 times
- User satisfaction score >4/5

## Appendix

### A. Current File Locations
- `orchestrator/recovery.py` - Contains TaskState.COMPLETED bug
- `orchestrator/dispatcher.py` - Task state management
- `orchestrator/app.py` - API endpoints and worker initialization
- `orchestrator/queue.py` - Redis queue configuration
- `orchestrator/persistence.py` - Database operations
- `orchestrator/persistence_models.py` - Data model definitions

### B. Related Documentation
- CLAUDE.md - Development commands and setup
- AGENTS.md - Multi-agent coordination patterns
- database/schema.sql - Database schema definition

### C. Command Reference
```bash
# Start RQ worker manually
rq worker autodev

# Check Redis queue status
rq info

# Monitor task processing
watch -n 1 'rq info --interval 1'

# Clear stuck tasks
rq empty autodev

# View task details in Redis
redis-cli GET "task_status:TASK_ID"
```

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-08-28 | Specifications Engineer AI | Initial specification document |

---
End of Specification Document