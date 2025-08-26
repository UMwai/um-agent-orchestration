# Full Access Mode Security Considerations

This document outlines important security considerations when using AutoDev's full access mode.

## ⚠️ Security Warning

**Full Access Mode Bypasses Safety Restrictions**

When `full_access: true` is enabled, the system uses:
- Claude Code with `--dangerously-skip-permissions`  
- Codex with `--ask-for-approval never --sandbox danger-full-access`

This grants agents unrestricted access to:
- File system operations (create, read, write, delete)
- System command execution
- Network operations
- Environment variable access
- Process spawning and management

## Recommended Security Practices

### 1. Environment Isolation

**DO:**
```bash
# Run full access mode in isolated development environments
docker run -it --rm -v $(pwd):/workspace autodev:dev

# Use dedicated development VMs or containers
vagrant up development
```

**DON'T:**
```bash
# Never run full access mode on production systems
# Never run with access to production databases
# Never run with production API keys in environment
```

### 2. Access Control

**DO:**
- Use separate API keys for development vs production
- Limit network access from development environments
- Use read-only database connections when possible
- Enable git branch protection rules

**Configuration Example:**
```yaml
# .env.development
ANTHROPIC_API_KEY=sk-ant-dev-only-key  # Development key only
DATABASE_URL=postgresql://dev-readonly:pass@dev-db/app
ENVIRONMENT=development

# config/config.yaml
full_access:
  enabled: true
  allowed_environments: ["development", "staging"]  # Never production
  max_file_size_mb: 100  # Limit file operations
  blocked_paths: ["/etc", "/usr", "/var", "~/.ssh"]  # System directories
```

### 3. Task Review Process

**Implement Code Review:**
```yaml
# Example task with mandatory review
id: FULL-ACCESS-TASK-001
title: "Infrastructure Changes"
role: backend
full_access: true
acceptance:
  tests: ["tests/infrastructure/"]
  lint: true
  typecheck: true
  manual_review_required: true  # Custom field for your process
```

**Git Workflow:**
```bash
# All full access tasks create feature branches
# Review before merging to main
git checkout auto/backend/FULL-ACCESS-TASK-001
git log --oneline  # Review all commits
git diff main  # Review all changes
```

### 4. Monitoring and Logging

**Enable Comprehensive Logging:**
```yaml
# monitoring/logging.yaml
logging:
  level: DEBUG
  full_access_tasks:
    log_all_commands: true
    log_file_operations: true
    alert_on_system_commands: true
```

**Monitor File Changes:**
```bash
# Track all file modifications
git log --name-status --oneline auto/backend/FULL-ACCESS-TASK-001

# Use file system monitoring
fswatch -o . | xargs -n1 -I{} git status --porcelain
```

### 5. Resource Limits

**Configure Resource Constraints:**
```yaml
# config/config.yaml
full_access:
  resource_limits:
    max_execution_time_minutes: 60
    max_file_operations: 1000
    max_subprocess_calls: 100
    memory_limit_mb: 2048
```

## Security Checklist

### Before Enabling Full Access Mode

- [ ] Verify running in development/staging environment only
- [ ] Confirm no production credentials in environment
- [ ] Enable git branch protection rules
- [ ] Set up monitoring and alerting
- [ ] Configure resource limits
- [ ] Establish code review process
- [ ] Create backup of current state

### During Task Execution

- [ ] Monitor system resource usage
- [ ] Track file system changes
- [ ] Review command execution logs
- [ ] Verify network connections are development-only
- [ ] Check for unexpected process spawning

### After Task Completion

- [ ] Review all git commits and changes
- [ ] Verify no secrets or credentials were exposed
- [ ] Check for unexpected file modifications
- [ ] Validate acceptance criteria were met
- [ ] Run security scans on modified code
- [ ] Clean up temporary files and processes

## Common Security Risks

### 1. Credential Exposure

**Risk:** Agent accidentally logs or commits API keys, passwords, or tokens

**Mitigation:**
```bash
# Add to .gitignore
echo "*.env*" >> .gitignore
echo "secrets/" >> .gitignore
echo "credentials.json" >> .gitignore

# Use git-secrets to prevent credential commits
git secrets --install
git secrets --register-aws
git secrets --register-gcp
```

