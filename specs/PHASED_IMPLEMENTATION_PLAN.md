# Phased CLI Integration Implementation Plan

## Executive Overview

This document provides a detailed, phased implementation plan to resolve critical issues in the CLI integration system and establish a stable, well-specified foundation for future development.

## Phase 1: Critical Stabilization (Days 1-10)

### Objective
Resolve immediate blockers preventing system operation

### Day 1-2: TaskState Unification

#### Problem Statement
Multiple conflicting TaskState definitions causing import errors and runtime failures

#### Solution Specification
```python
# orchestrator/models/states.py - CANONICAL DEFINITION
from enum import Enum

class TaskState(str, Enum):
    """Canonical task state definition - single source of truth"""
    # Initial states
    PENDING = "pending"
    QUEUED = "queued"
    
    # Execution states  
    RUNNING = "running"
    PROCESSING = "processing"
    
    # Completion states
    COMPLETED = "completed"
    SUCCEEDED = "succeeded"
    
    # Error states
    FAILED = "failed"
    ERROR = "error"
    
    # Cancelled state
    CANCELLED = "cancelled"
    
    @classmethod
    def is_terminal(cls, state: 'TaskState') -> bool:
        """Check if state is terminal (no further transitions)"""
        return state in {cls.COMPLETED, cls.SUCCEEDED, cls.FAILED, cls.ERROR, cls.CANCELLED}
    
    @classmethod
    def is_active(cls, state: 'TaskState') -> bool:
        """Check if state represents active processing"""
        return state in {cls.RUNNING, cls.PROCESSING}
```

#### Implementation Tasks
- [ ] Create canonical states.py module
- [ ] Update all imports to use canonical definition
- [ ] Remove duplicate definitions
- [ ] Add migration for existing task data

#### Test Requirements
```python
def test_taskstate_canonical():
    from orchestrator.models.states import TaskState
    
    # Test all states accessible
    assert TaskState.PENDING
    assert TaskState.RUNNING
    assert TaskState.COMPLETED
    
    # Test helper methods
    assert TaskState.is_terminal(TaskState.COMPLETED)
    assert not TaskState.is_terminal(TaskState.RUNNING)
    assert TaskState.is_active(TaskState.RUNNING)
```

#### Acceptance Criteria
- No import errors for TaskState
- All existing code using canonical definition
- Tests passing for state transitions

### Day 3-4: Authentication Loop Resolution

#### Problem Statement
Authentication enters infinite retry loop without backoff, causing resource exhaustion

#### Solution Specification
```python
# orchestrator/auth/authenticator.py
class AuthenticationManager:
    """Manages CLI authentication with retry logic and backoff"""
    
    def __init__(self):
        self.max_attempts = 3
        self.base_backoff = 1.0  # seconds
        self.max_backoff = 30.0
        
    async def authenticate(
        self,
        session_id: str,
        provider: str,
        credentials: Optional[Dict] = None
    ) -> AuthResult:
        """
        Authenticate CLI session with exponential backoff
        
        Returns:
            AuthResult with success status and any error details
        """
        attempts = 0
        backoff = self.base_backoff
        
        while attempts < self.max_attempts:
            try:
                result = await self._attempt_auth(session_id, provider, credentials)
                if result.success:
                    return result
                    
                # Check if error is retryable
                if not result.retryable:
                    return result
                    
            except Exception as e:
                logger.error(f"Auth attempt {attempts + 1} failed: {e}")
                
            attempts += 1
            if attempts < self.max_attempts:
                logger.info(f"Retrying auth in {backoff}s (attempt {attempts}/{self.max_attempts})")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)
        
        return AuthResult(
            success=False,
            error="MAX_ATTEMPTS_EXCEEDED",
            message=f"Authentication failed after {self.max_attempts} attempts"
        )
```

#### Implementation Tasks
- [ ] Implement AuthenticationManager
- [ ] Add exponential backoff logic
- [ ] Define retryable vs non-retryable errors
- [ ] Add circuit breaker pattern

#### Test Requirements
```python
async def test_auth_retry_logic():
    manager = AuthenticationManager()
    
    # Mock failing auth
    with patch('_attempt_auth') as mock_auth:
        mock_auth.side_effect = [
            AuthResult(False, retryable=True),
            AuthResult(False, retryable=True),
            AuthResult(True)
        ]
        
        result = await manager.authenticate("session1", "claude")
        assert result.success
        assert mock_auth.call_count == 3
```

