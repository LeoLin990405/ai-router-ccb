---
name: ask
description: Send a task to a provider via the unified `ask` CLI and wait for the reply. Use only when the user explicitly delegates.
metadata:
  short-description: Ask a provider (wait for reply) via ask
---

# ask (Unified)

Use `ask` to forward the user's request to a provider.

## Execution (MANDATORY)

```bash
ask <provider> --sync -q <<'EOF'
$ARGUMENTS
EOF
```

## Workflow (Mandatory)

1. Ensure the target provider backend is up (use `ping <provider>` if needed).
2. Run the command above with the user's request.
3. **IMPORTANT**: Use `timeout_ms: 3600000` (1 hour) to allow long-running tasks.
4. DO NOT send a second request until the current one exits.

## CRITICAL: Wait Silently (READ THIS)

After running `ask`, you MUST:
- **DO NOTHING** while waiting for the command to return
- **DO NOT** check status, monitor progress, or run any other commands
- **DO NOT** read files, search code, or do "useful" work while waiting
- **DO NOT** output any text like "waiting..." or "checking..."
- **JUST WAIT** silently until ask returns with the result
