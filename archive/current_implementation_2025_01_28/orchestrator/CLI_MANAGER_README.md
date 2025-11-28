# CLI Process Manager

The CLI Process Manager is a comprehensive process lifecycle management system designed specifically for managing CLI tools like Claude, Codex, and Gemini in the um-agent-orchestration system.

## Overview

The CLI Process Manager implements Phase 1 of the CLI integration specification, providing:

- **Process Pool Management**: Configurable limits and intelligent cleanup
- **Resource Enforcement**: Memory, CPU, and file descriptor limits
- **Async Output Streaming**: Real-time process output handling
- **Process Isolation**: Sandboxing and security controls
- **Health Monitoring**: Process status and resource usage tracking
- **Session Management**: Reusable CLI sessions for improved performance

## Architecture

### Core Components

1. **CLIProcessManager**: Main process management class
2. **ProcessInfo**: Process metadata and state tracking
3. **ResourceLimits**: Resource constraint configuration
4. **ManagedCLIProvider**: Integration layer with existing providers

### Key Features

- **Maximum 20 processes** with configurable limits
- **5-minute idle timeout** with automatic cleanup
- **Resource monitoring** with psutil integration
- **Graceful shutdown** and error recovery
- **Provider-specific sessions** for performance optimization

## Usage

### Basic Usage

```python
from orchestrator.cli_manager import CLIProcessManager, ResourceLimits
from orchestrator.settings import ProviderCfg

# Create manager with custom settings
manager = CLIProcessManager(
    max_processes=10,
    idle_timeout=300,  # 5 minutes
    resource_limits=ResourceLimits(
        max_memory_mb=2048,
        max_cpu_percent=80.0
    )
)

# Start monitoring
await manager.start_monitoring()

# Spawn a process
cfg = ProviderCfg(
    mode="cli",
    binary="claude",
    args=["-p", "--output-format", "text"]
)

process_id = await manager.spawn_process(
    provider_name="claude_cli",
    cfg=cfg,
    session_mode=True  # Enable session reuse
)

# Send commands
stdout, stderr = await manager.send_command(
    process_id=process_id,
    command="Write a hello world function",
    timeout=30
)

# Clean up
await manager.shutdown()
```

### Integration with Existing Providers

```python
from providers.managed_cli_provider import get_managed_provider

provider = get_managed_provider()

# Enhanced CLI calls with process management
response = await provider.call_cli_managed(
    provider_name="claude_cli",
    prompt="Explain recursion",
    cfg=claude_config,
    session_mode=True  # Reuse sessions for performance
)
```

## Configuration

### Resource Limits

```python
ResourceLimits(
    max_memory_mb=2048,      # 2GB per process
    max_cpu_percent=80.0,    # 80% CPU usage limit
    max_file_descriptors=1024,
    max_execution_time=300   # 5 minutes
)
```

### Provider Configuration

The CLI Manager works with existing ProviderCfg settings:

```yaml
# config/config.yaml
providers:
  claude_cli:
    mode: "cli"
    binary: "claude"
    args: ["-p", "--output-format", "text"]
    
  claude_interactive:
    mode: "interactive"
    binary: "claude"
    args: ["--dangerously-skip-permissions"]
    
  codex_cli:
    mode: "cli"
    binary: "codex"
    args: ["exec"]
```

## API Reference

### CLIProcessManager

#### Methods

- `spawn_process(provider_name, cfg, cwd=None, session_mode=False)`: Spawn new CLI process
- `send_command(process_id, command, timeout=None)`: Send command to process
- `terminate_process(process_id, force=False)`: Terminate specific process
- `get_process(process_id)`: Get process information
- `list_processes(provider_name=None)`: List managed processes
- `health_check(process_id=None)`: Get health status
- `shutdown(timeout=30)`: Graceful shutdown

#### Configuration

- `max_processes`: Maximum concurrent processes (default: 20)
- `idle_timeout`: Process idle timeout in seconds (default: 300)
- `resource_limits`: ResourceLimits instance
- `enable_monitoring`: Enable background monitoring (default: True)

### ProcessInfo

Process metadata and state tracking:

```python
@dataclass
class ProcessInfo:
    id: str
    provider_name: str
    binary: str
    args: List[str]
    process: Optional[subprocess.Popen] = None
    created_at: float
    last_accessed: float
    cwd: Optional[str] = None
    session_mode: bool = False
    
    # Properties
    is_alive: bool
    idle_time: float
```

