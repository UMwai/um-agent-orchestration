# CLI Integration Architecture Analysis & Design

## Current Issues Analysis

### 1. Dashboard CLI Interface Issues
- **Problem**: Current CLI interface in dashboard.html (lines 1865-1965) is purely simulated
- **Current**: JavaScript functions process commands like `help`, `tasks`, `metrics` locally
- **Missing**: No actual CLI process spawning or real CLI integration

### 2. Provider System Limitations  
- **Problem**: All CLI providers use one-shot `subprocess.run()` execution
- **Current**: Each call spawns a new process, executes, and terminates
- **Missing**: Persistent CLI sessions, interactive mode, streaming output

### 3. Process Management Gaps
- **Problem**: No process lifecycle management for CLI instances
- **Missing**: Session management, process cleanup, error handling, resource monitoring

### 4. Real-Time Communication Issues
- **Problem**: No real-time I/O streaming between dashboard and CLI processes
- **Current**: WebSocket only broadcasts task updates
- **Missing**: Bidirectional CLI I/O streaming, command queuing

## Proposed Architecture

### Core Components

#### 1. CLI Process Manager (`orchestrator/cli_manager.py`)
```python
class CLISessionManager:
    """Manages long-running CLI process sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, CLISession] = {}
        self.process_pool: Dict[str, subprocess.Popen] = {}
        
    async def spawn_cli_session(self, provider: str, session_id: str) -> CLISession
    async def terminate_session(self, session_id: str) -> bool
    async def send_command(self, session_id: str, command: str) -> str
    async def stream_output(self, session_id: str) -> AsyncIterator[str]
    def cleanup_stale_sessions(self) -> None
```

#### 2. CLI Session Model (`orchestrator/models.py` extension)
```python
@dataclass
class CLISession:
    session_id: str
    provider: str
    process: subprocess.Popen
    created_at: datetime
    last_activity: datetime
    status: CLISessionStatus
    working_directory: str
    environment_vars: Dict[str, str]
    
class CLISessionStatus(Enum):
    STARTING = "starting"
    ACTIVE = "active" 
    IDLE = "idle"
    TERMINATED = "terminated"
    ERROR = "error"
```

#### 3. Real-Time CLI Provider (`providers/cli_interactive_provider.py`)
```python
class InteractiveCLIProvider:
    """Provider for real-time interactive CLI sessions"""
    
    async def start_session(self, provider_config: ProviderCfg, cwd: str) -> CLISession
    async def send_command_async(self, session: CLISession, command: str) -> AsyncIterator[str]
    async def handle_cli_lifecycle(self, session: CLISession) -> None
    def format_prompt_for_provider(self, provider: str, prompt: str) -> str
```

#### 4. WebSocket CLI Bridge (`orchestrator/websocket_cli.py`)
```python
class CLIWebSocketHandler:
    """Bridge between WebSocket clients and CLI sessions"""
    
    async def handle_cli_command(self, websocket: WebSocket, message: dict) -> None
    async def stream_cli_output(self, session_id: str, websocket: WebSocket) -> None
    async def broadcast_session_status(self, session_id: str, status: dict) -> None
```

### API Endpoints Design

#### New FastAPI Endpoints (`orchestrator/app.py` additions)

```python
@app.post("/api/cli/sessions")
async def create_cli_session(
    provider: str, 
    working_directory: Optional[str] = None,
    environment: Optional[Dict[str, str]] = None
) -> CLISession:
    """Spawn a new CLI session with specified provider"""

@app.get("/api/cli/sessions")  
async def list_cli_sessions() -> List[CLISession]:
    """List all active CLI sessions"""

@app.get("/api/cli/sessions/{session_id}")
async def get_cli_session(session_id: str) -> CLISession:
    """Get details of a specific CLI session"""

@app.post("/api/cli/sessions/{session_id}/commands")
async def send_cli_command(session_id: str, command: CLICommand) -> CLIResponse:
    """Send command to CLI session and get response"""

@app.delete("/api/cli/sessions/{session_id}")
async def terminate_cli_session(session_id: str) -> dict:
    """Terminate a CLI session and cleanup resources"""

@app.websocket("/ws/cli/{session_id}")
async def cli_websocket(websocket: WebSocket, session_id: str):
    """Real-time bidirectional CLI I/O via WebSocket"""
```

