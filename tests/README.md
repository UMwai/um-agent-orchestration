# CLI Integration Test Suite

Comprehensive test suite for validating the Phase 1 CLI integration implementation. This test suite ensures the CLI integration system meets all acceptance criteria and maintains high quality, security, and performance standards.

## Overview

The test suite is organized into multiple specialized test categories:

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow validation
- **Performance Tests**: Load testing and resource validation
- **Security Tests**: Authentication and input validation security
- **Acceptance Tests**: Final acceptance criteria validation

## Test Organization

```
tests/
├── conftest.py                 # Shared pytest configuration and fixtures
├── README.md                   # This file
├── unit/                       # Unit tests
│   ├── test_cli_manager.py     # CLI process manager tests
│   └── test_cli_session_manager.py  # CLI session manager tests
├── integration/                # Integration tests  
│   └── test_cli_integration.py # End-to-end integration tests
├── performance/                # Performance tests
│   └── test_cli_load.py        # Load and performance tests
├── security/                   # Security tests
│   └── test_cli_security.py    # Security vulnerability tests
├── acceptance/                 # Acceptance tests
│   ├── test_risk.py            # Existing risk tests
│   └── test_sample.py          # Existing sample tests
└── test_cli_websocket.py       # Enhanced WebSocket tests
```

## Quick Start

### Prerequisites

1. **Python Dependencies**: Install test dependencies
   ```bash
   pip install pytest pytest-asyncio pytest-mock memory-profiler psutil
   ```

2. **Redis**: Required for persistence tests (optional for most tests)
   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server
   
   # macOS
   brew install redis
   
   # Start Redis
   redis-server
   ```

3. **Environment Variables**: Set up test environment
   ```bash
   cp .env.example .env
   # Edit .env with test values
   ```

### Running Tests

#### Using the Test Runner Script (Recommended)

```bash
# Run all tests
./scripts/run_cli_tests.py --all

# Run specific test suites
./scripts/run_cli_tests.py --unit          # Unit tests only
./scripts/run_cli_tests.py --integration   # Integration tests only
./scripts/run_cli_tests.py --performance   # Performance tests only
./scripts/run_cli_tests.py --security      # Security tests only

# Run quick smoke tests
./scripts/run_cli_tests.py --quick

# Run with verbose output
./scripts/run_cli_tests.py --all --verbose

# Skip slow tests (useful for CI)
./scripts/run_cli_tests.py --all --skip-slow

# Generate test report
./scripts/run_cli_tests.py --all --report test_results.md
```

#### Using pytest Directly

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v
pytest tests/integration/ -v -m integration
pytest tests/performance/ -v -m performance
pytest tests/security/ -v -m security

# Run tests with coverage
pytest tests/ --cov=orchestrator --cov-report=html

# Run only fast tests
pytest tests/ -m "not slow and not performance"
```

## Test Categories

### Unit Tests (`tests/unit/`)

Test individual components in isolation with comprehensive mocking.

**Coverage:**
- CLI process manager lifecycle
- Session management operations
- WebSocket handler functionality
- Authentication mechanisms
- Message validation and routing
- Error handling and edge cases

**Key Features:**
- Fast execution (< 30 seconds)
- No external dependencies
- Comprehensive mocking
- Edge case coverage

**Run:** `./scripts/run_cli_tests.py --unit`

### Integration Tests (`tests/integration/`)

Test complete end-to-end workflows and component interactions.

**Coverage:**
- Complete authentication → session → command → output → cleanup flow
- Multi-provider support (Claude, Codex, Gemini, Cursor)
- WebSocket real-time communication
- Session persistence and recovery
- Process management lifecycle
- Error handling scenarios

**Key Features:**
- Realistic workflow simulation
- Cross-component validation
- Multi-session scenarios
- Persistence testing

**Run:** `./scripts/run_cli_tests.py --integration`

### Performance Tests (`tests/performance/`)

