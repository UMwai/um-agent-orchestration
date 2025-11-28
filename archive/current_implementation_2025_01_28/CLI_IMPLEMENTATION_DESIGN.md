# CLI Implementation Design: Process Management & Real-Time Streaming

## 1. CLI Session Manager Implementation

### Core Session Manager Class
```python
# orchestrator/cli_manager.py
import asyncio
import subprocess
import time
import uuid
import weakref
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, AsyncIterator, List
from dataclasses import dataclass
import psutil
import signal
import os
import threading
from queue import Queue, Empty

class CLISessionStatus(Enum):
    STARTING = "starting"
    ACTIVE = "active"
    IDLE = "idle"
    TERMINATED = "terminated"
    ERROR = "error"

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
    command_queue: Queue
    output_queue: Queue
    error_queue: Queue
    stdout_thread: threading.Thread
    stderr_thread: threading.Thread

class CLISessionManager:
    def __init__(self):
        self.sessions: Dict[str, CLISession] = {}
        self.max_sessions = 10  # Configurable limit
        self.session_timeout = timedelta(hours=2)  # Auto-cleanup timeout
        self.cleanup_interval = 300  # 5 minutes
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background task for session cleanup"""
        loop = asyncio.get_event_loop()
        self._cleanup_task = loop.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Periodically clean up stale sessions"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_stale_sessions()
            except Exception as e:
                print(f"Error in periodic cleanup: {e}")
    
    async def spawn_cli_session(
        self, 
        provider: str, 
        working_directory: Optional[str] = None,
        environment_vars: Optional[Dict[str, str]] = None
    ) -> CLISession:
        """Spawn a new CLI session with the specified provider"""
        
        # Check session limits
        if len(self.sessions) >= self.max_sessions:
            # Try to clean up first
            await self.cleanup_stale_sessions()
            if len(self.sessions) >= self.max_sessions:
                raise RuntimeError("Maximum CLI sessions reached")
        
        session_id = str(uuid.uuid4())
        working_dir = working_directory or os.getcwd()
        env_vars = environment_vars or {}
        
        try:
            # Get provider configuration
            from orchestrator.settings import load_settings
            settings = load_settings()
            
            if provider not in settings.providers:
                raise ValueError(f"Provider '{provider}' not found in configuration")
            
            provider_config = settings.providers[provider]
            
            # Build command for the CLI
            command = self._build_cli_command(provider, provider_config)
            
            # Prepare environment
            env = os.environ.copy()
            env.update(env_vars)
            
            # Start the process
            process = subprocess.Popen(
                command,
                cwd=working_dir,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            # Create queues for communication
            command_queue = Queue()
            output_queue = Queue()
            error_queue = Queue()
            
            # Start threads for handling I/O
            stdout_thread = threading.Thread(
                target=self._read_stdout,
                args=(process.stdout, output_queue),
                daemon=True
            )
            stderr_thread = threading.Thread(
                target=self._read_stderr,
                args=(process.stderr, error_queue),
                daemon=True
            )
            
            stdout_thread.start()
            stderr_thread.start()
            
            # Create session object
            session = CLISession(
                session_id=session_id,
                provider=provider,
                process=process,
                created_at=datetime.now(),
                last_activity=datetime.now(),
                status=CLISessionStatus.STARTING,
                working_directory=working_dir,
                environment_vars=env_vars,
                command_queue=command_queue,
                output_queue=output_queue,
                error_queue=error_queue,
                stdout_thread=stdout_thread,
                stderr_thread=stderr_thread
            )
            
            self.sessions[session_id] = session
            
            # Wait a moment for process to initialize
            await asyncio.sleep(0.5)
            
            # Check if process started successfully
            if process.poll() is not None:
                session.status = CLISessionStatus.ERROR
                raise RuntimeError(f"CLI process failed to start: {process.returncode}")
            
            session.status = CLISessionStatus.ACTIVE
            
            return session
            
        except Exception as e:
            # Cleanup on failure
            if 'process' in locals() and process.poll() is None:
                process.terminate()
            raise RuntimeError(f"Failed to spawn CLI session: {e}")
    
    def _build_cli_command(self, provider: str, config) -> List[str]:
        """Build the appropriate CLI command for the provider"""
        binary = config.binary
        if not binary:
            raise ValueError(f"No binary specified for provider '{provider}'")
        
        command = [binary]
        
        # Add provider-specific arguments for interactive mode
        if provider == "claude_cli":
            command.extend(["--interactive", "--output-format", "text"])
        elif provider == "claude_interactive":
            command.extend(["--dangerously-skip-permissions", "--interactive"])
        elif provider == "codex_cli":
            command.extend(["--interactive-mode"])
        elif provider == "codex_interactive":
            command.extend([
                "--ask-for-approval", "never",
                "--sandbox", "danger-full-access",
                "--interactive-mode"
            ])
        elif provider == "gemini_cli":
            command.extend(["--interactive-mode"])
        elif provider == "cursor_cli":
            command.extend(["--interactive", "--output-format", "text"])
        else:
            # Use configured args if available
            if config.args:
                command.extend(config.args)
        
        return command
    
    def _read_stdout(self, stdout, output_queue: Queue):
        """Read stdout from CLI process and put in queue"""
        try:
            for line in iter(stdout.readline, ''):
                if line:
                    output_queue.put(('stdout', line.rstrip()))
        except Exception as e:
            output_queue.put(('error', f"Stdout reader error: {e}"))
        finally:
            stdout.close()
    
    def _read_stderr(self, stderr, error_queue: Queue):
        """Read stderr from CLI process and put in queue"""
        try:
            for line in iter(stderr.readline, ''):
                if line:
                    error_queue.put(('stderr', line.rstrip()))
        except Exception as e:
            error_queue.put(('error', f"Stderr reader error: {e}"))
        finally:
            stderr.close()
    
    async def send_command(self, session_id: str, command: str) -> bool:
        """Send a command to the CLI session"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if session.status not in [CLISessionStatus.ACTIVE, CLISessionStatus.IDLE]:
            raise RuntimeError(f"Session {session_id} is not active")
        
        try:
            # Send command to process stdin
            session.process.stdin.write(command + '\n')
            session.process.stdin.flush()
            
            # Update session activity
            session.last_activity = datetime.now()
            session.status = CLISessionStatus.ACTIVE
            
            return True
            
        except Exception as e:
            session.status = CLISessionStatus.ERROR
            raise RuntimeError(f"Failed to send command to session {session_id}: {e}")
    
    async def read_output(self, session_id: str, timeout: float = 1.0) -> List[tuple]:
        """Read available output from CLI session"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        outputs = []
        start_time = time.time()
        
        # Read from output queue
        while time.time() - start_time < timeout:
            try:
                output = session.output_queue.get_nowait()
                outputs.append(output)
            except Empty:
                # No output available, short sleep and try again
                await asyncio.sleep(0.1)
                continue
        
        # Read from error queue
        try:
            while True:
                error = session.error_queue.get_nowait()
                outputs.append(error)
        except Empty:
            pass
        
        return outputs
    
    async def stream_output(self, session_id: str) -> AsyncIterator[tuple]:
        """Stream output from CLI session in real-time"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        while session.status in [CLISessionStatus.ACTIVE, CLISessionStatus.IDLE]:
            try:
                # Try to get output from queue
                try:
                    output = session.output_queue.get_nowait()
                    yield output
                except Empty:
                    pass
                
                # Try to get error from queue  
                try:
                    error = session.error_queue.get_nowait()
                    yield error
                except Empty:
                    pass
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
                
                # Check if process is still alive
                if session.process.poll() is not None:
                    session.status = CLISessionStatus.TERMINATED
                    break
                    
            except Exception as e:
                yield ('error', f"Stream error: {e}")
                break
    
    async def terminate_session(self, session_id: str) -> bool:
        """Terminate a CLI session and cleanup resources"""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        try:
            # Terminate the process gracefully
            if session.process.poll() is None:
                session.process.terminate()
                
                # Wait for graceful termination
                try:
                    session.process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    # Force kill if needed
                    session.process.kill()
                    session.process.wait()
            
            # Wait for I/O threads to finish
            if session.stdout_thread.is_alive():
                session.stdout_thread.join(timeout=2.0)
            if session.stderr_thread.is_alive():
                session.stderr_thread.join(timeout=2.0)
            
            # Update status
            session.status = CLISessionStatus.TERMINATED
            
            # Remove from active sessions
            del self.sessions[session_id]
            
            return True
            
        except Exception as e:
            print(f"Error terminating session {session_id}: {e}")
            return False
    
    async def cleanup_stale_sessions(self) -> int:
        """Clean up stale/inactive sessions"""
        cleaned_count = 0
        current_time = datetime.now()
        stale_sessions = []
        
        for session_id, session in self.sessions.items():
            # Check if session is stale
            if (current_time - session.last_activity > self.session_timeout or
                session.status == CLISessionStatus.ERROR or
                session.process.poll() is not None):
                stale_sessions.append(session_id)
        
        # Terminate stale sessions
        for session_id in stale_sessions:
            if await self.terminate_session(session_id):
                cleaned_count += 1
        
        return cleaned_count
    
    def get_session_status(self, session_id: str) -> Optional[dict]:
        """Get status information for a session"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # Get process resource usage if available
        resource_info = {}
        try:
            process = psutil.Process(session.process.pid)
            resource_info = {
                "memory_mb": process.memory_info().rss / (1024 * 1024),
                "cpu_percent": process.cpu_percent(),
                "create_time": datetime.fromtimestamp(process.create_time()),
                "num_threads": process.num_threads()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        return {
            "session_id": session.session_id,
            "provider": session.provider,
            "status": session.status.value,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "working_directory": session.working_directory,
            "process_id": session.process.pid,
            "resource_usage": resource_info
        }
    
    def list_sessions(self) -> List[dict]:
        """List all active sessions with their status"""
        return [
            self.get_session_status(session_id) 
            for session_id in self.sessions.keys()
        ]

# Global session manager instance
_session_manager: Optional[CLISessionManager] = None

def get_cli_session_manager() -> CLISessionManager:
    """Get or create the global CLI session manager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = CLISessionManager()
    return _session_manager
```

