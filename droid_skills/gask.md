# gask (Gemini)
Use only when the user explicitly delegates to Gemini.
Call tool gask with args: message (required), timeout_s (optional), session_file (optional).
Then tell the user: "Gemini processing..." and end the turn.
When the user asks for the reply, call gpend (or ccb_pend_gemini).
