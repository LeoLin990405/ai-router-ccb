---
name: ping
description: Check provider connectivity via ping <provider>. Use only when the user explicitly asks.
metadata:
  short-description: Ping a provider via ping
---

# Ping Provider

Check connectivity for a provider via the unified `ping` command.

## Execution (MANDATORY)

```
Bash(ping $ARGUMENTS)
```

## Rules

- Arguments must start with the provider name (e.g., `gemini`).
- Only use when the user explicitly asks for a health check.
