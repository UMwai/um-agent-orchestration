# CLI Integration Specification

## Project Overview

### Executive Summary
The AutoDev system currently uses a simulated CLI interface in its dashboard that does not connect to actual CLI tools. This specification defines requirements and architecture for implementing real CLI integration, enabling the web dashboard to spawn, manage, and communicate with actual CLI processes (claude, codex, gemini) in real-time.

### Business Objectives
- **Primary Goal**: Enable real-time interaction between web dashboard and local CLI tools
- **Secondary Goals**:
  - Maintain system security and process isolation
  - Provide seamless user experience with minimal latency
  - Support concurrent CLI sessions across multiple agents
  - Enable structured prompt submission and output capture

### Success Criteria
- Dashboard can successfully spawn and manage CLI processes
- Real-time bidirectional communication between frontend and CLI tools
- Response latency < 500ms for command initiation
- Support for at least 10 concurrent CLI sessions
- 99.9% reliability for CLI process management
- Zero security vulnerabilities in process spawning

## System Architecture

### Component Overview
```
┌─────────────────┐       ┌──────────────────┐       ┌─────────────────┐
│   Web Dashboard │◄─────►│  FastAPI Backend │◄─────►│  CLI Processes  │
│   (React/HTML)  │  WS   │  (Orchestrator)  │ Spawn │ (claude/codex)  │
└─────────────────┘       └──────────────────┘       └─────────────────┘
         │                         │                          │
         │                    ┌────▼────┐              ┌─────▼──────┐
         └───────────────────►│ Session │              │   Process   │
              Real-time       │ Manager │              │   Manager   │
              Updates         └─────────┘              └────────────┘
```

### Data Flow
1. User submits prompt via dashboard interface
2. WebSocket message sent to backend with session ID and prompt
3. Backend spawns or reuses CLI process based on session
4. Structured prompt submitted to CLI process
5. Output captured and streamed back via WebSocket
6. Dashboard renders real-time output with formatting

## Functional Requirements

### FR-1: CLI Process Management

#### FR-1.1: Process Spawning
- **Description**: System shall spawn CLI processes on demand
- **Acceptance Criteria**:
  - Process spawned within 2 seconds of request
  - Environment variables correctly configured
  - Working directory set to appropriate worktree
  - Process isolation maintained between sessions

#### FR-1.2: Process Lifecycle
- **Description**: System shall manage full lifecycle of CLI processes
- **Acceptance Criteria**:
  - Processes tracked with unique session IDs
  - Idle processes terminated after 5 minutes
  - Graceful shutdown on system exit
  - Resource cleanup on process termination

#### FR-1.3: Process Pool Management
- **Description**: System shall maintain pool of reusable processes
- **Acceptance Criteria**:
  - Pool size configurable (min: 0, max: 20)
  - Process reuse for same session/agent
  - Health checks every 30 seconds
  - Automatic restart of failed processes

### FR-2: Communication Protocol

#### FR-2.1: WebSocket Connection
- **Description**: Real-time bidirectional communication via WebSocket
- **Acceptance Criteria**:
  - Connection established within 1 second
  - Automatic reconnection on disconnect
  - Message queuing during reconnection
  - Heartbeat every 30 seconds

#### FR-2.2: Message Protocol
- **Description**: Structured message format for commands and responses
- **Message Types**:
  ```json
  {
    "type": "command|output|status|error",
    "sessionId": "uuid",
    "provider": "claude|codex|gemini",
    "data": {
      "command": "string",
      "output": "string",
      "status": "initializing|ready|processing|completed|error",
      "error": "string"
    },
    "timestamp": "ISO8601"
  }
  ```

#### FR-2.3: Stream Processing
- **Description**: Real-time streaming of CLI output
- **Acceptance Criteria**:
  - Output chunks sent as available
  - Buffering for incomplete lines
  - ANSI escape code handling
  - UTF-8 encoding support

### FR-3: Session Management

#### FR-3.1: Session Creation
- **Description**: Create and track user sessions
- **Acceptance Criteria**:
  - Unique session ID generation
  - Session metadata storage
  - Provider preference tracking
  - Session persistence across reconnects