## 2. WebSocket CLI Bridge Implementation

```python
# orchestrator/websocket_cli.py
import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from orchestrator.cli_manager import get_cli_session_manager, CLISessionStatus

class CLIWebSocketHandler:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.websocket_sessions: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Connect WebSocket to CLI session"""
        await websocket.accept()
        
        # Add to active connections
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        self.active_connections[session_id].add(websocket)
        self.websocket_sessions[websocket] = session_id
        
        # Start output streaming for this connection
        asyncio.create_task(self.stream_cli_output(session_id, websocket))
    
    async def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        session_id = self.websocket_sessions.get(websocket)
        if session_id:
            # Remove from active connections
            if session_id in self.active_connections:
                self.active_connections[session_id].discard(websocket)
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]
            del self.websocket_sessions[websocket]
    
    async def handle_cli_message(self, websocket: WebSocket, message: dict):
        """Handle incoming WebSocket message for CLI"""
        session_id = self.websocket_sessions.get(websocket)
        if not session_id:
            await websocket.send_text(json.dumps({
                "type": "error",
                "content": "No session associated with WebSocket"
            }))
            return
        
        message_type = message.get("type")
        content = message.get("content", "")
        
        session_manager = get_cli_session_manager()
        
        try:
            if message_type == "command":
                # Send command to CLI session
                success = await session_manager.send_command(session_id, content)
                if success:
                    # Echo the command back to show it was sent
                    await websocket.send_text(json.dumps({
                        "type": "echo",
                        "content": f"$ {content}"
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error", 
                        "content": "Failed to send command to CLI"
                    }))
            
            elif message_type == "interrupt":
                # Send interrupt signal to CLI process
                session = session_manager.sessions.get(session_id)
                if session and session.process.poll() is None:
                    session.process.send_signal(signal.SIGINT)
                    await websocket.send_text(json.dumps({
                        "type": "system",
                        "content": "Interrupt signal sent"
                    }))
            
            elif message_type == "status":
                # Get session status
                status = session_manager.get_session_status(session_id)
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "content": status
                }))
            
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "content": f"Error handling message: {e}"
            }))
    
    async def stream_cli_output(self, session_id: str, websocket: WebSocket):
        """Stream CLI output to WebSocket client"""
        session_manager = get_cli_session_manager()
        
        try:
            async for output_type, content in session_manager.stream_output(session_id):
                if websocket in self.websocket_sessions:
                    await websocket.send_text(json.dumps({
                        "type": output_type,
                        "content": content,
                        "timestamp": datetime.now().isoformat()
                    }))
                else:
                    # WebSocket disconnected, stop streaming
                    break
        except Exception as e:
            if websocket in self.websocket_sessions:
                try:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "content": f"Output stream error: {e}"
                    }))
                except:
                    pass  # WebSocket might be closed
    
    async def broadcast_to_session(self, session_id: str, message: dict):
        """Broadcast message to all WebSockets connected to a session"""
        if session_id in self.active_connections:
            disconnected = []
            for websocket in self.active_connections[session_id].copy():
                try:
                    await websocket.send_text(json.dumps(message))
                except:
                    disconnected.append(websocket)
            
            # Clean up disconnected WebSockets
            for websocket in disconnected:
                await self.disconnect(websocket)

# Global WebSocket handler instance
_websocket_handler: Optional[CLIWebSocketHandler] = None

def get_cli_websocket_handler() -> CLIWebSocketHandler:
    """Get or create the global CLI WebSocket handler"""
    global _websocket_handler
    if _websocket_handler is None:
        _websocket_handler = CLIWebSocketHandler()
    return _websocket_handler
```

This implementation provides:

1. **Robust Process Management**: Full lifecycle management of CLI processes
2. **Real-Time I/O**: Threaded I/O handling with queues for non-blocking communication  
3. **Resource Monitoring**: Process resource tracking and cleanup
4. **Session Persistence**: Long-running sessions with proper state management
5. **WebSocket Integration**: Real-time bidirectional communication
6. **Error Handling**: Comprehensive error recovery and cleanup
7. **Scalability**: Session limits and automatic cleanup

The next step would be to integrate these components with the FastAPI app and update the dashboard frontend to use real CLI sessions instead of the simulated interface.