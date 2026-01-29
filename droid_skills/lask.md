# lask (Claude)
Use only when the user explicitly delegates to Claude.
Call tool lask with args: message (required), timeout_s (optional), session_file (optional).
Then tell the user: "Claude processing..." and end the turn.
When the user asks for the reply, call lpend (or ccb_pend_claude).
