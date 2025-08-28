# AutoDev CLI Integration Configuration Guide

**Version:** 1.0  
**Date:** August 27, 2025  
**Scope:** Production Configuration for CLI Integration Phase 1  

## Overview

This document provides comprehensive configuration guidance for the AutoDev CLI Integration system, covering environment variables, Redis setup, JWT authentication, CLI binary requirements, and security considerations.

## Environment Variables

### Core Configuration

```bash
# Database Configuration
DATABASE_PATH=database/tasks.db                    # SQLite database path
DATABASE_CONNECTION_POOL_SIZE=10                   # Connection pool size
DATABASE_WAL_MODE=true                             # Enable WAL mode for concurrent access

# Redis Configuration  
REDIS_URL=redis://localhost:6379                   # Redis connection URL
REDIS_PASSWORD=your_secure_redis_password          # Redis password (optional)
REDIS_DB=0                                          # Redis database number
REDIS_MAX_CONNECTIONS=20                            # Redis connection pool size
REDIS_RETRY_ON_TIMEOUT=true                        # Retry Redis operations on timeout

# WebSocket Security
JWT_SECRET=your_256_bit_secret_key_here            # JWT signing secret (REQUIRED)
JWT_ALGORITHM=HS256                                 # JWT algorithm
JWT_EXPIRATION_HOURS=24                            # Token expiration time
JWT_ISSUER=autodev                                  # JWT issuer claim

# CLI Session Configuration
CLI_SESSION_TIMEOUT_MINUTES=60                     # Inactive session cleanup timeout
CLI_MAX_CONCURRENT_SESSIONS=50                     # Maximum concurrent CLI sessions
CLI_OUTPUT_BUFFER_SIZE=8192                        # CLI output buffer size in bytes
CLI_HEARTBEAT_INTERVAL_SECONDS=30                  # WebSocket heartbeat interval
CLI_MESSAGE_QUEUE_SIZE=100                         # Max queued messages per connection
```

### CLI Provider API Keys

```bash
# Anthropic Claude CLI
ANTHROPIC_API_KEY=sk-ant-api03-your-claude-key-here

# OpenAI Codex CLI
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_ORG_ID=org-your-organization-id             # Optional organization ID

# Google Gemini CLI
GOOGLE_API_KEY=your-google-api-key-here
GOOGLE_PROJECT_ID=your-google-project-id           # Optional project ID

# Cursor CLI (may require subscription)
CURSOR_API_KEY=your-cursor-api-key-here            # If applicable
CURSOR_SUBSCRIPTION_KEY=your-subscription-key      # Pro/Team subscription
```

### Logging and Monitoring

```bash
# Logging Configuration
LOG_LEVEL=INFO                                      # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json                                     # json, text
LOG_FILE_PATH=logs/autodev.log                     # Log file path
LOG_MAX_SIZE_MB=100                                 # Max log file size
LOG_BACKUP_COUNT=5                                  # Number of backup log files

# Metrics and Monitoring
PROMETHEUS_ENABLED=true                             # Enable Prometheus metrics
PROMETHEUS_PORT=9090                                # Prometheus metrics port
METRICS_COLLECTION_INTERVAL_SECONDS=30             # Metrics collection interval
```

### Development and Testing

```bash
# Development Configuration
AUTODEV_ENV=production                              # development, staging, production
DEBUG=false                                         # Enable debug mode
RELOAD_ON_CHANGE=false                             # Auto-reload on code changes
TESTING_MODE=false                                  # Enable testing mode features

# CLI Integration Testing
TEST_CLI_BINARIES_PATH=/usr/local/bin              # Path to test CLI binaries
MOCK_CLI_RESPONSES=false                            # Use mock CLI responses for testing
CLI_TEST_TIMEOUT_SECONDS=30                        # Test timeout for CLI operations
```

## Redis Configuration

### Basic Redis Setup

#### Option 1: Docker Redis (Recommended for Development)
```bash
# Start Redis with Docker
docker run -d \
  --name autodev-redis \
  -p 6379:6379 \
  -v autodev-redis-data:/data \
  redis:7-alpine redis-server --appendonly yes
```

#### Option 2: System Redis Installation

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

**CentOS/RHEL:**
```bash
sudo yum install epel-release
sudo yum install redis
sudo systemctl enable redis
sudo systemctl start redis
```

**macOS:**
```bash
brew install redis
brew services start redis
```

### Redis Configuration File (`/etc/redis/redis.conf`)

