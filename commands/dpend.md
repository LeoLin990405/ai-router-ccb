Use `dpend` to fetch latest reply from Droid logs.

WARNING: Only use when user EXPLICITLY requests. Do NOT use proactively after dask.

Trigger conditions (ALL must match):
- User EXPLICITLY mentions dpend/Dpend
- Or user asks to "view droid reply" / "show droid response"

Execution:
- `dpend` - fetch latest reply: `Bash(dpend)`
- `dpend N` - fetch last N Q&A pairs: `Bash(dpend N)`

Output: stdout = reply text, exit code 0 = success, 2 = no reply
