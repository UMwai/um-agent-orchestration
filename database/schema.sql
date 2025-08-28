-- AutoDev Task Persistence Database Schema
-- This schema provides comprehensive task tracking and history storage

-- Tasks table: Core task information with full lifecycle tracking
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    role TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'queued',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    started_at TIMESTAMP NULL,
    
    -- Provider and model information
    provider TEXT NULL,
    model TEXT NULL,
    
    -- Git and worktree information
    branch TEXT NULL,
    worktree_path TEXT NULL,
    base_branch TEXT NULL,
    commit_hash TEXT NULL,
    
    -- Configuration and metadata
    target_dir TEXT DEFAULT '.',
    full_access BOOLEAN DEFAULT FALSE,
    provider_override TEXT NULL,
    repository_url TEXT NULL,
    
    -- Error tracking
    last_error TEXT NULL,
    error_count INTEGER DEFAULT 0,
    
    -- Acceptance criteria and additional metadata
    acceptance_criteria TEXT NULL, -- JSON string
    metadata TEXT NULL -- JSON string for extensibility
);

-- Task history table: State transitions and audit trail
CREATE TABLE IF NOT EXISTS task_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    state_from TEXT NULL,
    state_to TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Additional context
    provider TEXT NULL,
    model TEXT NULL,
    error_message TEXT NULL,
    details TEXT NULL, -- JSON string
    
    -- User context (for future multi-user support)
    user_id TEXT DEFAULT 'default',
    
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- Task outputs table: Store all outputs, logs, and artifacts
CREATE TABLE IF NOT EXISTS task_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    output_type TEXT NOT NULL, -- 'stdout', 'stderr', 'log', 'artifact', 'commit'
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- File information for artifacts
    file_path TEXT NULL,
    file_size INTEGER NULL,
    mime_type TEXT NULL,
    
    -- Commit information
    commit_hash TEXT NULL,
    branch TEXT NULL,
    
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- Task metrics table: Performance and resource usage tracking
CREATE TABLE IF NOT EXISTS task_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    unit TEXT NULL,
    
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- CLI sessions table: Track active CLI sessions
CREATE TABLE IF NOT EXISTS cli_sessions (
    session_id TEXT PRIMARY KEY,
    cli_tool TEXT NOT NULL, -- 'claude', 'codex', 'gemini', 'cursor'
    mode TEXT NOT NULL, -- 'cli', 'interactive', 'api'
    state TEXT NOT NULL DEFAULT 'initializing',
    pid INTEGER NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    terminated_at TIMESTAMP NULL,
    
    -- Session configuration
    current_directory TEXT NOT NULL,
    authentication_required BOOLEAN DEFAULT FALSE,
    auth_prompt TEXT NULL,
    
    -- Associated task (if any)
    task_id TEXT NULL,
    
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
);

-- CLI session commands table: Command history for CLI sessions
CREATE TABLE IF NOT EXISTS cli_session_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    command TEXT NOT NULL,
    output TEXT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms INTEGER NULL,
    exit_code INTEGER NULL,
    
    FOREIGN KEY (session_id) REFERENCES cli_sessions(session_id) ON DELETE CASCADE
);

-- User preferences table: Model and provider preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY DEFAULT 'default',
    preferred_provider TEXT NULL,
    preferred_model TEXT NULL,
    full_access_preferred BOOLEAN DEFAULT FALSE,
    role_preferences TEXT NULL, -- JSON string mapping role to provider
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_role ON tasks(role);
CREATE INDEX IF NOT EXISTS idx_tasks_provider ON tasks(provider);

CREATE INDEX IF NOT EXISTS idx_task_history_task_id ON task_history(task_id);
CREATE INDEX IF NOT EXISTS idx_task_history_timestamp ON task_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_task_history_state_to ON task_history(state_to);

CREATE INDEX IF NOT EXISTS idx_task_outputs_task_id ON task_outputs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_outputs_timestamp ON task_outputs(timestamp);
CREATE INDEX IF NOT EXISTS idx_task_outputs_output_type ON task_outputs(output_type);

CREATE INDEX IF NOT EXISTS idx_task_metrics_task_id ON task_metrics(task_id);
CREATE INDEX IF NOT EXISTS idx_task_metrics_timestamp ON task_metrics(timestamp);

CREATE INDEX IF NOT EXISTS idx_cli_sessions_state ON cli_sessions(state);
CREATE INDEX IF NOT EXISTS idx_cli_sessions_cli_tool ON cli_sessions(cli_tool);
CREATE INDEX IF NOT EXISTS idx_cli_sessions_created_at ON cli_sessions(created_at);

CREATE INDEX IF NOT EXISTS idx_cli_session_commands_session_id ON cli_session_commands(session_id);
CREATE INDEX IF NOT EXISTS idx_cli_session_commands_timestamp ON cli_session_commands(timestamp);

-- Triggers for automatic timestamp updates
CREATE TRIGGER IF NOT EXISTS update_tasks_updated_at 
    AFTER UPDATE ON tasks
    FOR EACH ROW
BEGIN
    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_user_preferences_updated_at 
    AFTER UPDATE ON user_preferences
    FOR EACH ROW
BEGIN
    UPDATE user_preferences SET updated_at = CURRENT_TIMESTAMP WHERE user_id = NEW.user_id;
END;

CREATE TRIGGER IF NOT EXISTS update_cli_sessions_last_activity 
    AFTER UPDATE ON cli_sessions
    FOR EACH ROW
BEGIN
    UPDATE cli_sessions SET last_activity = CURRENT_TIMESTAMP WHERE session_id = NEW.session_id;
END;

-- Views for common queries
CREATE VIEW IF NOT EXISTS task_summary AS
SELECT 
    t.id,
    t.title,
    t.role,
    t.state,
    t.provider,
    t.model,
    t.created_at,
    t.completed_at,
    t.last_error,
    COUNT(th.id) as state_changes,
    MAX(th.timestamp) as last_state_change
FROM tasks t
LEFT JOIN task_history th ON t.id = th.task_id
GROUP BY t.id;

CREATE VIEW IF NOT EXISTS active_cli_sessions AS
SELECT 
    cs.*,
    COUNT(csc.id) as command_count,
    MAX(csc.timestamp) as last_command_time
FROM cli_sessions cs
LEFT JOIN cli_session_commands csc ON cs.session_id = csc.session_id
WHERE cs.state NOT IN ('terminated', 'error')
GROUP BY cs.session_id;

-- Insert default user preferences
INSERT OR IGNORE INTO user_preferences (user_id) VALUES ('default');