### Dashboard Integration Design

#### Enhanced CLI Interface (`dashboard/dashboard.html` modifications)

Replace the current simulated terminal with real CLI integration:

```javascript
class RealCLITerminal {
    constructor(sessionId, provider) {
        this.sessionId = sessionId;
        this.provider = provider;
        this.websocket = null;
        this.outputBuffer = [];
    }

    async initializeSession() {
        // Create CLI session via API
        const response = await fetch('/api/cli/sessions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                provider: this.provider,
                working_directory: '/home/umwai/um-agent-orchestration'
            })
        });
        
        const session = await response.json();
        this.sessionId = session.session_id;
        
        // Connect WebSocket for real-time I/O
        this.websocket = new WebSocket(`ws://localhost:8001/ws/cli/${this.sessionId}`);
        this.setupWebSocketHandlers();
    }

    setupWebSocketHandlers() {
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'output') {
                this.appendOutput(data.content);
            } else if (data.type === 'error') {
                this.appendError(data.content);
            }
        };
    }

    async sendCommand(command) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'command',
                content: command
            }));
        }
    }
}
```

### Process Management Strategy

#### 1. Session Lifecycle Management
- **Spawn**: Create new CLI process with proper environment setup
- **Monitor**: Track process health, resource usage, activity
- **Timeout**: Auto-terminate idle sessions after configurable timeout  
- **Cleanup**: Proper cleanup of processes, file handles, resources

#### 2. Provider-Specific Initialization

**Claude CLI Session:**
```bash
claude --dangerously-skip-permissions --session-mode --working-dir /path/to/repo
```

**Codex CLI Session:**
```bash
codex --ask-for-approval never --sandbox danger-full-access --interactive
```

**Gemini CLI Session:**
```bash
gemini --interactive-mode --working-directory /path/to/repo
```

#### 3. Command Queuing & Rate Limiting
- Queue commands if CLI is busy processing
- Rate limiting to prevent overwhelming CLI processes
- Priority queuing for different command types

### Security & Resource Management

#### 1. Security Considerations
- Sandbox CLI processes appropriately
- Limit file system access to specific directories
- Resource limits (memory, CPU, runtime)
- Command validation and sanitization

#### 2. Resource Management  
- Maximum concurrent sessions per user
- Session timeout and cleanup
- Process memory monitoring
- Graceful shutdown handling

#### 3. Error Handling
- Process crash recovery
- Network disconnection handling
- Command timeout handling
- Partial output recovery

### Implementation Plan

#### Phase 1: Core Infrastructure
1. Implement `CLISessionManager` class
2. Add CLI session data models
3. Create basic process spawning logic
4. Add session cleanup mechanisms

#### Phase 2: Provider Integration
1. Extend existing CLI providers with session support
2. Implement provider-specific initialization
3. Add command formatting for each provider
4. Test CLI process management

#### Phase 3: WebSocket & API Integration  
1. Implement WebSocket CLI bridge
2. Add new FastAPI endpoints
3. Create real-time I/O streaming
4. Add session status broadcasting

#### Phase 4: Dashboard Enhancement
1. Replace simulated CLI with real integration
2. Add session management UI
3. Implement real-time terminal display
4. Add CLI provider switching

#### Phase 5: Advanced Features
1. Command history persistence
2. Session sharing between users
3. CLI output parsing and enhancement
4. Advanced session analytics

## Benefits of This Architecture

### 1. Real CLI Integration
- Actual CLI processes instead of simulation
- Full access to CLI capabilities and features
- Real-time interactive sessions

### 2. Better User Experience
- True CLI behavior and responses
- Real-time output streaming
- Persistent sessions across interactions

### 3. Scalable Design
- Multiple concurrent CLI sessions
- Provider-agnostic session management
- Resource-aware process management

### 4. Robust Process Management
- Proper lifecycle management
- Error recovery and cleanup  
- Resource monitoring and limits

This architecture provides a solid foundation for real CLI integration while maintaining the existing provider system's flexibility and the dashboard's user-friendly interface.