#### FR-3.2: Session State
- **Description**: Maintain session state and history
- **State Model**:
  ```python
  class SessionState:
      id: str
      provider: str
      process_id: Optional[int]
      status: SessionStatus
      created_at: datetime
      last_activity: datetime
      history: List[Message]
      metadata: Dict[str, Any]
  ```

#### FR-3.3: Session Recovery
- **Description**: Recover sessions after failures
- **Acceptance Criteria**:
  - Session state persisted to Redis
  - Recovery within 5 seconds
  - History preservation
  - Graceful degradation on data loss

### FR-4: Provider Integration

#### FR-4.1: Claude CLI Integration
- **Description**: Full integration with claude CLI tool
- **Acceptance Criteria**:
  - Support for --dangerously-skip-permissions flag
  - JSON and text output format support
  - Project context preservation
  - Error message parsing

#### FR-4.2: Codex CLI Integration
- **Description**: Full integration with codex CLI tool
- **Acceptance Criteria**:
  - Support for --sandbox danger-full-access
  - Approval mode configuration
  - Interactive mode support
  - Command chaining capability

#### FR-4.3: Gemini CLI Integration
- **Description**: Full integration with gemini CLI tool
- **Acceptance Criteria**:
  - Standard CLI argument support
  - Output format configuration
  - Model selection support
  - Token limit configuration

### FR-5: User Interface

#### FR-5.1: CLI Terminal Component
- **Description**: Terminal-like interface in dashboard
- **Acceptance Criteria**:
  - Monospace font rendering
  - ANSI color support
  - Copy/paste functionality
  - Command history navigation

#### FR-5.2: Provider Selection
- **Description**: UI for selecting and switching providers
- **Acceptance Criteria**:
  - Dropdown/tab interface
  - Provider status indicators
  - Model selection within provider
  - Preference persistence

#### FR-5.3: Session Management UI
- **Description**: Interface for managing active sessions
- **Acceptance Criteria**:
  - List of active sessions
  - Session switching capability
  - History viewing
  - Session termination controls

## Technical Requirements

### TR-1: Performance Requirements

#### TR-1.1: Latency
- Command initiation: < 500ms
- First byte response: < 2s
- Stream chunk delivery: < 100ms
- UI update rendering: < 16ms (60fps)

#### TR-1.2: Throughput
- Concurrent sessions: 10 minimum, 50 target
- Messages per second: 100 per session
- Output streaming rate: 10KB/s per session
- Total system throughput: 1MB/s

#### TR-1.3: Resource Usage
- Memory per session: < 50MB
- CPU per session: < 5% of single core
- Disk I/O: < 1MB/s per session
- Network bandwidth: < 100KB/s per session

### TR-2: Security Requirements

#### TR-2.1: Process Isolation
- **Requirement**: Each CLI process runs in isolated environment
- **Implementation**:
  - Separate process groups
  - Resource limits (ulimit)
  - No shell injection vulnerabilities
  - Input sanitization

#### TR-2.2: Authentication
- **Requirement**: Secure session authentication
- **Implementation**:
  - JWT token validation
  - Session token rotation
  - Rate limiting per client
  - IP-based access control

#### TR-2.3: Authorization
- **Requirement**: Role-based access control
- **Implementation**:
  - Provider access permissions
  - Full-access mode restrictions
  - Command filtering
  - Output redaction for sensitive data

### TR-3: Reliability Requirements

#### TR-3.1: Availability
- System uptime: 99.9% (8.76 hours downtime/year)
- Graceful degradation on component failure
- Automatic recovery mechanisms
- Health monitoring endpoints

#### TR-3.2: Fault Tolerance
- Process crash recovery
- Network disconnection handling
- Queue overflow protection
- Deadlock prevention

#### TR-3.3: Data Integrity
- Message ordering preservation
- No data loss during streaming
- Transaction consistency
- Checkpoint and recovery

### TR-4: Scalability Requirements

#### TR-4.1: Horizontal Scaling
- Multiple backend instances support
- Session affinity routing
- Shared state via Redis
- Load balancing capability

#### TR-4.2: Vertical Scaling
- Process pool auto-scaling
- Dynamic resource allocation
- Memory management optimization
- Connection pooling

## Implementation Architecture

### Backend Components