### 2. Unintended System Modifications

**Risk:** Agent modifies system files or configurations

**Mitigation:**
```yaml
# Restrict file system access
full_access:
  blocked_paths:
    - "/etc"
    - "/usr" 
    - "/var"
    - "/boot"
    - "~/.ssh"
    - "~/.aws"
    - "~/.gcp"
```

### 3. Network Security

**Risk:** Agent makes unauthorized network requests

**Mitigation:**
```bash
# Use network isolation
docker run --network none autodev:dev

# Or restrict network access
iptables -A OUTPUT -d 10.0.0.0/8 -j REJECT  # Block internal networks
```

### 4. Process Escalation  

**Risk:** Agent spawns processes with elevated privileges

**Mitigation:**
```bash
# Run with limited user privileges
useradd -m -s /bin/bash autodev
su - autodev -c "python orchestrator/app.py"

# Use containers with non-root user
FROM python:3.11
RUN useradd -m autodev
USER autodev
```

## Incident Response

### If Security Incident Occurs

1. **Immediate Actions:**
   ```bash
   # Stop all running tasks
   docker stop $(docker ps -q) || killall python
   
   # Revoke any exposed credentials immediately
   # AWS: aws iam update-access-key --access-key-id KEY --status Inactive
   # GitHub: Go to Settings -> Developer settings -> Personal access tokens
   
   # Isolate the system
   iptables -A INPUT -j DROP
   iptables -A OUTPUT -j DROP
   ```

2. **Investigation:**
   ```bash
   # Review all recent changes
   git log --since="1 hour ago" --name-status
   
   # Check process history
   history | tail -100
   
   # Review system logs  
   journalctl --since "1 hour ago"
   ```

3. **Recovery:**
   ```bash
   # Reset to known good state
   git reset --hard HEAD~10  # Adjust as needed
   
   # Clean up any temporary files
   find . -name "*.tmp" -delete
   find . -name "*.log" -exec truncate -s 0 {} \;
   ```

## Security Configuration Templates

### Development Environment

```yaml
# config/security-dev.yaml
environment: development
full_access:
  enabled: true
  max_execution_time: 3600  # 1 hour
  allowed_file_extensions: [".py", ".js", ".ts", ".yaml", ".json", ".md"]
  blocked_commands: ["rm -rf /", "sudo", "passwd", "chmod 777"]
  network_restrictions:
    allow_outbound: ["github.com", "pypi.org", "npmjs.com"]
    block_internal_ips: true
  monitoring:
    log_all_operations: true
    alert_on_suspicious_activity: true
```

### Staging Environment

```yaml
# config/security-staging.yaml  
environment: staging
full_access:
  enabled: true
  max_execution_time: 1800  # 30 minutes
  require_approval: true
  allowed_file_extensions: [".py", ".js", ".ts", ".yaml", ".json"]
  blocked_commands: ["rm", "sudo", "passwd", "chmod", "chown"]
  monitoring:
    log_all_operations: true
    require_human_review: true
```

### Production Environment

```yaml
# config/security-prod.yaml
environment: production  
full_access:
  enabled: false  # Never enable in production
  # If absolutely necessary:
  # enabled: true
  # max_execution_time: 300  # 5 minutes only
  # require_multi_approval: true
  # read_only_mode: true
```

## Compliance Considerations

### Data Privacy (GDPR/CCPA)

- Ensure agents don't process or log personal data
- Implement data minimization principles
- Use anonymized/synthetic data for development
- Enable right-to-deletion for any processed data

### Industry Standards (SOC2/ISO27001)

- Maintain audit logs of all full access operations
- Implement least privilege access controls  
- Regular security assessments of full access usage
- Incident response procedures documented

### Financial Services (PCI-DSS/SOX)

- Never enable full access in cardholder data environments
- Implement additional monitoring for financial data
- Require change management approval process
- Regular penetration testing of development environments

## Conclusion

Full access mode is a powerful capability that requires careful security consideration. By following these guidelines and implementing appropriate controls, you can harness autonomous development capabilities while maintaining security posture.

Remember: **Security is a shared responsibility**. The system provides the capabilities, but proper configuration and monitoring are essential for safe operation.