#### Acceptance Criteria
- No infinite authentication loops
- Proper backoff between retries
- Clear error messages after max attempts
- Circuit breaker prevents system overload

### Day 5-6: Session Timeout Standardization

#### Problem Statement
Inconsistent timeout values causing premature session termination and resource leaks

#### Solution Specification
```yaml
# orchestrator/config/timeouts.yaml
timeouts:
  session:
    idle_timeout: 300  # 5 minutes
    max_lifetime: 3600  # 1 hour
    warning_before_timeout: 30  # 30 seconds warning
    
  authentication:
    timeout: 30  # 30 seconds
    retry_delay: [1, 2, 4, 8, 16]  # Exponential backoff
    
  command:
    default_timeout: 300  # 5 minutes
    max_timeout: 1800  # 30 minutes
    
  websocket:
    ping_interval: 30  # 30 seconds
    pong_timeout: 10  # 10 seconds
    reconnect_delay: 5  # 5 seconds
```

```python
# orchestrator/session/timeout_manager.py
class TimeoutManager:
    """Centralized timeout management"""
    
    def __init__(self, config_path: str = "config/timeouts.yaml"):
        self.config = self._load_config(config_path)
        self._active_timers = {}
        
    async def start_idle_timer(self, session_id: str, callback: Callable):
        """Start idle timeout timer with warning"""
        timeout = self.config['session']['idle_timeout']
        warning_time = timeout - self.config['session']['warning_before_timeout']
        
        # Schedule warning
        asyncio.create_task(
            self._schedule_warning(session_id, warning_time)
        )
        
        # Schedule timeout
        timer = asyncio.create_task(
            self._schedule_timeout(session_id, timeout, callback)
        )
        self._active_timers[session_id] = timer
        
    def reset_timer(self, session_id: str):
        """Reset idle timer on activity"""
        if session_id in self._active_timers:
            self._active_timers[session_id].cancel()
            # Restart timer
            asyncio.create_task(
                self.start_idle_timer(session_id, self._timeout_callback)
            )
```

#### Implementation Tasks
- [ ] Create centralized timeout configuration
- [ ] Implement TimeoutManager
- [ ] Add warning notifications
- [ ] Update all timeout references

#### Test Requirements
```python
async def test_session_timeout():
    manager = TimeoutManager()
    timeout_called = False
    
    async def timeout_callback(session_id):
        nonlocal timeout_called
        timeout_called = True
    
    await manager.start_idle_timer("session1", timeout_callback)
    await asyncio.sleep(305)  # Just past timeout
    
    assert timeout_called
```

#### Acceptance Criteria
- Consistent timeout values across system
- Warning before timeout
- Proper cleanup on timeout
- Activity resets timeout

### Day 7-8: CLI Manager Consolidation

#### Problem Statement
Three conflicting CLI manager implementations causing confusion and bugs

#### Solution Specification
```python
# orchestrator/cli/unified_manager.py
class UnifiedCLIManager:
    """Single consolidated CLI manager - replaces all others"""
    
    def __init__(self):
        self.process_manager = ProcessManager()  # From cli_manager.py
        self.session_manager = SessionManager()  # From cli_session.py
        self.auth_manager = AuthenticationManager()  # New unified auth
        self.timeout_manager = TimeoutManager()  # New unified timeouts
        
    async def create_session(
        self,
        provider: str,
        mode: str = "cli",
        **options
    ) -> CLISession:
        """Create new CLI session with all managers coordinated"""
        
        # Create session
        session = await self.session_manager.create(provider, mode)
        
        # Start process
        process_id = await self.process_manager.spawn_process(
            provider,
            session_id=session.id
        )
        session.process_id = process_id
        
        # Setup authentication
        auth_result = await self.auth_manager.authenticate(
            session.id,
            provider,
            options.get('credentials')
        )
        
        if not auth_result.success:
            await self.terminate_session(session.id)
            raise AuthenticationError(auth_result.message)
        
        # Start timeout monitoring
        await self.timeout_manager.start_idle_timer(
            session.id,
            self._handle_timeout
        )
        
        return session
```

#### Migration Plan
```python
# orchestrator/cli/migration.py
def migrate_to_unified_manager():
    """Migration script to unified manager"""
    
    # Step 1: Stop new sessions on old managers
    deprecate_old_managers()
    
    # Step 2: Migrate active sessions
    old_sessions = get_active_sessions()
    for session in old_sessions:
        migrate_session_to_unified(session)
    
    # Step 3: Update all imports
    update_imports_to_unified()
    
    # Step 4: Remove old manager files (after validation)
    # archive_old_managers()
```

