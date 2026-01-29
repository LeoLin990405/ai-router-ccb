# cask (Codex)
Use only when the user explicitly delegates to Codex.
Call tool cask with args: message (required), timeout_s (optional), session_file (optional).
Then tell the user: "Codex processing..." and end the turn.
When the user asks for the reply, call cpend (or ccb_pend_codex).
