Use `ask` to send a request to a provider via the unified command.

Trigger conditions (ALL must match):
- User explicitly asks to "ask <provider>" / "let <provider>" / "/ask"

Execution:
- `ask <provider> <message>`: `Bash(ask <provider> <message>)`
- Multiline: `Bash(ask <provider> <<'EOF' ... EOF)`

Notes:
- End the turn immediately after submission.
- Do NOT poll for results unless the user asks for `pend`.