#### Implementation Tasks
- [ ] Create UnifiedCLIManager
- [ ] Integrate all manager functionality  
- [ ] Write migration script
- [ ] Update all references
- [ ] Archive old implementations

#### Test Requirements
```python
async def test_unified_manager():
    manager = UnifiedCLIManager()
    
    # Test session creation
    session = await manager.create_session("claude", "cli")
    assert session.id
    assert session.process_id
    assert session.state == SessionState.READY
    
    # Test command execution
    result = await manager.execute_command(session.id, "test")
    assert result.success
    
    # Test cleanup
    await manager.terminate_session(session.id)
    assert session.state == SessionState.TERMINATED
```

#### Acceptance Criteria
- Single manager handles all CLI operations
- No duplicate functionality
- Clean migration from old managers
- All tests passing

### Day 9-10: Integration Testing and Validation

#### Test Suite Specification
```python
# tests/integration/test_phase1_complete.py

class TestPhase1Integration:
    """Validate all Phase 1 objectives achieved"""
    
    async def test_no_import_errors(self):
        """Verify clean imports"""
        from orchestrator.models.states import TaskState
        from orchestrator.cli.unified_manager import UnifiedCLIManager
        from orchestrator.auth.authenticator import AuthenticationManager
        from orchestrator.session.timeout_manager import TimeoutManager
        
    async def test_full_session_lifecycle(self):
        """Test complete session flow"""
        manager = UnifiedCLIManager()
        
        # Create
        session = await manager.create_session("claude")
        assert session.state == SessionState.READY
        
        # Execute
        result = await manager.execute_command(session.id, "echo test")
        assert "test" in result.output
        
        # Timeout warning
        await asyncio.sleep(270)  # Close to timeout
        assert session.warning_sent
        
        # Activity resets
        await manager.execute_command(session.id, "echo alive")
        assert not session.warning_sent
        
        # Cleanup
        await manager.terminate_session(session.id)
        assert session.state == SessionState.TERMINATED
        
    async def test_auth_retry_behavior(self):
        """Verify auth retries properly"""
        manager = UnifiedCLIManager()
        
        with patch('authenticate') as mock_auth:
            # Fail twice, succeed third time
            mock_auth.side_effect = [
                AuthResult(False, retryable=True),
                AuthResult(False, retryable=True),
                AuthResult(True)
            ]
            
            session = await manager.create_session("claude")
            assert session.state == SessionState.READY
            assert mock_auth.call_count == 3
```

#### Validation Checklist
- [ ] All imports work without errors
- [ ] Authentication completes within 3 attempts
- [ ] Sessions timeout at 300 seconds
- [ ] Warnings sent 30 seconds before timeout
- [ ] Activity properly resets timeout
- [ ] Process cleanup on termination
- [ ] No resource leaks after 100 sessions
- [ ] Error messages are clear and actionable

## Phase 2: Specification Consolidation (Days 11-20)

### Day 11-13: Master Specification Creation

#### Document Structure
```markdown
# CLI Integration Master Specification v2.0

## 1. Overview
This document is the authoritative specification for CLI integration.
All other documents are deprecated as of [DATE].

## 2. Requirements
### 2.1 Functional Requirements
[Consolidated from all sources]

### 2.2 Non-Functional Requirements
[Performance, Security, Reliability]

## 3. Architecture
### 3.1 Component Architecture
[As implemented in Phase 1]

### 3.2 Data Flow
[Updated diagrams]

## 4. API Specification
### 4.1 REST API
[OpenAPI 3.0 format]

### 4.2 WebSocket API
[AsyncAPI 2.0 format]

## 5. Security Controls
### 5.1 Required Controls
[Must be implemented]

### 5.2 Optional Controls
[Can be phased]

## 6. Testing Requirements
[Linked to requirements]

## 7. Appendices
### 7.1 Migration from v1.x
### 7.2 Deprecated Features
### 7.3 Future Roadmap
```

### Day 14-16: Conflict Resolution

#### Resolution Process
1. Identify all conflicts
2. Document current implementation
3. Decide on correct approach
4. Update master specification
5. Create migration plan if needed

### Day 17-20: Documentation and Communication

#### Deliverables
- Master specification published
- Deprecation notices sent
- Team training conducted
- Migration guide available

## Phase 3: Implementation Standardization (Days 21-30)

### Day 21-24: Code Standardization

#### Standards to Implement
- Consistent error handling
- Unified logging format
- Standard response formats
- Common utility functions

