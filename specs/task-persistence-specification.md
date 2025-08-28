# Task Persistence Specification

## Executive Summary

This specification defines the comprehensive task persistence system for the AutoDev orchestration platform, ensuring zero data loss and complete task lifecycle tracking through dual-write architecture with Redis (real-time) and SQLite (persistent storage).

## Business Requirements

### Primary Objectives
- **Zero Data Loss**: All submitted tasks and their progression must survive system restarts
- **Complete Audit Trail**: Full history of task state changes with timestamps and metadata
- **Fast Recovery**: System must restore task state within 30 seconds of restart
- **Scalable Storage**: Handle 10,000+ tasks with efficient querying and filtering

### Success Criteria
- ✅ No task data lost during Redis/application restarts
- ✅ Complete task history available for analysis and debugging
- ✅ Task recovery time < 30 seconds on system startup
- ✅ API response times < 500ms for task queries
- ✅ Support for advanced filtering and search capabilities

## Technical Architecture

### Dual-Write Storage Strategy

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Task Submit   │───►│  Dual-Write      │───►│   SQLite DB     │
│   (API Call)    │    │  Persistence     │    │  (Permanent)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Redis Cache   │
                       │  (Real-time)    │
                       └─────────────────┘
```

### Data Models

#### Core Task Record
```python
class TaskRecord(BaseModel):
    id: str
    title: str
    description: str
    role: str
    state: TaskState  # Enhanced enum with full lifecycle
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    
    # Provider and execution metadata
    provider: Optional[str] = None
    model: Optional[str] = None
    
    # Git and deployment information
    branch: Optional[str] = None
    worktree_path: Optional[str] = None
    base_branch: Optional[str] = None
    commit_hash: Optional[str] = None
    
    # Configuration and preferences
    target_dir: str = "."
    full_access: bool = False
    provider_override: Optional[str] = None
    repository_url: Optional[str] = None
    
    # Error tracking and debugging
    last_error: Optional[str] = None
    error_count: int = 0
    
    # Extensible metadata
    acceptance_criteria: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
```

#### Task History Tracking
```python
class TaskHistoryRecord(BaseModel):
    id: Optional[int] = None
    task_id: str
    state_from: Optional[TaskState] = None
    state_to: TaskState
    timestamp: datetime
    provider: Optional[str] = None
    model: Optional[str] = None
    error_message: Optional[str] = None
    details: Dict[str, Any] = {}
    user_id: str = "default"  # Future multi-user support
```

#### Task Outputs and Artifacts
```python
class TaskOutput(BaseModel):
    id: Optional[int] = None
    task_id: str
    output_type: OutputType  # stdout, stderr, log, artifact, commit
    content: str
    timestamp: datetime
    
    # File and artifact metadata
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    
    # Git integration
    commit_hash: Optional[str] = None
    branch: Optional[str] = None
```

## Database Schema

### SQLite Tables

#### Primary Tables
- **`tasks`**: Core task information with full lifecycle data
- **`task_history`**: Complete audit trail of state changes
- **`task_outputs`**: All outputs, logs, and artifacts
- **`task_metrics`**: Performance and resource usage metrics

#### CLI Integration Tables
- **`cli_sessions`**: Active CLI session tracking
- **`cli_session_commands`**: Command history for CLI sessions

#### Configuration Tables
- **`user_preferences`**: Model and provider preferences

### Performance Optimization
- **Indexes**: Optimized for common query patterns (state, role, date ranges)
- **Views**: Pre-computed summaries for dashboard display
- **Triggers**: Automatic timestamp updates and data validation
- **WAL Mode**: Write-Ahead Logging for concurrent access

## API Endpoints

### Task Persistence APIs

#### Task History Management
```http
GET /api/tasks/history/{task_id}
# Returns complete history for a specific task

GET /api/tasks/persistent
# Get all tasks with advanced filtering
# Query params: states, roles, providers, search, limit, offset

POST /api/tasks/{task_id}/recover
# Recover task from persistent storage to Redis
```

#### Output and Artifact Management
```http
GET /api/tasks/outputs/{task_id}
# Get all outputs and artifacts for a task

