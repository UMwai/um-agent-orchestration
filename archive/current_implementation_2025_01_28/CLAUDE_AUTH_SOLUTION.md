# Claude Authentication Solution

## Problem Summary
The web app is creating new Claude CLI sessions that each require separate authentication, even when you already have an authenticated Claude session. This happens because:
1. Each `claude` process starts fresh and requests its own OAuth authentication
2. The `--dangerously-skip-permissions` flag doesn't bypass authentication, only permissions
3. Claude's OAuth tokens appear to be session-specific rather than shared across processes

## Current Behavior
When creating a Claude CLI session through the web app:
1. A new `claude` process is spawned
2. It detects it needs authentication (even if you're already logged in elsewhere)
3. It prompts for browser-based OAuth login
4. The session gets stuck waiting for authentication

## Solutions

### Option 1: Use the Anthropic API directly
Instead of using the Claude CLI, configure the orchestrator to use the Anthropic API directly:
```bash
# Set your API key
export ANTHROPIC_API_KEY="your-api-key-here"

# The orchestrator will fall back to API mode automatically
```

### Option 2: Use a single persistent Claude session
Rather than creating new Claude processes, proxy commands through your existing authenticated Claude session:
1. Keep your main Claude session running
2. Have the web app send commands to that single session
3. This avoids repeated authentication requests

### Option 3: Pre-authenticate sessions
Before using the web app:
1. Manually authenticate Claude: `claude auth login`
2. Ensure your credentials are fresh
3. The sessions *should* inherit the auth (though this is currently not working reliably)

## Recommended Solution
**Use the Anthropic API directly** (Option 1) for the orchestrator. This provides:
- No authentication issues
- Better programmatic control
- Consistent behavior
- No interactive prompts

## Configuration
To switch to API mode, update `config/config.yaml`:
```yaml
providers:
  anthropic_api:
    mode: "api"
    provider_type: "api"
    model: "claude-3-5-sonnet-20241022"
    api_key: "${ANTHROPIC_API_KEY}"
```

Then set your environment variable:
```bash
echo "ANTHROPIC_API_KEY=your-key-here" >> .env
```

## Testing the Fix
After configuring API mode:
```bash
# Restart the server
make dev

# Create a session (will use API instead of CLI)
curl -X POST http://localhost:8001/api/cli/sessions \
  -H "Content-Type: application/json" \
  -d '{"cli_tool": "claude", "full_access": true}'
```

The session will now use the API directly without authentication prompts.