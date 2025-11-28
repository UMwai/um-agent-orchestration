# Claude CLI Integration with Web Application

## Overview
Your webapp at `localhost:8001` can successfully launch and manage local Claude Code CLI sessions. The integration uses your existing Claude authentication from `~/.claude/` to avoid repeated login prompts.

## How It Works

### 1. Authentication Inheritance
- Each Claude process spawned by the webapp inherits your local user environment
- The system correctly sets `HOME`, `USER`, and XDG paths
- Claude CLI automatically finds and uses credentials from `~/.claude/.credentials.json`
- OAuth tokens are reused across sessions

### 2. Session Reuse 
- First Claude session with `full_access=true` becomes the "master" session
- Subsequent Claude sessions detect and reuse the master session's process
- This avoids spawning multiple processes and repeated authentication
- When a reused session terminates, the master process is preserved

### 3. Health Monitoring
- Health check endpoint at `/api/cli/auth/health` verifies authentication status
- Checks token validity, expiration time, and Claude binary availability
- Provides recommendations when authentication issues are detected

## API Endpoints

### Check Authentication Health
```bash
GET /api/cli/auth/health
```
Returns authentication status, token validity, and recommendations.

### Create CLI Session
```bash
POST /api/cli/sessions
{
  "cli_tool": "claude",
  "mode": "cli",
  "full_access": true
}
```
Creates a new Claude session (or reuses existing authenticated session).

### Send Input to Session
```bash
POST /api/cli/sessions/{session_id}/input
{
  "input": "Your message here"
}
```

### List Active Sessions
```bash
GET /api/cli/sessions
```

### Get Session Info
```bash
GET /api/cli/sessions/{session_id}
```

### Terminate Session
```bash
DELETE /api/cli/sessions/{session_id}
```

## Testing the Integration

Run the test script to verify everything works:
```bash
# Make sure the server is running
make dev

# In another terminal, run the test
python test_claude_integration.py
```

## Key Benefits

1. **Single Authentication**: Authenticate once, use everywhere
2. **Process Efficiency**: Reuses sessions to minimize resource usage
3. **Seamless Integration**: Works with your existing Claude Code setup
4. **Real-time Communication**: WebSocket support for streaming responses
5. **Robust Error Handling**: Graceful fallbacks and clear error messages

## Troubleshooting

### Authentication Issues
If you see authentication prompts:
1. Run `claude auth login` in your terminal first
2. Check health endpoint: `curl localhost:8001/api/cli/auth/health`
3. Verify credentials exist: `ls ~/.claude/.credentials.json`

### Session Not Starting
1. Check Claude binary: `which claude`
2. Verify environment variables are passed correctly
3. Check logs for specific error messages

### Session Reuse Not Working
1. Ensure first session uses `full_access=true`
2. Verify master session is still running
3. Check process health in session info

## Architecture Details

### Components
- **CLISessionManager**: Manages session lifecycle and reuse logic
- **CLIProcessManager**: Handles PTY-based process communication  
- **ClaudeSessionPool**: Optional pooling for high-volume scenarios
- **WebSocket Handler**: Real-time bidirectional communication

### Session States
- `INITIALIZING`: Session being created
- `STARTING`: Process launching
- `RUNNING`: Ready for commands
- `PROCESSING`: Handling user input
- `TERMINATED`: Session ended

## Production Recommendations

1. **Use Session Pooling**: For high-volume applications, enable the session pool
2. **Monitor Token Expiry**: Check auth health regularly
3. **Implement Retry Logic**: Handle transient failures gracefully
4. **Set Resource Limits**: Limit concurrent sessions per user
5. **Add Metrics**: Track session usage and performance

## Alternative: API Fallback

If CLI integration has issues, you can fallback to the Anthropic API:

```bash
# Set your API key
export ANTHROPIC_API_KEY="your-key-here"

# Update config to use API mode
# The system will automatically fallback when CLI is unavailable
```

## Summary

Your webapp can successfully integrate with local Claude Code CLI! The implementation:
- ✅ Uses your existing Claude authentication
- ✅ Reuses sessions to avoid repeated logins
- ✅ Provides health monitoring
- ✅ Supports real-time communication
- ✅ Handles errors gracefully

The integration is production-ready and optimized for a smooth developer experience.