#### CLI Process Manager
```python
class CLIProcessManager:
    """Manages lifecycle of CLI processes"""
    
    def spawn_process(
        self,
        provider: str,
        session_id: str,
        working_dir: str,
        env_vars: Dict[str, str]
    ) -> Process
    
    def send_command(
        self,
        process: Process,
        command: str
    ) -> AsyncIterator[str]
    
    def terminate_process(
        self,
        process: Process,
        timeout: float = 5.0
    ) -> None
```

#### WebSocket Handler
```python
class CLIWebSocketHandler:
    """Handles WebSocket connections for CLI integration"""
    
    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str
    ) -> None
    
    async def process_message(
        self,
        message: CLIMessage,
        session: Session
    ) -> CLIResponse
    
    async def stream_output(
        self,
        output: AsyncIterator[str],
        websocket: WebSocket
    ) -> None
```

#### Session Manager
```python
class SessionManager:
    """Manages CLI sessions and state"""
    
    def create_session(
        self,
        provider: str,
        user_id: str
    ) -> Session
    
    def get_session(
        self,
        session_id: str
    ) -> Optional[Session]
    
    def update_session_state(
        self,
        session_id: str,
        state: SessionState
    ) -> None
```

### Frontend Components

#### CLI Terminal Component
```typescript
interface CLITerminalProps {
    sessionId: string;
    provider: string;
    onCommand: (command: string) => void;
}

class CLITerminal extends React.Component<CLITerminalProps> {
    // Terminal rendering and interaction logic
}
```

#### WebSocket Client
```typescript
class CLIWebSocketClient {
    connect(url: string): Promise<void>
    send(message: CLIMessage): void
    onMessage(handler: (response: CLIResponse) => void): void
    disconnect(): void
}
```

## Testing Strategy

### Unit Tests
- Process spawning and management
- Message parsing and formatting
- Session state transitions
- Error handling scenarios

### Integration Tests
- End-to-end CLI communication
- WebSocket message flow
- Multi-provider switching
- Session recovery

### Performance Tests
- Load testing with concurrent sessions
- Latency measurements
- Resource usage monitoring
- Stress testing edge cases

### Security Tests
- Input injection attempts
- Process escape attempts
- Authentication bypass tests
- Resource exhaustion tests

## Risk Assessment

### High Risk Items
1. **Process escape/injection**: Malicious input could escape process sandbox
   - Mitigation: Strict input validation, process isolation
   
2. **Resource exhaustion**: Unlimited process spawning could exhaust system
   - Mitigation: Process limits, rate limiting, resource quotas

3. **Data leakage**: Sensitive information in CLI output
   - Mitigation: Output filtering, secure logging

### Medium Risk Items
1. **Performance degradation**: High load causing slow responses
   - Mitigation: Performance monitoring, auto-scaling
   
2. **Network instability**: WebSocket disconnections
   - Mitigation: Reconnection logic, message queuing

### Low Risk Items
1. **UI rendering issues**: Terminal output formatting problems
   - Mitigation: Comprehensive testing, fallback rendering

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] CLI Process Manager implementation
- [ ] Basic WebSocket handler
- [ ] Session management foundation
- [ ] Unit test coverage

### Phase 2: Provider Integration (Week 3-4)
- [ ] Claude CLI integration
- [ ] Codex CLI integration
- [ ] Gemini CLI integration
- [ ] Integration testing

### Phase 3: Frontend Development (Week 5-6)
- [ ] Terminal component
- [ ] WebSocket client
- [ ] Provider selection UI
- [ ] End-to-end testing

### Phase 4: Production Readiness (Week 7-8)
- [ ] Performance optimization
- [ ] Security hardening
- [ ] Documentation
- [ ] Deployment preparation

## Acceptance Criteria

### Functional Acceptance
- All three CLI providers (claude, codex, gemini) fully integrated
- Real-time output streaming working reliably
- Session management and recovery functional
- UI provides smooth user experience

### Performance Acceptance
- Latency metrics within specified limits
- Concurrent session support verified
- Resource usage within bounds
- No memory leaks detected

### Security Acceptance
- Security audit passed
- No known vulnerabilities
- Process isolation verified
- Authentication/authorization working

### Documentation Acceptance
- API documentation complete
- User guide written
- Deployment guide available
- Troubleshooting guide prepared
