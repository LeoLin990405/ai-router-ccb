# oask (OpenCode)
Use only when the user explicitly delegates to OpenCode.
Call tool oask with args: message (required), timeout_s (optional), session_file (optional).
Then tell the user: "OpenCode processing..." and end the turn.
When the user asks for the reply, call opend (or ccb_pend_opencode).