### Day 25-27: Pattern Implementation

#### Patterns to Establish
- Repository pattern for data access
- Factory pattern for CLI providers
- Observer pattern for events
- Strategy pattern for authentication

### Day 28-30: Code Review and Cleanup

#### Cleanup Tasks
- Remove dead code
- Fix linting issues
- Update documentation strings
- Optimize imports

## Phase 4: Testing and Validation (Days 31-40)

### Day 31-34: Unit Test Coverage

#### Coverage Goals
- Overall: 80%
- Critical paths: 100%
- Error handling: 90%
- Edge cases: 70%

### Day 35-37: Integration Testing

#### Test Scenarios
- Multi-provider switching
- Concurrent sessions
- Failure recovery
- Performance under load

### Day 38-40: Acceptance Testing

#### User Scenarios
- Developer workflow
- Debugging session
- Long-running tasks
- Error recovery

## Phase 5: Production Hardening (Days 41-50)

### Day 41-43: Performance Optimization

#### Optimization Targets
- Session creation < 2s
- Command latency < 500ms
- Memory per session < 50MB
- CPU per session < 5%

### Day 44-46: Security Hardening

#### Security Tasks
- Input validation review
- Process isolation verification
- Authentication audit
- Penetration testing

### Day 47-50: Deployment and Monitoring

#### Deployment Tasks
- Production configuration
- Monitoring setup
- Alert configuration
- Runbook creation

## Risk Mitigation Strategies

### Technical Risks

| Risk | Mitigation |
|------|------------|
| Breaking changes | Feature flags for gradual rollout |
| Performance regression | Benchmark before/after each change |
| Security vulnerabilities | Security review at each phase |
| Integration failures | Comprehensive integration tests |

### Process Risks

| Risk | Mitigation |
|------|------------|
| Scope creep | Strict phase boundaries |
| Resource availability | Buffer time in schedule |
| Communication gaps | Daily standups |
| Knowledge silos | Pair programming |

## Success Metrics

### Phase 1 Success Metrics
- Zero TaskState errors: ✓
- Zero auth loops: ✓
- Proper timeouts: ✓
- Single CLI manager: ✓

### Phase 2 Success Metrics
- Master spec complete: [ ]
- Conflicts resolved: [ ]
- Team trained: [ ]

### Phase 3 Success Metrics
- Code standards met: [ ]
- Patterns implemented: [ ]
- Technical debt reduced: [ ]

### Phase 4 Success Metrics
- Test coverage > 80%: [ ]
- All acceptance tests pass: [ ]
- Performance targets met: [ ]

### Phase 5 Success Metrics
- Production deployed: [ ]
- Monitoring active: [ ]
- Zero critical issues: [ ]

## Timeline Summary

```
Week 1-2:  Phase 1 - Critical Stabilization ← CURRENT FOCUS
Week 3-4:  Phase 2 - Specification Consolidation
Week 5-6:  Phase 3 - Implementation Standardization  
Week 7-8:  Phase 4 - Testing and Validation
Week 9-10: Phase 5 - Production Hardening
```

## Resource Requirements

### Team Allocation
- **Phase 1**: 2 senior engineers (full-time)
- **Phase 2**: 1 engineer + 1 technical writer
- **Phase 3**: 2 engineers (full-time)
- **Phase 4**: 1 engineer + 1 QA engineer
- **Phase 5**: 1 engineer + 1 DevOps engineer

### Infrastructure
- Development environment (existing)
- Staging environment (existing)
- Production environment (prepare in Phase 5)

## Communication Plan

### Daily
- 15-minute standup
- Blockers and progress
- Specification questions

### Weekly
- Progress review with PM
- Technical deep dive
- Risk assessment update

### Phase Completion
- Demo to stakeholders
- Retrospective
- Phase report

## Next Actions

### Immediate (Next 24 hours)
1. Review and approve this plan
2. Assign engineers to Phase 1
3. Set up daily standup
4. Create Phase 1 tracking board
5. Begin TaskState unification

### This Week
1. Complete Phase 1, Day 1-5 tasks
2. Daily progress updates
3. Identify any additional blockers
4. Prepare for Day 6-10 tasks

### Next Week
1. Complete Phase 1, Day 6-10 tasks
2. Phase 1 validation and sign-off
3. Begin Phase 2 preparation
4. Resource allocation for Phase 2

This plan provides a clear, actionable path to stabilize and standardize the CLI integration system with minimal risk and maximum visibility.