```bash
# Basic Configuration
bind 127.0.0.1                    # Bind to localhost only for security
port 6379                         # Standard Redis port
daemonize yes                     # Run as daemon

# Security
requirepass your_secure_password  # Set password
rename-command FLUSHALL ""        # Disable dangerous commands
rename-command FLUSHDB ""
rename-command CONFIG ""

# Performance
maxmemory 256mb                   # Set memory limit
maxmemory-policy allkeys-lru      # Eviction policy
tcp-keepalive 60                  # TCP keepalive
timeout 300                       # Client timeout

# Persistence
save 900 1                        # Save after 900 seconds if at least 1 key changed
save 300 10                       # Save after 300 seconds if at least 10 keys changed
save 60 10000                     # Save after 60 seconds if at least 10000 keys changed
appendonly yes                    # Enable AOF persistence
appendfsync everysec              # Sync AOF every second
```

### Redis Cluster Configuration (Production)

For high availability, configure Redis Sentinel or Cluster mode:

```bash
# Redis Sentinel configuration example
REDIS_URL=redis+sentinel://localhost:26379
REDIS_SENTINEL_SERVICE_NAME=mymaster
REDIS_SENTINEL_SOCKET_TIMEOUT=0.1
REDIS_SENTINEL_PASSWORD=your_sentinel_password
```

## JWT Authentication Configuration

### JWT Secret Generation

Generate a secure JWT secret:

```bash
# Generate a 256-bit secret key
python -c "import secrets; print(secrets.token_hex(32))"

# Or use OpenSSL
openssl rand -hex 32

# Example output (DO NOT USE THIS IN PRODUCTION):
# a1b2c3d4e5f6789abcdef123456789abcdef123456789abcdef123456789abcdef
```

### JWT Token Configuration

```bash
# JWT Configuration in environment
JWT_SECRET=your_generated_secret_here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
JWT_ISSUER=autodev
JWT_AUDIENCE=autodev-users

# Advanced JWT Configuration
JWT_REQUIRE_EXP=true                # Require expiration claim
JWT_REQUIRE_IAT=true                # Require issued at claim
JWT_VERIFY_SIGNATURE=true           # Verify token signature
JWT_VERIFY_EXPIRATION=true          # Verify token expiration
```

### JWT Token Usage Example

```bash
# Generate a test token (for development)
python -c "
import jwt
import datetime
payload = {
    'user_id': 'test_user',
    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),
    'iat': datetime.datetime.utcnow(),
    'iss': 'autodev'
}
token = jwt.encode(payload, 'your_secret_here', algorithm='HS256')
print('Test Token:', token)
"
```

## CLI Binary Requirements

### Installation Paths and Verification

The system requires actual CLI binaries to be installed and accessible in the system PATH:

#### Claude CLI (Anthropic)
```bash
# Installation (requires Anthropic account)
curl -O https://storage.googleapis.com/anthropic-cli/install.sh
chmod +x install.sh
./install.sh

# Verify installation
claude --version
claude auth login    # Authenticate with API key

# Test CLI availability
which claude         # Should return: /usr/local/bin/claude
```

#### Codex CLI (OpenAI)
```bash
# Installation (varies by provider)
npm install -g openai-codex-cli  # If available via npm
# or
pip install codex-cli            # If available via pip

# Verify installation
codex --version
codex auth login

# Test CLI availability
which codex          # Should return path to codex binary
```

#### Gemini CLI (Google)
```bash
# Installation
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/gemini-cli-linux-x86_64.tar.gz
tar -xzf gemini-cli-linux-x86_64.tar.gz
sudo mv gemini /usr/local/bin/

# Verify installation
gemini --version
gemini auth login

# Test CLI availability
which gemini         # Should return: /usr/local/bin/gemini
```

#### Cursor CLI (Cursor AI)
```bash
# Installation (requires Cursor subscription)
curl -fsSL https://cursor.sh/install | sh
# or download from https://cursor.sh/

# Verify installation
cursor-agent --version

# Test CLI availability
which cursor-agent   # Should return path to cursor-agent
```

### CLI Binary Configuration Verification

Create a verification script to check CLI availability:

```bash
#!/bin/bash
# cli_check.sh - Verify CLI binaries are properly installed

echo "Checking CLI Binary Availability..."

check_cli() {
    local cli=$1
    local version_flag=${2:-"--version"}
    
    if command -v "$cli" >/dev/null 2>&1; then
        echo "✅ $cli: $(which $cli)"
        $cli $version_flag 2>/dev/null || echo "⚠️  Version check failed for $cli"
    else
        echo "❌ $cli: Not found in PATH"
    fi
}

check_cli "claude"
check_cli "codex"
check_cli "gemini"
check_cli "cursor-agent"

echo "CLI Binary Check Complete"
```

