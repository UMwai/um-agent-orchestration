# Claude Session Reuse Implementation

## Problem
When the web app spawns multiple Claude CLI processes, each one requires separate OAuth authentication, even when using `--dangerously-skip-permissions`. This leads to authentication fatigue and poor user experience.

## Solution
We've implemented a session reuse mechanism that maintains a single authenticated Claude session and routes all requests through it. This allows you to authenticate once and reuse your Claude Code subscription across all orchestration tasks.

## How It Works

1. **First Session**: When the first Claude session is created with full access, it starts normally and you authenticate as usual.

2. **Subsequent Sessions**: Any additional Claude sessions will detect and reuse the existing authenticated session, avoiding repeated auth flows.

3. **Session Persistence**: The authenticated session is kept alive and shared across all requests until explicitly terminated.

## Key Features

- **Automatic Detection**: The system automatically detects existing authenticated Claude sessions
- **Credentials Validation**: Checks `~/.claude/.credentials.json` for valid OAuth tokens
- **Process Sharing**: Multiple logical sessions share the same underlying Claude process
- **Clean Separation**: Non-Claude tools (Codex, Gemini) still get their own separate processes

## Implementation Details

### CLI Session Manager Updates

The `CLISessionManager` now includes:
- `claude_authenticated_session`: Stores reference to the authenticated session
- `_try_reuse_claude_session()`: Attempts to reuse existing session
- `_check_claude_auth_status()`: Validates Claude OAuth credentials
- Special handling in `terminate_session()` to preserve shared sessions

### Testing

Run the test script to verify session reuse:

```bash
python test_claude_session_reuse.py
```

This will:
1. Create two Claude sessions
2. Start them with full access
3. Verify they share the same process
4. Send a test message through the second session

## Usage in Production

1. **Web App**: The orchestrator will automatically reuse authenticated Claude sessions when processing tasks.

2. **API Requests**: Multiple API calls to create Claude sessions will share the same authenticated process.

3. **Manual Testing**: You can test via the API:

```bash
# Create first session
curl -X POST http://localhost:8000/cli/session/create \
  -H "Content-Type: application/json" \
  -d '{"cli_tool": "claude", "mode": "cli"}'

# Start with full access (authenticate once)
curl -X POST http://localhost:8000/cli/session/{session_id}/start \
  -H "Content-Type: application/json" \
  -d '{"full_access": true}'

# Create second session (will reuse auth)
curl -X POST http://localhost:8000/cli/session/create \
  -H "Content-Type: application/json" \
  -d '{"cli_tool": "claude", "mode": "cli"}'

# Start second session (no auth needed)
curl -X POST http://localhost:8000/cli/session/{session_id2}/start \
  -H "Content-Type: application/json" \
  -d '{"full_access": true}'
```

## Benefits

1. **Single Authentication**: Authenticate once per server session
2. **Subscription Value**: Maximize your Claude Code subscription usage
3. **Better UX**: No repeated authentication interruptions
4. **Resource Efficiency**: Single process handles multiple requests

## Limitations

- Sessions must use the same `full_access` setting
- All sessions share the same working directory context
- If the primary session crashes, all dependent sessions are affected

## Troubleshooting

### Session Not Reusing
Check:
- OAuth token validity in `~/.claude/.credentials.json`
- Both sessions are using `full_access=True`
- No process crashes between session creations

### Authentication Still Required
- Clear credentials: `rm -rf ~/.claude/.credentials.json`
- Restart the orchestrator
- Authenticate fresh with the first session

### Performance Issues
- Monitor process memory usage
- Consider restarting the shared session periodically
- Use API fallback for high-volume scenarios