Validate system performance under load and resource constraints.

**Target Metrics:**
- 10+ concurrent sessions
- < 500ms session creation latency
- < 100ms message processing latency
- WebSocket connection stability
- Memory usage within limits
- Efficient cleanup

**Coverage:**
- Concurrent session handling
- WebSocket connection stress testing
- Message throughput validation
- Memory usage monitoring
- Process cleanup efficiency
- End-to-end performance

**Key Features:**
- Real performance metrics collection
- Resource usage validation
- Stress testing scenarios
- Performance regression detection

**Run:** `./scripts/run_cli_tests.py --performance`

### Security Tests (`tests/security/`)

Comprehensive security vulnerability testing.

**Coverage:**
- JWT token security (tampering, expiration, algorithm confusion)
- Input validation and sanitization
- Command injection prevention
- Path traversal protection
- Authentication bypass attempts
- Session hijacking prevention
- WebSocket security vulnerabilities
- Rate limiting and DoS protection

**Key Features:**
- Real attack simulation
- Common vulnerability patterns
- Security regression prevention
- Compliance validation

**Run:** `./scripts/run_cli_tests.py --security`

## Test Configuration

### Pytest Markers

The test suite uses custom pytest markers for organization:

- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.performance`: Performance tests
- `@pytest.mark.security`: Security tests
- `@pytest.mark.slow`: Slow-running tests
- `@pytest.mark.redis`: Tests requiring Redis
- `@pytest.mark.websocket`: WebSocket-specific tests

### Environment Configuration

Tests use environment variables for configuration:

```bash
# Test Redis database (separate from production)
REDIS_URL=redis://localhost:6379/15

# API keys for CLI tool testing (use test keys)
ANTHROPIC_API_KEY=test-key
OPENAI_API_KEY=test-key
GOOGLE_API_KEY=test-key

# JWT secret for testing
JWT_SECRET=test-secret-key

# Performance test controls
RUN_PERFORMANCE_TESTS=1
SKIP_SECURITY_TESTS=0
```

### Mock Configuration

Tests extensively use mocking to:
- Avoid external service dependencies
- Control test environments
- Simulate error conditions
- Ensure test repeatability

Key mock patterns:
- Redis persistence layer
- CLI process execution
- WebSocket connections
- API service calls

## Test Data and Fixtures

### Shared Fixtures (`conftest.py`)

- `test_client`: FastAPI test client
- `redis_client`: Test Redis connection
- `mock_persistence_manager`: Mocked persistence layer
- `temp_dir`: Temporary directory for file operations
- `mock_env_vars`: Environment variable mocking
- `performance_test_config`: Performance test settings
- `security_test_config`: Security test settings

### Test Data

- Sample CLI commands for various scenarios
- WebSocket message formats
- Malicious input patterns for security testing
- Performance test configurations
- Mock authentication tokens

## Phase 1 Acceptance Criteria Validation

The test suite validates all Phase 1 acceptance criteria:

### ✅ Authentication System
- [x] JWT token-based authentication
- [x] Session-based access control
- [x] Token validation and expiration
- [x] Security vulnerability protection

### ✅ CLI Session Management
- [x] Multiple CLI tool support (Claude, Codex, Gemini, Cursor)
- [x] Interactive and non-interactive modes
- [x] Process lifecycle management
- [x] Session isolation and security

### ✅ Real-time Communication
- [x] WebSocket bidirectional communication
- [x] Real-time output streaming
- [x] Message queuing and recovery
- [x] Connection management

### ✅ Process Management
- [x] CLI process spawning and termination
- [x] PTY-based terminal interaction
- [x] Authentication state detection
- [x] Resource cleanup

### ✅ Persistence & Recovery
- [x] Redis-based session persistence
- [x] Session recovery after failures
- [x] Message history storage
- [x] Metrics collection

### ✅ Performance Requirements
- [x] 10+ concurrent sessions supported
- [x] < 500ms session creation latency
- [x] Efficient resource usage
- [x] Memory cleanup validation

### ✅ Security Requirements
- [x] Input validation and sanitization
- [x] Command injection prevention
- [x] Authentication bypass protection
- [x] Session security isolation

## CI/CD Integration

### GitHub Actions

```yaml
# Example CI configuration
- name: Run CLI Integration Tests
  run: |
    # Quick tests for PR validation
    ./scripts/run_cli_tests.py --quick
    
    # Full test suite for main branch
    if [[ "$GITHUB_REF" == "refs/heads/main" ]]; then
      export RUN_PERFORMANCE_TESTS=1
      ./scripts/run_cli_tests.py --all --report ci_results.md
    fi