## Database Configuration

### SQLite Configuration

The system uses SQLite with WAL mode for concurrent access:

```bash
# Database configuration
DATABASE_PATH=database/tasks.db
DATABASE_BACKUP_PATH=database/backups/
DATABASE_BACKUP_INTERVAL_HOURS=24

# SQLite optimizations (applied automatically)
# - WAL mode for concurrent access
# - NORMAL synchronous mode for performance
# - 10MB cache size
# - Connection pooling
```

### Database Initialization

```bash
# Initialize database schema (automatic on first run)
# Database will be created at: database/tasks.db
# Schema will be applied from: database/schema.sql

# Manual database initialization (if needed)
sqlite3 database/tasks.db < database/schema.sql
```

### Database Backup Strategy

```bash
#!/bin/bash
# backup_database.sh - Database backup script

DATABASE_PATH="database/tasks.db"
BACKUP_DIR="database/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create backup with WAL mode considerations
sqlite3 "$DATABASE_PATH" ".backup $BACKUP_DIR/tasks_${TIMESTAMP}.db"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "tasks_*.db" -mtime +7 -delete

echo "Database backup completed: tasks_${TIMESTAMP}.db"
```

## Security Configuration

### Network Security

```bash
# Bind services to localhost only for security
FASTAPI_HOST=127.0.0.1              # Bind FastAPI to localhost
FASTAPI_PORT=8000                   # FastAPI port
WEBSOCKET_ALLOWED_ORIGINS=["http://localhost:3000", "https://your-domain.com"]

# CORS configuration for dashboard
CORS_ALLOWED_ORIGINS=["http://localhost:3000"]
CORS_ALLOWED_METHODS=["GET", "POST", "PUT", "DELETE"]
CORS_ALLOWED_HEADERS=["*"]
CORS_ALLOW_CREDENTIALS=true
```

### Process Security

```bash
# CLI process security
CLI_PROCESS_ISOLATION=true           # Enable process isolation
CLI_PROCESS_USER=autodev            # Run CLI processes as specific user
CLI_PROCESS_GROUP=autodev           # Process group for CLI processes
CLI_CHROOT_ENABLED=false            # Enable chroot for CLI processes (advanced)
CLI_RESOURCE_LIMITS_ENABLED=true    # Enable resource limits

# Resource limits per CLI process
CLI_MAX_MEMORY_MB=512               # Maximum memory per CLI process
CLI_MAX_CPU_PERCENT=50              # Maximum CPU usage per CLI process  
CLI_MAX_EXECUTION_TIME_MINUTES=60   # Maximum execution time per CLI process
```

### File System Security

```bash
# Working directory configuration
CLI_WORK_DIR=/tmp/autodev/cli      # CLI working directory
CLI_OUTPUT_DIR=/var/log/autodev/cli # CLI output directory
CLI_TEMP_DIR=/tmp/autodev/temp      # Temporary directory for CLI operations

# File permissions
CLI_FILE_PERMISSIONS=0755           # Default file permissions
CLI_DIR_PERMISSIONS=0755            # Default directory permissions
CLI_LOG_PERMISSIONS=0644            # Log file permissions
```

## Performance Tuning

### Memory Configuration

```bash
# Memory limits and optimization
PYTHON_MAX_MEMORY_MB=2048           # Maximum Python process memory
CLI_OUTPUT_BUFFER_SIZE=8192         # CLI output buffer size
REDIS_MAX_MEMORY=256mb              # Redis memory limit
DATABASE_CACHE_SIZE_MB=50           # Database cache size
```

### Connection Limits

```bash
# Connection and concurrency limits
MAX_CONCURRENT_CLI_SESSIONS=50      # Maximum concurrent CLI sessions
MAX_WEBSOCKET_CONNECTIONS=100       # Maximum WebSocket connections
MAX_REDIS_CONNECTIONS=20            # Redis connection pool size
MAX_DATABASE_CONNECTIONS=10         # Database connection pool size
```

### Timeout Configuration

```bash
# Various timeout settings
CLI_SESSION_TIMEOUT_MINUTES=60      # Inactive CLI session timeout
WEBSOCKET_TIMEOUT_SECONDS=300       # WebSocket connection timeout
REDIS_TIMEOUT_SECONDS=5             # Redis operation timeout
DATABASE_TIMEOUT_SECONDS=30         # Database operation timeout
HTTP_TIMEOUT_SECONDS=30             # HTTP request timeout
```

## Configuration Validation