POST /api/tasks/outputs/{task_id}
# Add new output/artifact to a task
```

#### System Statistics
```http
GET /api/persistence/stats
# Get database statistics and health metrics
```

### Query Parameters and Filtering

#### Advanced Task Filtering
```http
GET /api/tasks/persistent?states=running,queued&roles=backend,frontend&providers=claude&search=login&limit=50&offset=0
```

#### Date Range Queries
```http
GET /api/tasks/persistent?date_from=2024-01-01T00:00:00Z&date_to=2024-12-31T23:59:59Z
```

## Data Persistence Guarantees

### Write Operations
1. **Task Creation**: Dual-write to SQLite (immediate) and Redis (cache)
2. **State Updates**: SQLite updated first, then Redis for consistency
3. **Output Storage**: Immediate persistence with optional streaming

### Read Operations
1. **Real-time Data**: Redis for current task status
2. **Historical Data**: SQLite for complete history and analytics
3. **Recovery Data**: SQLite as source of truth during recovery

### Consistency Model
- **Eventually Consistent**: Redis may lag SQLite by milliseconds
- **Conflict Resolution**: SQLite data takes precedence during recovery
- **Transaction Safety**: SQLite operations are atomic with rollback support

## Recovery Mechanisms

### Startup Recovery Process
1. **Database Initialization**: Create schema if not exists
2. **Data Validation**: Check database integrity
3. **Task Recovery**: Restore active tasks from SQLite to Redis
4. **Interrupted Tasks**: Mark running tasks as failed with recovery reason
5. **Consistency Check**: Verify Redis/SQLite alignment

### Automatic Recovery Features
- **Interrupted Task Detection**: Automatically handle system crashes
- **Redis Repopulation**: Restore cache from persistent storage
- **Data Consistency Verification**: Regular consistency checks
- **Cleanup Operations**: Remove expired Redis entries

### Manual Recovery Options
```bash
# API endpoints for manual recovery
POST /api/tasks/{task_id}/recover     # Recover specific task
GET /api/persistence/stats            # Check system health
```

## Performance Requirements

### Response Time Targets
- **Task Submission**: < 100ms (including dual-write)
- **Task Status Query**: < 50ms (from Redis cache)
- **History Retrieval**: < 500ms (from SQLite)
- **Search Operations**: < 1000ms (with proper indexing)

### Throughput Requirements
- **Task Submissions**: 100 tasks/minute sustained
- **Concurrent Reads**: 1000 requests/minute
- **Storage Growth**: Linear scaling to 100K+ tasks

### Storage Efficiency
- **Database Size**: < 1MB per 1000 completed tasks
- **Index Overhead**: < 20% of total database size
- **Cleanup Frequency**: Automated archival of tasks > 90 days old

## Security and Compliance

### Data Protection
- **Sensitive Data**: No API keys or secrets stored in task data
- **Access Control**: Future-ready for multi-user authentication
- **Audit Trail**: Immutable history for compliance tracking

### Backup and Disaster Recovery
- **SQLite Backup**: Automated daily backups with 30-day retention
- **Redis Persistence**: RDB snapshots + AOF for durability
- **Export Capabilities**: JSON/CSV export for data portability

## Monitoring and Alerting

### Health Metrics
- **Database Size**: Monitor growth and performance impact
- **Write Performance**: Track dual-write latency
- **Recovery Statistics**: Monitor startup recovery times
- **Consistency Checks**: Alert on data inconsistencies

### Operational Dashboards
- **Task Statistics**: Real-time counts by state/role/provider
- **Performance Metrics**: Response times and throughput
- **Error Tracking**: Failed tasks and recovery operations
- **Storage Analytics**: Database growth and optimization opportunities

## Implementation Phases

### Phase 1: Core Persistence (Completed)
- ✅ SQLite schema and models
- ✅ TaskPersistenceManager implementation
- ✅ Dual-write integration
- ✅ Basic API endpoints

### Phase 2: Advanced Features
- 🔄 Dashboard UI for task history
- 🔄 Advanced filtering and search
- 🔄 Export/import capabilities
- 🔄 Performance optimization

### Phase 3: Production Hardening
- 📋 Monitoring and alerting
- 📋 Backup automation
- 📋 Performance tuning
- 📋 Security hardening

### Phase 4: Scale and Analytics
- 📋 Multi-user support
- 📋 Advanced analytics
- 📋 Data archival strategies
- 📋 Integration with external systems

## Testing Strategy

### Unit Tests
- ✅ TaskPersistenceManager operations
- ✅ Data model validation
- ✅ Recovery mechanisms
- ✅ API endpoint functionality

### Integration Tests
- 🔄 Redis/SQLite consistency
- 🔄 Recovery scenarios
- 🔄 Performance benchmarks
- 🔄 Concurrent operations

### Load Testing
- 📋 High-throughput task submission
- 📋 Large-scale recovery operations
- 📋 Database performance under load
- 📋 Memory usage optimization

## Migration and Deployment

### Backward Compatibility
- **Existing Tasks**: Automatic migration of Redis-only tasks
- **API Compatibility**: All existing endpoints remain functional
- **Data Format**: Graceful handling of legacy task formats

### Deployment Steps
1. **Database Migration**: Run schema creation scripts
2. **Application Restart**: Enable persistence features
3. **Data Migration**: Import existing Redis tasks to SQLite
4. **Validation**: Verify data consistency and functionality
5. **Monitoring**: Enable health checks and alerting

### Rollback Strategy
- **Feature Flags**: Disable persistence if issues arise
- **Data Preservation**: Both Redis and SQLite data maintained
- **Quick Recovery**: Rollback to Redis-only mode if needed

## Success Metrics

### Technical Metrics
- **Zero Data Loss**: 100% task preservation across restarts
- **Recovery Time**: < 30 seconds for system startup
- **API Performance**: < 500ms for all persistence operations
- **Data Consistency**: > 99.9% Redis/SQLite alignment

### Business Metrics
- **System Reliability**: > 99.9% uptime with persistence
- **Developer Productivity**: Reduced time spent on task debugging
- **Operational Efficiency**: Reduced manual task recovery operations
- **Audit Compliance**: Complete task history for compliance requirements

This specification ensures that the AutoDev system provides enterprise-grade task persistence with zero data loss, comprehensive auditing, and efficient recovery capabilities.