## Error Handling

The CLI Manager provides comprehensive error handling:

- **ProcessLimitError**: Raised when process limit exceeded
- **ProcessTimeoutError**: Raised on command timeout
- **ProcessPoolError**: General process management errors
- **ResourceLimitError**: Resource constraint violations

```python
try:
    process_id = await manager.spawn_process("claude_cli", cfg)
except ProcessLimitError:
    # Handle process limit exceeded
    await manager._cleanup_idle_processes()
    # Retry...
except ProcessPoolError as e:
    # Handle other process errors
    logger.error(f"Process management error: {e}")
```

## Monitoring and Health Checks

### Health Check Response

```python
{
    "total_processes": 3,
    "alive_processes": 3,
    "dead_processes": 0,
    "processes": [
        {
            "id": "uuid-1234",
            "provider": "claude_cli",
            "alive": True,
            "idle_time": 45.2,
            "session_mode": True,
            "resource_usage": {
                "memory_mb": 256.5,
                "cpu_percent": 15.2,
                "num_fds": 12
            }
        }
    ]
}
```

### Resource Monitoring

The manager continuously monitors:
- Memory usage per process
- CPU utilization
- File descriptor counts
- Process health status
- Idle time tracking

## Integration Examples

### Session Reuse for Performance

```python
# Multiple calls reuse the same session
provider = get_managed_provider()

for prompt in prompts:
    response = await provider.call_cli_managed(
        provider_name="claude_cli",
        prompt=prompt,
        cfg=cfg,
        session_mode=True  # Reuses existing session
    )
```

### Provider Cleanup

```python
# Clean up specific provider sessions
count = await provider.cleanup_provider("claude_cli")
print(f"Cleaned up {count} Claude processes")

# Get session information
sessions = provider.get_session_info()
for provider_name, info in sessions.items():
    print(f"{provider_name}: {info['alive']}, idle: {info['idle_time']:.1f}s")
```

## Testing

The CLI Manager includes comprehensive tests:

```bash
# Run unit tests (requires pytest)
python -m pytest tests/unit/test_cli_manager.py -v

# Run integration examples
python examples/cli_manager_integration.py
```

## Security Considerations

1. **Process Isolation**: Each CLI process runs in isolation
2. **Resource Limits**: Enforced memory, CPU, and file descriptor limits
3. **Timeout Protection**: Prevents runaway processes
4. **Graceful Shutdown**: Clean process termination
5. **Error Isolation**: Process failures don't affect other processes

## Performance Optimizations

1. **Session Reuse**: Interactive sessions reduce startup overhead
2. **Process Pooling**: Efficient resource utilization
3. **Idle Cleanup**: Automatic cleanup of unused processes
4. **Async Operations**: Non-blocking process management
5. **Resource Monitoring**: Proactive resource management

## Dependencies

Core dependencies:
- `asyncio`: Async process management
- `subprocess`: Process execution
- `psutil`: Resource monitoring
- `threading`: Concurrency control

Optional:
- `logging`: Comprehensive logging
- `uuid`: Process ID generation

## Migration Guide

To migrate from direct CLI calls to managed processes:

1. **Replace direct subprocess calls**:
   ```python
   # Before
   proc = subprocess.run(["claude", "-p", prompt])
   
   # After  
   stdout, stderr = await manager.send_command(process_id, prompt)
   ```

2. **Use the managed provider wrapper**:
   ```python
   from providers.managed_cli_provider import call_claude_cli_managed
   
   response = await call_claude_cli_managed(prompt, cfg, session_mode=True)
   ```

3. **Update configuration** to use managed providers in the router.

## Future Enhancements

Planned improvements:
- Process affinity control
- Container-based isolation
- Advanced scheduling algorithms
- Distributed process management
- Enhanced security sandboxing

## Troubleshooting

Common issues and solutions:

1. **Process limit exceeded**: Increase `max_processes` or reduce `idle_timeout`
2. **Memory issues**: Adjust `max_memory_mb` in ResourceLimits
3. **Hanging processes**: Check timeout settings and process termination
4. **Permission errors**: Verify CLI tool permissions and paths

For detailed troubleshooting, check the logs and health status endpoints.