### Environment Validation Script

```bash
#!/bin/bash
# validate_config.sh - Configuration validation script

echo "Validating AutoDev CLI Integration Configuration..."

# Check required environment variables
check_env_var() {
    local var_name=$1
    local required=${2:-true}
    
    if [[ -z "${!var_name}" ]]; then
        if [[ "$required" == "true" ]]; then
            echo "❌ Required environment variable $var_name is not set"
            return 1
        else
            echo "⚠️  Optional environment variable $var_name is not set"
        fi
    else
        echo "✅ $var_name is set"
    fi
}

# Required variables
check_env_var "JWT_SECRET" true
check_env_var "REDIS_URL" false
check_env_var "DATABASE_PATH" false

# API keys (at least one required)
api_key_count=0
[[ -n "$ANTHROPIC_API_KEY" ]] && ((api_key_count++)) && echo "✅ ANTHROPIC_API_KEY is set"
[[ -n "$OPENAI_API_KEY" ]] && ((api_key_count++)) && echo "✅ OPENAI_API_KEY is set"
[[ -n "$GOOGLE_API_KEY" ]] && ((api_key_count++)) && echo "✅ GOOGLE_API_KEY is set"

if [[ $api_key_count -eq 0 ]]; then
    echo "❌ At least one API key must be set (ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY)"
else
    echo "✅ $api_key_count API key(s) configured"
fi

echo "Configuration validation complete"
```

### Runtime Configuration Check

The system performs automatic configuration validation on startup:

```bash
# Configuration check output example:
🔧 AutoDev CLI Integration Configuration Check
   ✅ JWT_SECRET: Configured (length: 64)
   ✅ Redis: Connected (redis://localhost:6379)
   ✅ Database: Initialized (database/tasks.db)
   ✅ CLI Binaries: 3/4 available (claude, codex, gemini)
   ⚠️  CLI Binary: cursor-agent not found
   ✅ WebSocket: Configured (port 8000)
   ✅ Metrics: Enabled (port 9090)
```

## Environment-Specific Configuration

### Development Environment

```bash
# .env.development
AUTODEV_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG
RELOAD_ON_CHANGE=true
JWT_SECRET=dev_secret_key_not_for_production
REDIS_URL=redis://localhost:6379
TESTING_MODE=true
CLI_SESSION_TIMEOUT_MINUTES=30
```

### Staging Environment

```bash
# .env.staging
AUTODEV_ENV=staging
DEBUG=false
LOG_LEVEL=INFO
RELOAD_ON_CHANGE=false
JWT_SECRET=staging_secure_secret_key
REDIS_URL=redis://staging-redis:6379
REDIS_PASSWORD=staging_redis_password
CLI_SESSION_TIMEOUT_MINUTES=45
```

### Production Environment

```bash
# .env.production
AUTODEV_ENV=production
DEBUG=false
LOG_LEVEL=WARNING
RELOAD_ON_CHANGE=false
JWT_SECRET=production_ultra_secure_secret_key
REDIS_URL=redis://production-redis:6379
REDIS_PASSWORD=production_ultra_secure_redis_password
CLI_SESSION_TIMEOUT_MINUTES=60
PROMETHEUS_ENABLED=true
```

## Troubleshooting Configuration Issues

### Common Configuration Problems

1. **JWT Authentication Failures**
   ```bash
   # Check JWT secret length (should be 32+ characters)
   echo $JWT_SECRET | wc -c
   
   # Verify JWT token generation
   python -c "import jwt; print(jwt.encode({'test': 'data'}, '$JWT_SECRET', algorithm='HS256'))"
   ```

2. **Redis Connection Issues**
   ```bash
   # Test Redis connectivity
   redis-cli -h localhost -p 6379 ping
   
   # Check Redis configuration
   redis-cli config get "*"
   ```

3. **CLI Binary Issues**
   ```bash
   # Verify PATH includes CLI binaries
   echo $PATH
   
   # Check CLI binary permissions
   ls -la $(which claude codex gemini cursor-agent)
   ```

4. **Database Issues**
   ```bash
   # Check database file permissions
   ls -la database/tasks.db
   
   # Verify database schema
   sqlite3 database/tasks.db ".schema"
   ```

### Configuration Debugging

Enable debug mode for detailed configuration logging:

```bash
DEBUG=true LOG_LEVEL=DEBUG python -m orchestrator.app
```

This will output detailed configuration information during startup, helping identify configuration issues.

---

This configuration guide provides comprehensive setup instructions for the AutoDev CLI Integration system. For additional support, refer to the User Guide and Developer Guide documentation.