Use `pend` to fetch latest replies via the unified command.

WARNING: Only use when user EXPLICITLY requests. Do NOT use proactively after `ask`.

Trigger conditions (ALL must match):
- User explicitly mentions pend
- Or asks to "view/show <provider> reply/response"

Execution:
- `pend <provider>`: `Bash(pend <provider>)`
- `pend <provider> N`: `Bash(pend <provider> N)`

Output: stdout = reply text, exit code 0 = success, 2 = no reply
