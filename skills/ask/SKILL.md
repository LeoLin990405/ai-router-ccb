---
name: ask
description: Async via ask <provider> <message>; use only when user explicitly delegates to a provider.
metadata:
  short-description: Ask a provider asynchronously via ask
---

# Ask Provider (Async)

Send the user's request to a provider via the unified `ask` command.

## Execution (MANDATORY)

```
Bash(ask <<'EOF'
$ARGUMENTS
EOF
, run_in_background=true)
```

## Rules

- Arguments must start with the provider name (e.g., `gemini ...`).
- After running `ask`, say "<Provider> processing..." and end your turn.
- Do not poll or use `pend` unless the user explicitly asks.
