# AutoDev CLI Integration User Guide

**Version:** 1.0  
**Date:** August 27, 2025  
**Audience:** End Users, System Administrators  

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Authentication and Security](#authentication-and-security)
4. [Using the CLI Integration](#using-the-cli-integration)
5. [WebSocket Connection Management](#websocket-connection-management)
6. [Task Management with CLI Sessions](#task-management-with-cli-sessions)
7. [Troubleshooting](#troubleshooting)
8. [Performance Optimization](#performance-optimization)
9. [FAQ](#frequently-asked-questions)

## Introduction

The AutoDev CLI Integration provides real-time interaction with AI-powered CLI tools including Claude, Codex, Gemini, and Cursor. This system transforms the AutoDev orchestrator from a mock CLI environment to a production-ready platform capable of managing actual CLI processes with full terminal interaction capabilities.

### Key Features

- **Real-time CLI Interaction**: Direct terminal-style interaction with AI CLI tools
- **WebSocket Streaming**: Live output streaming and bidirectional communication
- **Session Persistence**: Complete session history and recovery capabilities
- **Multi-Provider Support**: Unified interface for multiple AI CLI providers
- **Authentication Security**: JWT-based authentication for secure access
- **Full Access Modes**: Support for unrestricted CLI operations when needed

## Getting Started

### Prerequisites

Before using the CLI integration, ensure you have:

1. **CLI Binaries Installed**: Required AI CLI tools installed on your system
2. **API Keys Configured**: Valid API keys for your chosen AI providers  
3. **System Access**: Proper system permissions for process management
4. **Network Access**: Available network connectivity for WebSocket connections

### Quick Start Guide

#### Step 1: Verify CLI Tools Installation

Run the verification script to check if CLI tools are properly installed:

```bash
# Check if CLI tools are available
which claude codex gemini cursor-agent

# Verify CLI tools can run
claude --version
codex --version  
gemini --version
cursor-agent --version
```

#### Step 2: Configure API Keys

Set up your API keys in the environment:

```bash
# Copy environment template
cp .env.example .env

# Edit configuration file
nano .env

# Add your API keys:
ANTHROPIC_API_KEY=sk-ant-api03-your-claude-key-here
OPENAI_API_KEY=sk-your-openai-key-here  
GOOGLE_API_KEY=your-google-api-key-here
JWT_SECRET=your-secure-256-bit-secret-key
```

#### Step 3: Start the System

```bash
# Start Redis (if not already running)
redis-server &

# Start AutoDev with CLI integration
make dev

# Or start manually:
uvicorn orchestrator.app:app --host 0.0.0.0 --port 8001 --reload
```

#### Step 4: Verify System Status

Check that all components are working:

```bash
# Check system status
curl http://localhost:8001/health

# Verify CLI provider status  
curl http://localhost:8001/providers

# Check WebSocket endpoint
curl http://localhost:8001/metrics
```

## Authentication and Security

### JWT Token Authentication

The CLI integration uses JWT tokens for secure WebSocket authentication.

#### Obtaining a JWT Token

For development and testing, you can generate a test token:

```python
import jwt
import datetime

# Create payload
payload = {
    'user_id': 'your_user_id',
    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),
    'iat': datetime.datetime.utcnow(),
    'iss': 'autodev'
}

# Generate token (use your actual JWT_SECRET)
token = jwt.encode(payload, 'your_jwt_secret_here', algorithm='HS256')
print(f"Your JWT token: {token}")
```

#### Using JWT Tokens in WebSocket Connections

```javascript
// JavaScript example for WebSocket connection with JWT
const token = "your_jwt_token_here";
const sessionId = "your_session_id";
const wsUrl = `ws://localhost:8001/cli/session/${sessionId}/ws?token=${token}`;

const websocket = new WebSocket(wsUrl);

websocket.onopen = function(event) {
    console.log("Connected to CLI session");
};

websocket.onmessage = function(event) {
    const message = JSON.parse(event.data);
    console.log("Received:", message);
};
```

### Security Best Practices

1. **Secure JWT Secrets**: Use strong, randomly generated JWT secrets
2. **Token Expiration**: Configure appropriate token expiration times
3. **HTTPS in Production**: Always use HTTPS/WSS in production environments
4. **API Key Protection**: Securely store and manage API keys
5. **Network Isolation**: Limit network access to CLI integration endpoints

## Using the CLI Integration

### Creating CLI Sessions

#### Method 1: Through REST API

Create a new CLI session via HTTP POST:

```bash
# Create a Claude CLI session
curl -X POST http://localhost:8001/cli/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "cli_tool": "claude",
    "mode": "interactive",
    "full_access": true,
    "user_id": "your_user_id"
  }'

# Response includes session_id for WebSocket connection
{
  "session_id": "cli-session-uuid-here",
  "status": "created",
  "websocket_url": "ws://localhost:8001/cli/session/cli-session-uuid-here/ws"
}
```

#### Method 2: Through Task Submission

Create a CLI session automatically when submitting a task:

```bash
curl -X POST http://localhost:8001/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my-task-123",
    "title": "Implement new feature",
    "description": "Add user authentication to the web app",
    "role": "backend",
    "provider_override": "claude",
    "full_access": true
  }'
```

### Connecting to CLI Sessions

#### WebSocket Connection

Once you have a session ID and JWT token, connect via WebSocket:

```javascript
// Complete WebSocket connection example
class CLISessionClient {
    constructor(sessionId, token) {
        this.sessionId = sessionId;
        this.token = token;
        this.websocket = null;
        this.messageQueue = [];
    }
    
    connect() {
        const wsUrl = `ws://localhost:8001/cli/session/${this.sessionId}/ws?token=${this.token}`;
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = (event) => {
            console.log(`Connected to CLI session: ${this.sessionId}`);
            this.flushMessageQueue();
        };
        
        this.websocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };
        
        this.websocket.onclose = (event) => {
            console.log(`CLI session disconnected: ${event.code} - ${event.reason}`);
        };
        
        this.websocket.onerror = (error) => {
            console.error(`WebSocket error:`, error);
        };
    }
    
    handleMessage(message) {
        switch(message.type) {
            case 'output':
                this.displayOutput(message.data.output, message.data.output_type);
                break;
            case 'status':
                this.updateStatus(message.data);
                break;
            case 'error':
                this.displayError(message.data.error);
                break;
            case 'pong':
                console.log('Received heartbeat response');
                break;
        }
    }
    
    sendCommand(command) {
        const message = {
            type: 'command',
            session_id: this.sessionId,
            data: { command: command },
            timestamp: new Date().toISOString()
        };
        
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(message));
        } else {
            this.messageQueue.push(message);
        }
    }
    
    displayOutput(output, outputType) {
        const outputElement = document.getElementById('cli-output');
        const outputLine = document.createElement('div');
        outputLine.className = `output-${outputType}`;
        outputLine.textContent = output;
        outputElement.appendChild(outputLine);
        outputElement.scrollTop = outputElement.scrollHeight;
    }
    
    updateStatus(status) {
        console.log('Status update:', status);
        if (status.authentication_required) {
            this.promptForAuthentication(status.auth_prompt);
        }
    }
    
    promptForAuthentication(prompt) {
        const apiKey = window.prompt(prompt || "Please enter your API key:");
        if (apiKey) {
            this.sendCommand(apiKey);
        }
    }
}

// Usage
const client = new CLISessionClient('your-session-id', 'your-jwt-token');
client.connect();

// Send commands
client.sendCommand('Help me implement a REST API');
```

### WebSocket Message Protocol

#### Message Types

The CLI integration uses structured messages for communication:

```json
{
  "type": "command|output|status|error|ping|pong|cancel|auth",
  "session_id": "session-uuid",
  "data": {
    // Type-specific data
  },
  "timestamp": "2025-08-27T12:00:00.000Z",
  "message_id": "message-uuid"
}
```

#### Command Messages

Send commands to the CLI process:

```json
{
  "type": "command",
  "session_id": "cli-session-123",
  "data": {
    "command": "Implement user authentication in Python Flask"
  },
  "timestamp": "2025-08-27T12:00:00.000Z"
}
```

#### Output Messages

Receive CLI output in real-time:

```json
{
  "type": "output", 
  "session_id": "cli-session-123",
  "data": {
    "output": "I'll help you implement user authentication...",
    "output_type": "stdout",
    "timestamp": 1724756400.123
  },
  "timestamp": "2025-08-27T12:00:00.000Z"
}
```

#### Status Messages

Monitor session status and state changes:

```json
{
  "type": "status",
  "session_id": "cli-session-123", 
  "data": {
    "session_id": "cli-session-123",
    "cli_tool": "claude",
    "mode": "interactive",
    "state": "running",
    "authentication_required": false,
    "pid": 12345,
    "current_directory": "/workspace",
    "last_activity": 1724756400.123
  },
  "timestamp": "2025-08-27T12:00:00.000Z"
}
```

## WebSocket Connection Management

### Connection States

CLI WebSocket connections progress through several states:

1. **Connecting**: Initial WebSocket connection establishment
2. **Connected**: WebSocket connected, authentication pending
3. **Authenticated**: JWT token validated, ready for commands
4. **Disconnected**: Connection closed or lost

### Heartbeat and Keep-Alive

The system automatically manages connection health:

- **Heartbeat Interval**: 30 seconds (configurable)
- **Timeout Detection**: Automatic ping when inactive > 60 seconds  
- **Automatic Reconnection**: Client should implement reconnection logic

#### Implementing Reconnection

```javascript
class ReconnectingCLIClient extends CLISessionClient {
    constructor(sessionId, token, options = {}) {
        super(sessionId, token);
        this.reconnectInterval = options.reconnectInterval || 5000;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
        this.reconnectAttempts = 0;
        this.shouldReconnect = true;
    }
    
    connect() {
        super.connect();
        
        this.websocket.onclose = (event) => {
            console.log(`Connection closed: ${event.code}`);
            if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.attemptReconnect();
            }
        };
    }
    
    attemptReconnect() {
        this.reconnectAttempts++;
        console.log(`Reconnection attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
        
        setTimeout(() => {
            this.connect();
        }, this.reconnectInterval * this.reconnectAttempts);
    }
    
    disconnect() {
        this.shouldReconnect = false;
        if (this.websocket) {
            this.websocket.close();
        }
    }
}
```

### Error Handling

Common WebSocket errors and handling strategies:

#### Authentication Errors

```javascript
// Handle authentication failures
websocket.onclose = function(event) {
    if (event.code === 1008) { // Policy Violation
        console.error("Authentication failed - invalid or expired token");
        // Refresh token and reconnect
        refreshJWTToken().then(newToken => {
            client = new CLISessionClient(sessionId, newToken);
            client.connect();
        });
    }
};
```

#### Network Errors

```javascript
// Handle network connectivity issues
websocket.onerror = function(error) {
    console.error("WebSocket error:", error);
    // Implement exponential backoff for reconnection
    setTimeout(() => {
        if (websocket.readyState !== WebSocket.OPEN) {
            attemptReconnect();
        }
    }, Math.min(30000, 1000 * Math.pow(2, reconnectAttempts)));
};
```

## Task Management with CLI Sessions

### Associating Tasks with CLI Sessions

CLI sessions can be associated with specific tasks for better organization:

```bash
# Create task with CLI session
curl -X POST http://localhost:8001/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "id": "feature-auth-123",
    "title": "Implement User Authentication",
    "description": "Add JWT-based authentication to the API",
    "role": "backend", 
    "provider_override": "claude",
    "full_access": true,
    "acceptance": {
      "tests_pass": true,
      "security_review": true,
      "documentation_updated": true
    }
  }'
```

### Monitoring Task Progress

Track task progress through CLI sessions:

```bash
# Get task status
curl http://localhost:8001/tasks/feature-auth-123

# Get CLI session associated with task
curl http://localhost:8001/cli/sessions/by-task/feature-auth-123

# Get session history
curl http://localhost:8001/cli/sessions/cli-session-123/history
```

### CLI Session Recovery

The system automatically recovers CLI sessions after restarts:

```bash
# Check recovered sessions after system restart
curl http://localhost:8001/cli/sessions/recovery/status

# Get list of recovered sessions
curl http://localhost:8001/cli/sessions?status=recovered
```

## Troubleshooting

### Common Issues and Solutions

#### 1. WebSocket Connection Failures

**Symptoms**: Cannot establish WebSocket connection, immediate disconnection

**Solutions**:
- Verify JWT token is valid and not expired
- Check network connectivity to the AutoDev server
- Ensure WebSocket endpoint is accessible (firewall, proxy settings)
- Verify session ID exists and is valid

```bash
# Test WebSocket endpoint accessibility
curl -I http://localhost:8001/cli/session/test/ws
# Should return: 426 Upgrade Required (expected for WebSocket endpoint)

# Check if session exists  
curl http://localhost:8001/cli/sessions/your-session-id
```

#### 2. CLI Authentication Issues

**Symptoms**: CLI process stuck in "waiting_input" state, authentication prompts

**Solutions**:
- Verify API keys are set correctly in environment variables
- Check CLI tool can authenticate independently
- Ensure API keys have appropriate permissions

```bash
# Test CLI authentication independently
claude auth status
codex auth status
gemini auth login --check

# Verify environment variables
echo $ANTHROPIC_API_KEY | cut -c1-8  # Should show first 8 characters
echo $OPENAI_API_KEY | cut -c1-8
echo $GOOGLE_API_KEY | cut -c1-8
```

#### 3. Process Startup Failures

**Symptoms**: CLI sessions fail to start, "error" state immediately

**Solutions**:
- Verify CLI binaries are installed and accessible
- Check system permissions for process spawning
- Ensure working directory is accessible

```bash
# Check CLI binary availability
which claude codex gemini cursor-agent

# Test CLI binary execution
claude --help
codex --help

# Check working directory permissions
ls -la /path/to/working/directory
```

#### 4. Performance Issues

**Symptoms**: Slow responses, high memory usage, connection timeouts

**Solutions**:
- Monitor system resources (CPU, memory, network)
- Adjust connection limits and timeouts
- Check Redis performance and connectivity

```bash
# Monitor system resources
htop
# Or
top -p $(pgrep -f autodev)

# Check Redis performance
redis-cli --latency-history -h localhost -p 6379

# Monitor WebSocket connections
curl http://localhost:8001/metrics | grep websocket
```

### Debugging CLI Sessions

#### Enable Debug Logging

```bash
# Start with debug logging enabled
DEBUG=true LOG_LEVEL=DEBUG python -m orchestrator.app

# Or set environment variable
export DEBUG=true
export LOG_LEVEL=DEBUG
make dev
```

#### CLI Session Diagnostics

```bash
# Get detailed session information
curl http://localhost:8001/cli/sessions/your-session-id/diagnostics

# Get session command history
curl http://localhost:8001/cli/sessions/your-session-id/history

# Check session process status
curl http://localhost:8001/cli/sessions/your-session-id/process
```

#### WebSocket Message Debugging

Enable WebSocket message logging in your client:

```javascript
// Debug WebSocket messages
websocket.addEventListener('message', function(event) {
    console.log('WebSocket received:', event.data);
});

websocket.addEventListener('send', function(event) {
    console.log('WebSocket sent:', event.data);
});
```

### Log Analysis

#### Common Log Patterns

**Successful Session Creation**:
```
INFO - CLI WebSocket Handler initialized
INFO - WebSocket connection established: conn-123 for session sess-456
INFO - Authentication successful for user user-789
```

**Authentication Failures**:
```
WARNING - Authentication failed for session sess-456: Invalid token
ERROR - JWT token has expired
```

**Process Issues**:
```
ERROR - Error starting CLI process: FileNotFoundError: 'claude' command not found
WARNING - CLI session sess-456 process terminated unexpectedly
```

#### Log File Locations

```bash
# Application logs
tail -f logs/autodev.log

# CLI session specific logs
tail -f logs/cli-sessions/sess-456.log

# WebSocket connection logs  
tail -f logs/websocket.log
```

## Performance Optimization

### Optimizing WebSocket Connections

#### Connection Pooling

For applications with multiple CLI sessions, implement connection pooling:

```javascript
class CLISessionPool {
    constructor(maxConnections = 10) {
        this.connections = new Map();
        this.maxConnections = maxConnections;
    }
    
    async getConnection(sessionId, token) {
        if (this.connections.has(sessionId)) {
            return this.connections.get(sessionId);
        }
        
        if (this.connections.size >= this.maxConnections) {
            // Remove oldest connection
            const oldestSession = this.connections.keys().next().value;
            await this.closeConnection(oldestSession);
        }
        
        const connection = new ReconnectingCLIClient(sessionId, token);
        await connection.connect();
        this.connections.set(sessionId, connection);
        return connection;
    }
    
    async closeConnection(sessionId) {
        const connection = this.connections.get(sessionId);
        if (connection) {
            connection.disconnect();
            this.connections.delete(sessionId);
        }
    }
}
```

#### Message Batching

Batch multiple commands for better performance:

```javascript
class BatchedCLIClient extends CLISessionClient {
    constructor(sessionId, token, batchSize = 5, batchTimeout = 1000) {
        super(sessionId, token);
        this.batchSize = batchSize;
        this.batchTimeout = batchTimeout;
        this.commandBatch = [];
        this.batchTimer = null;
    }
    
    sendCommand(command) {
        this.commandBatch.push(command);
        
        if (this.commandBatch.length >= this.batchSize) {
            this.flushBatch();
        } else if (!this.batchTimer) {
            this.batchTimer = setTimeout(() => this.flushBatch(), this.batchTimeout);
        }
    }
    
    flushBatch() {
        if (this.commandBatch.length === 0) return;
        
        const batchedCommand = this.commandBatch.join('\n');
        super.sendCommand(batchedCommand);
        
        this.commandBatch = [];
        if (this.batchTimer) {
            clearTimeout(this.batchTimer);
            this.batchTimer = null;
        }
    }
}
```

### System Resource Optimization

#### Memory Management

Monitor and optimize memory usage:

```bash
# Monitor memory usage by component
ps aux | grep autodev | awk '{print $4, $11}' | sort -nr

# Check CLI session memory usage
curl http://localhost:8001/metrics | grep memory

# Configure memory limits
export CLI_MAX_MEMORY_MB=512
export PYTHON_MAX_MEMORY_MB=2048
```

#### CPU Optimization

Optimize CPU usage for multiple concurrent sessions:

```bash
# Monitor CPU usage
htop -p $(pgrep -f autodev)

# Configure CPU limits
export CLI_MAX_CPU_PERCENT=50
export MAX_CONCURRENT_CLI_SESSIONS=25
```

#### Network Optimization

Optimize network performance:

```bash
# Configure connection limits
export MAX_WEBSOCKET_CONNECTIONS=100
export WEBSOCKET_TIMEOUT_SECONDS=300

# Monitor network usage
netstat -i
ss -tuln | grep :8000
```

## Frequently Asked Questions

### Q: Can I use multiple CLI providers simultaneously?

**A**: Yes, you can create separate CLI sessions for different providers and run them concurrently. Each session is isolated and can use a different provider (Claude, Codex, Gemini, Cursor).

```bash
# Create multiple sessions with different providers
curl -X POST http://localhost:8001/cli/sessions -d '{"cli_tool": "claude", "mode": "interactive"}'
curl -X POST http://localhost:8001/cli/sessions -d '{"cli_tool": "codex", "mode": "interactive"}'
curl -X POST http://localhost:8001/cli/sessions -d '{"cli_tool": "gemini", "mode": "interactive"}'
```

### Q: How do I handle long-running CLI operations?

**A**: The system is designed for long-running operations with:
- Session persistence across disconnections
- Message queuing during temporary network issues
- Automatic session recovery after system restarts
- Configurable timeouts for different operation types

### Q: What happens if the CLI process crashes?

**A**: The system detects process crashes and:
- Updates session state to "error"
- Sends error notifications to connected WebSocket clients
- Preserves session history and outputs in the database
- Allows for manual session recovery or restart

### Q: Can I customize CLI command execution?

**A**: Yes, you can:
- Set custom working directories for CLI sessions
- Configure environment variables per session
- Use full-access mode for unrestricted operations
- Pass custom arguments to CLI tools

### Q: How do I monitor CLI session performance?

**A**: The system provides comprehensive metrics:
- WebSocket connection metrics at `/metrics`
- CLI session statistics via REST API
- Real-time performance monitoring through dashboard
- Detailed logging with configurable verbosity levels

### Q: Is the CLI integration secure for production use?

**A**: Yes, the implementation includes:
- JWT-based authentication for WebSocket connections
- Process isolation between CLI sessions
- Secure API key handling with environment variables
- Network security with configurable CORS policies
- Session-based access control and audit logging

### Q: Can I extend the system with custom CLI tools?

**A**: Yes, the architecture supports adding custom CLI providers by:
- Creating new provider classes following the existing pattern
- Adding CLI-specific authentication detection patterns
- Configuring command-line arguments and environment variables
- Implementing provider-specific error handling

---

This user guide provides comprehensive information for effectively using the AutoDev CLI Integration system. For technical implementation details, refer to the Developer Guide documentation.