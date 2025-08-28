# AutoDev CLI Integration Developer Guide

**Version:** 1.0  
**Date:** August 27, 2025  
**Audience:** Developers, Contributors, System Architects  

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Design Decisions](#design-decisions)
3. [Adding New CLI Providers](#adding-new-cli-providers)
4. [Extending Session Management](#extending-session-management)
5. [Testing and Debugging](#testing-and-debugging)
6. [Performance Considerations](#performance-considerations)
7. [Contributing Guidelines](#contributing-guidelines)
8. [API Reference](#api-reference)

## Architecture Overview

The AutoDev CLI Integration is built on a modular architecture that separates concerns across multiple layers:

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Dashboard/Client                          │
│                 (WebSocket Client)                           │
└─────────────────┬───────────────────────────────────────────┘
                  │ WebSocket Connection
                  │ (JWT Authenticated)
┌─────────────────▼───────────────────────────────────────────┐
│                FastAPI Application                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   WebSocket     │  │  Task Manager   │  │   Metrics   │ │
│  │    Handler      │  │                 │  │  Exporter   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                CLI Session Manager                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │    Session      │  │   Process       │  │  Recovery   │ │
│  │   Tracking      │  │   Manager       │  │   System    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│              Persistence Layer                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │     Redis       │  │     SQLite      │  │    Task     │ │
│  │ (Real-time)     │  │ (Persistence)   │  │  Recovery   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                 CLI Processes                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │     Claude      │  │     Codex       │  │   Gemini    │ │
│  │      CLI        │  │      CLI        │  │     CLI     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. CLI Session Manager (`orchestrator/cli_session_manager.py`)

**Purpose**: Manages multiple CLI sessions with process lifecycle management

**Key Responsibilities**:
- Creates and manages CLI process instances
- Handles PTY (pseudo-terminal) interaction for real terminal behavior
- Manages session state transitions and error handling
- Integrates with persistence layer for session recovery

**Key Classes**:
```python
class CLISessionState(Enum):
    """8 distinct states for comprehensive session tracking"""
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running" 
    WAITING_INPUT = "waiting_input"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    TERMINATED = "terminated"

class CLIProcessManager:
    """Manages single CLI process with PTY interaction"""
    async def start_process(self, command: List[str], env: Dict[str, str])
    async def send_input(self, text: str)
    async def terminate(self)

class CLISessionManager:
    """Global session coordinator with Redis persistence"""
    async def create_session(self, cli_tool: str, mode: str, cwd: str, user_id: str) -> str
    async def start_cli_process(self, session_id: str, full_access: bool) -> bool
    async def send_input_to_session(self, session_id: str, input_text: str) -> bool
```

#### 2. WebSocket Handler (`orchestrator/cli_websocket.py`)

**Purpose**: Real-time bidirectional communication with clients

**Key Features**:
- JWT authentication with configurable secrets
- Message routing and validation
- Connection lifecycle management with heartbeat
- Message queuing during temporary disconnections
- Broadcasting to multiple connections per session

**Message Protocol**:
```python
@dataclass
class CLIMessage:
    type: MessageType  # command, output, status, error, ping, pong, cancel, auth
    session_id: str
    data: Dict[str, Any]
    timestamp: str
    message_id: str = None

class MessageType(Enum):
    COMMAND = "command"     # Client -> Server: Execute command
    OUTPUT = "output"       # Server -> Client: CLI output
    STATUS = "status"       # Server -> Client: Session status
    ERROR = "error"         # Server -> Client: Error occurred
    PING = "ping"           # Heartbeat ping
    PONG = "pong"           # Heartbeat pong  
    CANCEL = "cancel"       # Client -> Server: Cancel command
    AUTH = "auth"           # Client -> Server: Authentication
```

#### 3. Persistence Layer (`orchestrator/persistence.py`)

**Purpose**: Dual-write persistence with Redis and SQLite

**Architecture**:
- **Redis**: Real-time session coordination and task status
- **SQLite**: Persistent storage with full history and recovery
- **Dual-Write**: All critical data written to both systems

**Key Models**:
```python
class TaskState(str, Enum):
    """Enhanced task states for lifecycle tracking"""
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETING = "completing"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

class TaskPersistenceManager:
    """Comprehensive persistence with SQLite and Redis integration"""
    def create_task(self, spec: TaskSpec) -> TaskRecord
    def update_task_state(self, task_id: str, new_state: TaskState, **kwargs) -> bool
    def get_task_history(self, task_id: str) -> List[TaskHistoryRecord]
```

#### 4. Recovery System (`orchestrator/recovery.py`)

**Purpose**: System restart recovery and data consistency

**Recovery Process**:
1. **Startup Recovery**: Restore tasks from persistent storage
2. **Interrupted Task Handling**: Mark running tasks as failed
3. **Data Consistency**: Cross-validate Redis and SQLite data
4. **Cleanup**: Remove orphaned entries and expired data

## Design Decisions

### 1. PTY-Based Process Management

**Decision**: Use pseudo-terminal (PTY) instead of standard subprocess pipes

**Rationale**:
- CLI tools expect terminal interaction for authentication prompts
- PTY provides real terminal behavior with proper signal handling
- Better compatibility with interactive CLI features
- Proper handling of terminal control sequences and colors

**Implementation**:
```python
# PTY creation for real terminal interaction
self.pty_master, self.pty_slave = pty.openpty()

self.process = subprocess.Popen(
    command,
    stdin=self.pty_slave,
    stdout=self.pty_slave, 
    stderr=self.pty_slave,
    preexec_fn=os.setsid,  # Create process group for proper signal handling
    env=process_env
)
```

### 2. Dual-Write Persistence Strategy

**Decision**: Write to both Redis (real-time) and SQLite (persistence)

**Rationale**:
- Redis provides fast cross-process communication for real-time updates
- SQLite ensures data persistence across system restarts
- Allows for complex querying and reporting on historical data
- Provides redundancy and data recovery capabilities

**Trade-offs**:
- Increased storage overhead (data stored twice)
- Potential consistency issues (mitigated with careful transaction handling)
- Additional complexity in data management

### 3. JWT-Based WebSocket Authentication

**Decision**: Use JWT tokens for WebSocket authentication instead of session cookies

**Rationale**:
- Stateless authentication suitable for distributed systems
- Easy integration with existing authentication systems
- Flexible token payload for user context and permissions
- Better security model for API-first architecture

**Implementation**:
```python
def _verify_jwt_token(self, token: str) -> Optional[str]:
    """Verify JWT token and return user ID."""
    try:
        payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
        return payload.get("user_id")
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
```

### 4. Asynchronous Architecture

**Decision**: Full async/await implementation for all I/O operations

**Rationale**:
- Better concurrency for multiple CLI sessions
- Non-blocking WebSocket communication
- Efficient resource utilization
- Better scalability for high-load scenarios

**Implementation Pattern**:
```python
async def _handle_messages(self, connection: WebSocketConnection):
    """Main message handling loop with async I/O"""
    while connection.websocket.client_state == WebSocketState.CONNECTED:
        try:
            data = await asyncio.wait_for(
                connection.websocket.receive_text(),
                timeout=60.0
            )
            message = CLIMessage.from_json(data)
            await self._route_message(connection, message)
        except asyncio.TimeoutError:
            await self._send_ping(connection)
```

### 5. Provider-Agnostic CLI Interface

**Decision**: Unified interface for all CLI providers with provider-specific customization

**Rationale**:
- Consistent developer experience across different AI providers
- Easy to add new providers without changing core architecture
- Provider-specific optimizations while maintaining common interface
- Simplified client implementation

**Pattern**:
```python
def _build_cli_command(self, cli_tool: str, mode: str, full_access: bool) -> List[str]:
    """Build CLI command based on tool and configuration"""
    if cli_tool == "claude":
        return ["claude", "--dangerously-skip-permissions"] if full_access else ["claude"]
    elif cli_tool == "codex":
        return ["codex", "--ask-for-approval", "never", "--sandbox", "danger-full-access", "exec"] if full_access else ["codex"]
    # ... provider-specific logic
```

## Adding New CLI Providers

### Step 1: Define Provider Configuration

Add provider configuration to the CLI session manager:

```python
# In _build_cli_command method
elif cli_tool == "your_provider":
    if full_access and mode == "interactive":
        return ["your-cli-tool", "--full-access", "--auto-approve"]
    else:
        return ["your-cli-tool", "--standard-mode"]
```

### Step 2: Add Authentication Detection

Implement provider-specific authentication pattern detection:

```python
# In _read_output method of CLIProcessManager
elif self.session_info.cli_tool == "your_provider":
    if any(pattern in output_lower for pattern in [
        'api key required', 'please login', 'authentication needed'
    ]):
        self.session_info.state = CLISessionState.WAITING_INPUT
        self.session_info.authentication_required = True
        self.session_info.auth_prompt = "Your Provider API key required"
```

### Step 3: Configure Environment Variables

Add environment variable handling:

```python
# In _get_cli_environment method
elif cli_tool == "your_provider":
    if os.getenv("YOUR_PROVIDER_API_KEY"):
        env["YOUR_PROVIDER_API_KEY"] = os.getenv("YOUR_PROVIDER_API_KEY")
    if os.getenv("YOUR_PROVIDER_PROJECT_ID"):
        env["YOUR_PROVIDER_PROJECT_ID"] = os.getenv("YOUR_PROVIDER_PROJECT_ID")
```

### Step 4: Add Provider-Specific API Implementation

Create API provider implementation following the existing pattern:

```python
# providers/your_provider_api.py
from __future__ import annotations
import os
from orchestrator.settings import ProviderCfg

def call_your_provider_api(prompt: str, cfg: ProviderCfg) -> str:
    """
    Call Your Provider API using the official SDK
    """
    api_key = os.environ.get("YOUR_PROVIDER_API_KEY")
    if not api_key:
        raise RuntimeError("YOUR_PROVIDER_API_KEY environment variable is required")
    
    # Initialize your provider's client
    client = YourProviderClient(api_key=api_key)
    
    try:
        # Make API call
        response = client.generate(
            prompt=prompt,
            model=cfg.model or "your-default-model"
        )
        
        if not response.text:
            raise RuntimeError("Empty response from Your Provider API")
            
        return response.text
    except Exception as e:
        raise RuntimeError(f"Your Provider API call failed: {str(e)}")
```

### Step 5: Update Provider Router

Add your provider to the router configuration:

```python
# providers/router.py - Add to PROVIDER_CONFIGS
"your_provider": ProviderConfig(
    name="Your Provider",
    modes=["cli", "api"],
    api_module="providers.your_provider_api",
    api_function="call_your_provider_api",
    cli_command="your-cli-tool",
    models=["model-1", "model-2", "model-3"],
    default_model="model-1"
)
```

### Step 6: Add Provider Tests

Create comprehensive tests for your provider:

```python
# tests/unit/test_your_provider.py
import pytest
from unittest.mock import patch, MagicMock
from providers.your_provider_api import call_your_provider_api
from orchestrator.settings import ProviderCfg

class TestYourProvider:
    def test_api_call_success(self):
        """Test successful API call"""
        with patch.dict(os.environ, {'YOUR_PROVIDER_API_KEY': 'test-key'}):
            with patch('your_provider_client.Client') as mock_client:
                mock_response = MagicMock()
                mock_response.text = "Generated response"
                mock_client.return_value.generate.return_value = mock_response
                
                cfg = ProviderCfg(model="test-model")
                result = call_your_provider_api("test prompt", cfg)
                
                assert result == "Generated response"
                mock_client.return_value.generate.assert_called_once()
    
    def test_missing_api_key(self):
        """Test error when API key is missing"""
        with patch.dict(os.environ, {}, clear=True):
            cfg = ProviderCfg()
            with pytest.raises(RuntimeError, match="YOUR_PROVIDER_API_KEY environment variable is required"):
                call_your_provider_api("test prompt", cfg)
    
    def test_cli_command_generation(self):
        """Test CLI command generation"""
        from orchestrator.cli_session_manager import CLISessionManager
        
        manager = CLISessionManager()
        command = manager._build_cli_command("your_provider", "interactive", True)
        assert command == ["your-cli-tool", "--full-access", "--auto-approve"]
        
        command = manager._build_cli_command("your_provider", "standard", False) 
        assert command == ["your-cli-tool", "--standard-mode"]
```

### Step 7: Update Documentation

Add provider documentation:

```markdown
# Your Provider CLI Integration

## Installation

```bash
# Install Your Provider CLI
curl -O https://your-provider.com/install.sh
chmod +x install.sh
./install.sh

# Verify installation
your-cli-tool --version
```

## Configuration

```bash
# Set API key
export YOUR_PROVIDER_API_KEY=your_api_key_here
export YOUR_PROVIDER_PROJECT_ID=your_project_id  # Optional
```

## Usage

```bash
# Create Your Provider CLI session
curl -X POST http://localhost:8001/cli/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "cli_tool": "your_provider",
    "mode": "interactive",
    "full_access": true
  }'
```
```

## Extending Session Management

### Custom Session States

Add custom session states for specific workflow requirements:

```python
class ExtendedCLISessionState(Enum):
    """Extended session states for custom workflows"""
    # Standard states
    INITIALIZING = "initializing"
    RUNNING = "running"
    # Custom states
    REVIEWING_CODE = "reviewing_code"
    WAITING_APPROVAL = "waiting_approval"
    GENERATING_DOCS = "generating_docs"
    VALIDATING_OUTPUT = "validating_output"

class CustomCLISessionManager(CLISessionManager):
    """Extended session manager with custom state handling"""
    
    def __init__(self):
        super().__init__()
        self.custom_state_handlers = {
            ExtendedCLISessionState.REVIEWING_CODE: self._handle_code_review,
            ExtendedCLISessionState.WAITING_APPROVAL: self._handle_approval_wait,
        }
    
    async def _handle_code_review(self, session_id: str, data: Dict[str, Any]):
        """Custom handler for code review state"""
        # Implement custom logic for code review workflow
        pass
        
    async def transition_to_custom_state(self, session_id: str, new_state: ExtendedCLISessionState):
        """Transition to custom state with specific handling"""
        session_info = self.get_session_info(session_id)
        if session_info:
            session_info.state = new_state
            
            # Call custom state handler if available
            handler = self.custom_state_handlers.get(new_state)
            if handler:
                await handler(session_id, {"transition_time": time.time()})
```

### Session Middleware

Implement middleware for cross-cutting concerns:

```python
class SessionMiddleware:
    """Base class for session middleware"""
    
    async def before_command(self, session_id: str, command: str) -> str:
        """Process command before sending to CLI"""
        return command
        
    async def after_output(self, session_id: str, output: str) -> str:
        """Process output after receiving from CLI"""
        return output
        
    async def on_state_change(self, session_id: str, old_state: str, new_state: str):
        """Handle state changes"""
        pass

class LoggingMiddleware(SessionMiddleware):
    """Middleware for detailed session logging"""
    
    async def before_command(self, session_id: str, command: str) -> str:
        logger.info(f"Session {session_id} executing command: {command[:100]}...")
        return command
        
    async def after_output(self, session_id: str, output: str) -> str:
        logger.debug(f"Session {session_id} produced output: {len(output)} chars")
        return output

class SecurityMiddleware(SessionMiddleware):
    """Middleware for security filtering"""
    
    SENSITIVE_PATTERNS = [
        r'password\s*[=:]\s*\w+',
        r'api[_-]?key\s*[=:]\s*\w+',
        r'secret\s*[=:]\s*\w+',
    ]
    
    async def after_output(self, session_id: str, output: str) -> str:
        """Filter sensitive information from output"""
        for pattern in self.SENSITIVE_PATTERNS:
            output = re.sub(pattern, '[REDACTED]', output, flags=re.IGNORECASE)
        return output

# Integrate middleware into session manager
class MiddlewareEnabledSessionManager(CLISessionManager):
    def __init__(self):
        super().__init__()
        self.middleware_stack = [
            LoggingMiddleware(),
            SecurityMiddleware(),
        ]
    
    async def send_input_to_session(self, session_id: str, input_text: str) -> bool:
        """Send input through middleware stack"""
        processed_input = input_text
        for middleware in self.middleware_stack:
            processed_input = await middleware.before_command(session_id, processed_input)
        
        return await super().send_input_to_session(session_id, processed_input)
```

### Custom Session Persistence

Extend persistence with custom data requirements:

```python
class CustomTaskRecord(TaskRecord):
    """Extended task record with custom fields"""
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    workflow_stage: str = "initial"
    approval_required: bool = False
    security_level: str = "standard"

class ExtendedPersistenceManager(TaskPersistenceManager):
    """Extended persistence with custom data handling"""
    
    def create_custom_task(self, spec: TaskSpec, custom_data: Dict[str, Any]) -> CustomTaskRecord:
        """Create task with custom data"""
        base_record = super().create_task(spec)
        
        # Convert to custom record with additional fields
        custom_record = CustomTaskRecord(
            **base_record.dict(),
            custom_metadata=custom_data.get('metadata', {}),
            workflow_stage=custom_data.get('workflow_stage', 'initial'),
            approval_required=custom_data.get('approval_required', False),
            security_level=custom_data.get('security_level', 'standard')
        )
        
        # Store custom fields in database
        self._store_custom_fields(custom_record)
        return custom_record
    
    def _store_custom_fields(self, record: CustomTaskRecord):
        """Store custom fields in extended table"""
        conn = self._get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO task_custom_data (
                task_id, custom_metadata, workflow_stage, 
                approval_required, security_level
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            record.id,
            json.dumps(record.custom_metadata),
            record.workflow_stage,
            record.approval_required,
            record.security_level
        ))
```

## Testing and Debugging

### Unit Testing Framework

Comprehensive unit testing for CLI integration components:

```python
# tests/unit/test_cli_session_manager.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from orchestrator.cli_session_manager import CLISessionManager, CLISessionState

@pytest.fixture
def session_manager():
    """Create session manager for testing"""
    return CLISessionManager()

@pytest.fixture  
def mock_process():
    """Mock CLI process for testing"""
    process = MagicMock()
    process.pid = 12345
    process.poll.return_value = None  # Process still running
    return process

class TestCLISessionManager:
    @pytest.mark.asyncio
    async def test_create_session_success(self, session_manager):
        """Test successful session creation"""
        session_id = await session_manager.create_session(
            cli_tool="claude",
            mode="interactive", 
            cwd="/tmp",
            user_id="test_user"
        )
        
        assert session_id is not None
        assert session_id in session_manager.session_info
        
        session_info = session_manager.get_session_info(session_id)
        assert session_info.cli_tool == "claude"
        assert session_info.mode == "interactive"
        assert session_info.state == CLISessionState.INITIALIZING
    
    @pytest.mark.asyncio
    async def test_start_cli_process_success(self, session_manager, mock_process):
        """Test successful CLI process startup"""
        session_id = await session_manager.create_session("claude", "interactive")
        
        with patch('subprocess.Popen', return_value=mock_process):
            with patch('pty.openpty', return_value=(1, 2)):
                success = await session_manager.start_cli_process(session_id, full_access=True)
                
        assert success
        session_info = session_manager.get_session_info(session_id)
        assert session_info.state == CLISessionState.RUNNING
        assert session_info.pid == 12345
    
    @pytest.mark.asyncio
    async def test_send_input_to_session(self, session_manager):
        """Test sending input to CLI session"""
        session_id = await session_manager.create_session("claude", "interactive")
        
        # Mock the CLI process as running
        with patch.object(session_manager.sessions.get(session_id), 'send_input') as mock_send:
            mock_send.return_value = None
            success = await session_manager.send_input_to_session(session_id, "help")
            
        mock_send.assert_called_once_with("help")
        
    @pytest.mark.asyncio  
    async def test_session_cleanup(self, session_manager):
        """Test proper session cleanup"""
        session_id = await session_manager.create_session("claude", "interactive")
        
        # Terminate session
        success = await session_manager.terminate_session(session_id)
        assert success
        assert session_id not in session_manager.session_info
        assert session_id not in session_manager.sessions
```

### Integration Testing

Test complete CLI workflows:

```python
# tests/integration/test_cli_workflow.py
import pytest
import asyncio
import websockets
import json
from fastapi.testclient import TestClient
from orchestrator.app import app

class TestCLIWorkflow:
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    async def jwt_token(self):
        """Generate test JWT token"""
        import jwt
        import datetime
        
        payload = {
            'user_id': 'test_user',
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            'iat': datetime.datetime.utcnow(),
            'iss': 'autodev'
        }
        return jwt.encode(payload, 'test-secret', algorithm='HS256')
    
    @pytest.mark.asyncio
    async def test_complete_cli_workflow(self, client, jwt_token):
        """Test complete CLI workflow from session creation to termination"""
        
        # Step 1: Create CLI session
        response = client.post("/cli/sessions", json={
            "cli_tool": "claude",
            "mode": "interactive", 
            "full_access": False,
            "user_id": "test_user"
        })
        assert response.status_code == 201
        session_data = response.json()
        session_id = session_data["session_id"]
        
        # Step 2: Connect via WebSocket
        websocket_url = f"ws://localhost:8001/cli/session/{session_id}/ws?token={jwt_token}"
        
        async with websockets.connect(websocket_url) as websocket:
            # Step 3: Wait for connection confirmation
            message = await websocket.recv()
            data = json.loads(message)
            assert data["type"] == "status"
            assert data["data"]["connected"] is True
            
            # Step 4: Send command
            command_message = {
                "type": "command",
                "session_id": session_id,
                "data": {"command": "help"},
                "timestamp": "2025-08-27T12:00:00.000Z"
            }
            await websocket.send(json.dumps(command_message))
            
            # Step 5: Receive output
            output_received = False
            for _ in range(10):  # Wait for up to 10 messages
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(message)
                
                if data["type"] == "output":
                    assert "data" in data
                    assert "output" in data["data"]
                    output_received = True
                    break
            
            assert output_received
            
        # Step 6: Verify session status
        response = client.get(f"/cli/sessions/{session_id}")
        assert response.status_code == 200
        session_info = response.json()
        assert session_info["session_id"] == session_id
        
        # Step 7: Terminate session
        response = client.delete(f"/cli/sessions/{session_id}")
        assert response.status_code == 200
```

### Mock CLI Process for Testing

Create mock CLI processes for reliable testing:

```python
# tests/mocks/mock_cli_process.py
import asyncio
import os
import tempfile
from typing import List, Dict, Any

class MockCLIProcess:
    """Mock CLI process for testing"""
    
    def __init__(self, cli_tool: str = "claude"):
        self.cli_tool = cli_tool
        self.process = None
        self.responses = {
            "help": "Available commands: help, version, quit\n",
            "version": f"{cli_tool} CLI v1.0.0\n",
            "quit": "Goodbye!\n",
        }
        self.authentication_required = True
        self.authenticated = False
        
    async def start(self, command: List[str], env: Dict[str, str] = None):
        """Start mock process"""
        # Create temporary files to simulate PTY
        self.input_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
        self.output_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
        
        # Simulate authentication prompt
        if self.authentication_required and not self.authenticated:
            self.output_file.write(f"Please enter your {self.cli_tool.upper()} API key: ")
            self.output_file.flush()
    
    async def send_input(self, text: str):
        """Send input to mock process"""
        text = text.strip()
        
        # Handle authentication
        if self.authentication_required and not self.authenticated:
            if text.startswith(('sk-', 'api-', 'key-')):
                self.authenticated = True
                self.output_file.write("Authentication successful!\n")
                self.output_file.write(f"{self.cli_tool} is ready. Type 'help' for commands.\n")
            else:
                self.output_file.write("Invalid API key. Please try again: ")
            self.output_file.flush()
            return
            
        # Handle commands
        response = self.responses.get(text.lower(), f"Unknown command: {text}\n")
        self.output_file.write(response)
        self.output_file.flush()
        
        # Simulate process exit on quit
        if text.lower() == "quit":
            self.terminate()
    
    def read_output(self) -> str:
        """Read output from mock process"""
        self.output_file.seek(0)
        content = self.output_file.read()
        self.output_file.seek(0)
        self.output_file.truncate()
        return content
    
    def terminate(self):
        """Terminate mock process"""
        if self.input_file:
            self.input_file.close()
            os.unlink(self.input_file.name)
        if self.output_file:
            self.output_file.close()
            os.unlink(self.output_file.name)

# Integration with test framework
@pytest.fixture
def mock_cli_factory():
    """Factory for creating mock CLI processes"""
    created_mocks = []
    
    def create_mock(cli_tool: str = "claude"):
        mock = MockCLIProcess(cli_tool)
        created_mocks.append(mock)
        return mock
    
    yield create_mock
    
    # Cleanup
    for mock in created_mocks:
        mock.terminate()
```

### Debugging Tools

Development utilities for debugging CLI sessions:

```python
# orchestrator/debug_tools.py
import json
import time
from typing import Dict, Any, List
from orchestrator.cli_session_manager import get_cli_session_manager
from orchestrator.cli_websocket import get_cli_websocket_handler

class CLIDebugger:
    """Debugging utilities for CLI integration"""
    
    def __init__(self):
        self.session_manager = get_cli_session_manager()
        self.websocket_handler = get_cli_websocket_handler()
        
    def dump_session_state(self, session_id: str) -> Dict[str, Any]:
        """Dump complete session state for debugging"""
        session_info = self.session_manager.get_session_info(session_id)
        if not session_info:
            return {"error": "Session not found"}
            
        persistent_session = self.session_manager.get_persistent_session(session_id)
        session_history = self.session_manager.get_session_history(session_id, limit=50)
        
        return {
            "session_info": {
                "session_id": session_info.session_id,
                "cli_tool": session_info.cli_tool,
                "mode": session_info.mode,
                "state": session_info.state.value,
                "pid": session_info.pid,
                "created_at": session_info.created_at,
                "last_activity": session_info.last_activity,
                "current_directory": session_info.current_directory,
                "authentication_required": session_info.authentication_required,
                "command_history": session_info.command_history
            },
            "persistent_session": persistent_session.dict() if persistent_session else None,
            "recent_history": [msg.dict() for msg in session_history],
            "websocket_connections": self.websocket_handler.get_active_connections(),
            "timestamp": time.time()
        }
    
    def export_debug_data(self, session_id: str, filename: str = None):
        """Export debug data to file"""
        if not filename:
            filename = f"cli_debug_{session_id}_{int(time.time())}.json"
            
        debug_data = self.dump_session_state(session_id)
        
        with open(filename, 'w') as f:
            json.dump(debug_data, f, indent=2, default=str)
            
        print(f"Debug data exported to: {filename}")
        return filename
    
    def monitor_session_realtime(self, session_id: str, duration: int = 60):
        """Monitor session in real-time"""
        print(f"Monitoring session {session_id} for {duration} seconds...")
        start_time = time.time()
        
        while time.time() - start_time < duration:
            session_info = self.session_manager.get_session_info(session_id)
            if session_info:
                print(f"[{time.strftime('%H:%M:%S')}] State: {session_info.state.value}, "
                      f"PID: {session_info.pid}, "
                      f"Auth Required: {session_info.authentication_required}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Session not found")
                break
                
            time.sleep(5)

# CLI debugging command
def debug_cli_session(session_id: str, action: str = "dump"):
    """Command-line interface for debugging CLI sessions"""
    debugger = CLIDebugger()
    
    if action == "dump":
        data = debugger.dump_session_state(session_id)
        print(json.dumps(data, indent=2, default=str))
    elif action == "export":
        filename = debugger.export_debug_data(session_id)
        print(f"Debug data exported to {filename}")
    elif action == "monitor":
        debugger.monitor_session_realtime(session_id)
    else:
        print(f"Unknown action: {action}")
        print("Available actions: dump, export, monitor")

# Usage: python -c "from orchestrator.debug_tools import debug_cli_session; debug_cli_session('session-id', 'dump')"
```

## Performance Considerations

### Memory Management

Optimize memory usage for multiple concurrent sessions:

```python
class MemoryOptimizedSessionManager(CLISessionManager):
    """Session manager with memory optimization"""
    
    def __init__(self, max_memory_per_session: int = 50 * 1024 * 1024):  # 50MB
        super().__init__()
        self.max_memory_per_session = max_memory_per_session
        self.memory_monitor = MemoryMonitor()
        
    async def create_session(self, cli_tool: str, mode: str = "cli", cwd: str = None, user_id: str = "default") -> str:
        """Create session with memory monitoring"""
        # Check available memory before creating session
        available_memory = self.memory_monitor.get_available_memory()
        if available_memory < self.max_memory_per_session:
            # Try to cleanup inactive sessions
            await self.cleanup_inactive_sessions(max_age=1800)  # 30 minutes
            
            # Recheck memory
            available_memory = self.memory_monitor.get_available_memory()
            if available_memory < self.max_memory_per_session:
                raise RuntimeError("Insufficient memory for new CLI session")
                
        session_id = await super().create_session(cli_tool, mode, cwd, user_id)
        
        # Start memory monitoring for this session
        self.memory_monitor.start_monitoring(session_id, self.max_memory_per_session)
        
        return session_id

class MemoryMonitor:
    """Monitor memory usage for CLI sessions"""
    
    def __init__(self):
        self.session_memory = {}
        
    def start_monitoring(self, session_id: str, max_memory: int):
        """Start monitoring memory for session"""
        self.session_memory[session_id] = {
            "max_memory": max_memory,
            "current_usage": 0,
            "start_time": time.time()
        }
    
    def get_available_memory(self) -> int:
        """Get available system memory"""
        import psutil
        return psutil.virtual_memory().available
    
    def check_session_memory(self, session_id: str) -> bool:
        """Check if session is within memory limits"""
        if session_id not in self.session_memory:
            return True
            
        import psutil
        try:
            # Get memory usage for session's process
            session_info = get_cli_session_manager().get_session_info(session_id)
            if session_info and session_info.pid:
                process = psutil.Process(session_info.pid)
                memory_usage = process.memory_info().rss
                
                self.session_memory[session_id]["current_usage"] = memory_usage
                
                if memory_usage > self.session_memory[session_id]["max_memory"]:
                    logger.warning(f"Session {session_id} exceeds memory limit: {memory_usage} > {self.session_memory[session_id]['max_memory']}")
                    return False
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process might have terminated
            pass
            
        return True
```

### Connection Pool Management

Optimize WebSocket connections:

```python
class PooledWebSocketHandler(CLIWebSocketHandler):
    """WebSocket handler with connection pooling"""
    
    def __init__(self, max_connections_per_session: int = 5):
        super().__init__()
        self.max_connections_per_session = max_connections_per_session
        self.connection_pools = {}
        
    async def handle_connection(self, websocket: WebSocket, session_id: str, token: str = None):
        """Handle connection with pooling limits"""
        # Check connection limits for session
        if session_id in self.session_connections:
            active_connections = len(self.session_connections[session_id])
            if active_connections >= self.max_connections_per_session:
                await self._send_error(websocket, f"Maximum connections ({self.max_connections_per_session}) reached for session")
                await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
                return
                
        await super().handle_connection(websocket, session_id, token)
        
    def get_connection_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        pool_stats = {}
        for session_id, connection_ids in self.session_connections.items():
            pool_stats[session_id] = {
                "active_connections": len(connection_ids),
                "max_connections": self.max_connections_per_session,
                "utilization": len(connection_ids) / self.max_connections_per_session
            }
        return pool_stats
```

### Database Optimization

Optimize database performance for high-load scenarios:

```python
class OptimizedPersistenceManager(TaskPersistenceManager):
    """Persistence manager with performance optimizations"""
    
    def __init__(self, db_path: str = "database/tasks.db", redis_client=None, 
                 enable_batch_writes: bool = True, batch_size: int = 100):
        super().__init__(db_path, redis_client)
        self.enable_batch_writes = enable_batch_writes
        self.batch_size = batch_size
        self.write_batch = []
        self.batch_lock = threading.Lock()
        
        if enable_batch_writes:
            self._start_batch_writer()
    
    def _start_batch_writer(self):
        """Start background batch writer thread"""
        self.batch_writer_thread = threading.Thread(target=self._batch_writer_loop, daemon=True)
        self.batch_writer_thread.start()
    
    def _batch_writer_loop(self):
        """Background batch writer"""
        while True:
            time.sleep(1)  # Write batches every second
            if self.write_batch:
                with self.batch_lock:
                    batch_to_write = self.write_batch[:]
                    self.write_batch.clear()
                
                if batch_to_write:
                    self._execute_batch(batch_to_write)
    
    def _execute_batch(self, batch: List[Dict[str, Any]]):
        """Execute batch of database operations"""
        conn = self._get_connection()
        conn.execute("BEGIN TRANSACTION")
        
        try:
            for operation in batch:
                if operation["type"] == "task_history":
                    conn.execute(operation["sql"], operation["params"])
                elif operation["type"] == "task_output":
                    conn.execute(operation["sql"], operation["params"])
                # Add other operation types as needed
                    
            conn.execute("COMMIT")
        except Exception as e:
            conn.execute("ROLLBACK")
            logger.error(f"Batch write failed: {e}")
    
    def add_task_history_batched(self, task_id: str, state_from: Optional[TaskState],
                               state_to: TaskState, **kwargs):
        """Add task history entry to batch"""
        if not self.enable_batch_writes:
            return super().add_task_history(task_id, state_from, state_to, **kwargs)
            
        operation = {
            "type": "task_history",
            "sql": """INSERT INTO task_history (task_id, state_from, state_to, provider, model, error_message, details) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
            "params": (
                task_id,
                state_from.value if state_from else None,
                state_to.value,
                kwargs.get("provider"),
                kwargs.get("model"),
                kwargs.get("error_message"),
                json.dumps(kwargs.get("details")) if kwargs.get("details") else None
            )
        }
        
        with self.batch_lock:
            self.write_batch.append(operation)
            
            # Force write if batch is full
            if len(self.write_batch) >= self.batch_size:
                batch_to_write = self.write_batch[:]
                self.write_batch.clear()
                # Execute immediately for full batch
                self._execute_batch(batch_to_write)
```

## Contributing Guidelines

### Code Style and Standards

Follow established code style and patterns:

```python
# Required imports for type hints
from __future__ import annotations

# Standard library imports
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

# Third-party imports
from fastapi import WebSocket
from pydantic import BaseModel

# Local imports  
from orchestrator.models import TaskSpec
from orchestrator.persistence import get_persistence_manager

# Use proper type hints
async def create_session(
    cli_tool: str,
    mode: str = "cli",
    cwd: Optional[str] = None,
    user_id: str = "default"
) -> str:
    """Create CLI session with proper type annotations"""
    pass

# Use dataclasses for structured data
from dataclasses import dataclass

@dataclass
class SessionConfig:
    """Session configuration with proper documentation"""
    cli_tool: str
    mode: str
    full_access: bool = False
    timeout_minutes: int = 60
    
    def validate(self) -> bool:
        """Validate configuration parameters"""
        return self.cli_tool in ["claude", "codex", "gemini", "cursor"]
```

### Testing Requirements

All new features must include comprehensive tests:

1. **Unit Tests**: Test individual functions and classes
2. **Integration Tests**: Test component interactions
3. **End-to-End Tests**: Test complete workflows
4. **Performance Tests**: Test under load conditions

```python
# Test structure example
class TestNewFeature:
    """Test suite for new feature with proper structure"""
    
    @pytest.fixture
    def setup_test_environment(self):
        """Setup test environment"""
        # Setup code here
        yield test_data
        # Cleanup code here
    
    def test_feature_success_case(self, setup_test_environment):
        """Test successful operation"""
        # Arrange
        input_data = setup_test_environment
        
        # Act
        result = new_feature_function(input_data)
        
        # Assert
        assert result.success is True
        assert result.data is not None
    
    def test_feature_error_handling(self, setup_test_environment):
        """Test error scenarios"""
        with pytest.raises(ValueError, match="Invalid input"):
            new_feature_function(invalid_input)
    
    @pytest.mark.asyncio
    async def test_async_feature(self, setup_test_environment):
        """Test async functionality"""
        result = await async_new_feature(setup_test_environment)
        assert result is not None
```

### Documentation Standards

All public APIs must be documented:

```python
class NewCLIProvider:
    """
    New CLI provider implementation.
    
    This class provides integration with a new AI CLI tool following
    the established provider pattern.
    
    Attributes:
        provider_name: Name of the CLI provider
        default_model: Default model to use if none specified
        supported_modes: List of supported interaction modes
    
    Example:
        >>> provider = NewCLIProvider("new-tool")
        >>> session_id = await provider.create_session(mode="interactive")
        >>> await provider.send_command(session_id, "help")
    """
    
    def __init__(self, provider_name: str, default_model: Optional[str] = None):
        """
        Initialize the CLI provider.
        
        Args:
            provider_name: Name of the CLI provider tool
            default_model: Default model to use for API calls
            
        Raises:
            ValueError: If provider_name is empty or invalid
            RuntimeError: If CLI tool is not available on system
        """
        pass
    
    async def create_session(
        self,
        mode: str = "cli",
        full_access: bool = False,
        **kwargs
    ) -> str:
        """
        Create a new CLI session.
        
        Args:
            mode: Interaction mode ('cli', 'interactive', 'api')
            full_access: Whether to enable full access mode
            **kwargs: Additional provider-specific arguments
            
        Returns:
            str: Unique session identifier
            
        Raises:
            RuntimeError: If session creation fails
            ValueError: If invalid arguments provided
        """
        pass
```

### Commit Message Format

Follow conventional commit format:

```bash
# Feature commits
feat(cli): add support for new CLI provider
feat(websocket): implement message batching for better performance
feat(persistence): add custom metadata fields to task records

# Bug fix commits  
fix(session): resolve memory leak in session cleanup
fix(websocket): handle connection timeout properly
fix(auth): fix JWT token validation edge case

# Documentation commits
docs(api): update CLI integration API documentation
docs(guide): add troubleshooting section to user guide

# Test commits
test(cli): add integration tests for new provider
test(websocket): improve test coverage for error scenarios

# Refactor commits
refactor(persistence): optimize database query performance
refactor(session): simplify session state management
```

## API Reference

### REST API Endpoints

#### Session Management

**Create CLI Session**
```http
POST /cli/sessions
Content-Type: application/json

{
  "cli_tool": "claude",
  "mode": "interactive", 
  "full_access": true,
  "user_id": "user123",
  "working_directory": "/workspace",
  "metadata": {
    "project": "autodev",
    "environment": "development"
  }
}
```

**Response:**
```json
{
  "session_id": "cli-sess-uuid-here",
  "status": "created",
  "websocket_url": "ws://localhost:8001/cli/session/cli-sess-uuid-here/ws",
  "created_at": "2025-08-27T12:00:00.000Z"
}
```

**Get Session Information**
```http
GET /cli/sessions/{session_id}
```

**Response:**
```json
{
  "session_id": "cli-sess-uuid-here",
  "cli_tool": "claude",
  "mode": "interactive",
  "state": "running",
  "pid": 12345,
  "created_at": "2025-08-27T12:00:00.000Z",
  "last_activity": "2025-08-27T12:05:00.000Z",
  "current_directory": "/workspace",
  "authentication_required": false,
  "command_history": ["help", "create a Python function"],
  "metadata": {
    "project": "autodev",
    "environment": "development"
  }
}
```

**List All Sessions**
```http
GET /cli/sessions?status=active&cli_tool=claude&limit=50&offset=0
```

**Terminate Session**
```http
DELETE /cli/sessions/{session_id}
```

#### Session History and Diagnostics

**Get Session History**
```http
GET /cli/sessions/{session_id}/history?limit=100&message_type=command
```

**Get Session Diagnostics**
```http
GET /cli/sessions/{session_id}/diagnostics
```

### WebSocket API

#### Connection

**Connect to Session**
```
ws://localhost:8001/cli/session/{session_id}/ws?token={jwt_token}
```

#### Message Format

All WebSocket messages follow this structure:

```typescript
interface CLIMessage {
  type: "command" | "output" | "status" | "error" | "ping" | "pong" | "cancel" | "auth";
  session_id: string;
  data: Record<string, any>;
  timestamp: string;
  message_id?: string;
}
```

#### Message Types

**Command Message (Client → Server)**
```json
{
  "type": "command",
  "session_id": "cli-sess-uuid",
  "data": {
    "command": "Create a REST API endpoint for user authentication",
    "metadata": {
      "priority": "high",
      "timeout": 300
    }
  },
  "timestamp": "2025-08-27T12:00:00.000Z"
}
```

**Output Message (Server → Client)**
```json
{
  "type": "output",
  "session_id": "cli-sess-uuid", 
  "data": {
    "output": "I'll help you create a REST API endpoint for user authentication...",
    "output_type": "stdout",
    "timestamp": 1724756400.123
  },
  "timestamp": "2025-08-27T12:00:00.000Z",
  "message_id": "msg-uuid"
}
```

**Status Message (Server → Client)**
```json
{
  "type": "status",
  "session_id": "cli-sess-uuid",
  "data": {
    "state": "running",
    "authentication_required": false,
    "current_directory": "/workspace",
    "last_activity": 1724756400.123,
    "connected": true
  },
  "timestamp": "2025-08-27T12:00:00.000Z"
}
```

**Error Message (Server → Client)**
```json
{
  "type": "error", 
  "session_id": "cli-sess-uuid",
  "data": {
    "error": "CLI process terminated unexpectedly",
    "error_code": "PROCESS_TERMINATED",
    "recoverable": true
  },
  "timestamp": "2025-08-27T12:00:00.000Z"
}
```

---

This developer guide provides comprehensive information for extending and contributing to the AutoDev CLI Integration system. For user-focused information, refer to the User Guide documentation.