```

### Test Skipping

Tests automatically skip when dependencies are unavailable:

- Redis tests skip if Redis is not running
- Performance tests skip in CI unless `RUN_PERFORMANCE_TESTS=1`
- Security tests skip if `SKIP_SECURITY_TESTS=1`

## Performance Metrics

Performance tests collect detailed metrics:

### Timing Metrics
- Mean, median, P95, P99 latency
- Operations per second
- Total execution time

### Resource Metrics
- Memory usage (RSS)
- CPU utilization
- Connection counts

### Success Metrics
- Success rate percentage
- Error counts and types
- Test coverage

## Troubleshooting

### Common Issues

1. **Redis Connection Errors**
   ```bash
   # Start Redis server
   redis-server
   
   # Check Redis is running
   redis-cli ping
   ```

2. **Permission Errors**
   ```bash
   # Make scripts executable
   chmod +x scripts/run_cli_tests.py
   ```

3. **Import Errors**
   ```bash
   # Install test dependencies
   pip install -r requirements-test.txt
   
   # Ensure project is in Python path
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

4. **WebSocket Test Failures**
   ```bash
   # Check FastAPI dependencies
   pip install fastapi[websockets] uvicorn
   ```

### Debug Mode

Run tests with maximum verbosity and debugging:

```bash
# Full debug output
./scripts/run_cli_tests.py --all --verbose

# Pytest debug options
pytest tests/ -v -s --tb=long --capture=no

# Performance profiling
pytest tests/performance/ -v -s --durations=0
```

### Test Logs

Tests generate detailed logs for debugging:

- Use `capture_logs` fixture for log inspection
- Performance tests output metrics to console
- Security tests log attack attempts
- Integration tests show full workflow traces

## Contributing

### Adding New Tests

1. **Choose the appropriate test category**:
   - Unit tests for individual components
   - Integration tests for workflows
   - Performance tests for load scenarios
   - Security tests for vulnerabilities

2. **Follow naming conventions**:
   - Test files: `test_*.py`
   - Test methods: `test_*`
   - Use descriptive names

3. **Use appropriate fixtures**:
   - Leverage shared fixtures from `conftest.py`
   - Create test-specific fixtures as needed
   - Mock external dependencies

4. **Add proper markers**:
   ```python
   @pytest.mark.integration
   @pytest.mark.performance
   @pytest.mark.security
   ```

5. **Document test purpose**:
   - Clear docstrings
   - Expected behavior
   - Test data requirements

### Test Quality Guidelines

- **Independence**: Tests should not depend on other tests
- **Determinism**: Tests should produce consistent results
- **Speed**: Unit tests should be fast (< 1s each)
- **Isolation**: Use mocking to avoid external dependencies
- **Coverage**: Aim for comprehensive scenario coverage
- **Clarity**: Tests should be readable and well-documented

## Conclusion

This comprehensive test suite ensures the CLI integration system is robust, secure, performant, and ready for production use. The organized test categories, automated execution, and detailed reporting provide confidence in the system's quality and maintainability.

For questions or issues with the test suite, refer to the troubleshooting section or check the test runner help:

```bash
./scripts/run_cli_tests.py --help
```