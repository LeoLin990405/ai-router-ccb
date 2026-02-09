#!/usr/bin/env bash
# Build unified tool index for Hivemind v1.1
set -euo pipefail

cd "$(dirname "$0")/.."
python3 - <<'PY'
from lib.skills.tool_index import ToolIndex
from lib.skills.tool_index_builder import build_index

entries = build_index()
index = ToolIndex()
index.set_entries(entries)
stats = index.stats

print(f"Tool index built: {stats['total']} entries")
print(f"  By type: {stats['by_type']}")
print(f"  Installed: {stats['installed']}")
PY
