"""Auto-split mixins for LSPClient."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .lsp_client import (
        HANDLED_EXCEPTIONS,
        DiagnosticInfo,
        Location,
        SymbolInfo,
        TextEdit,
        _warn,
    )
except ImportError:  # pragma: no cover - script mode
    from lsp_client import (
        HANDLED_EXCEPTIONS,
        DiagnosticInfo,
        Location,
        SymbolInfo,
        TextEdit,
        _warn,
    )


class LSPClientSymbolsMixin:
    """Mixin methods extracted from LSPClient."""

    def get_document_symbols(self, file: str) -> List[SymbolInfo]:
        """
        Get all symbols in a document.

        Args:
            file: File path

        Returns:
            List of symbols
        """
        language = self._get_language(file)
        if not language:
            return []

        proc = self._start_server(language)
        if not proc:
            return []

        self._open_document(proc, file)

        response = self._send_request(proc, "textDocument/documentSymbol", {
            "textDocument": {"uri": f"file://{file}"},
        })

        if not response or "result" not in response:
            return []

        symbols = []
        self._parse_symbols(file, response["result"] or [], symbols)

        return symbols

    def _parse_symbols(
        self,
        file: str,
        items: List[Dict],
        symbols: List[SymbolInfo],
        container: Optional[str] = None,
    ) -> None:
        """Parse symbol information recursively."""
        symbol_kinds = {
            1: "file", 2: "module", 3: "namespace", 4: "package",
            5: "class", 6: "method", 7: "property", 8: "field",
            9: "constructor", 10: "enum", 11: "interface", 12: "function",
            13: "variable", 14: "constant", 15: "string", 16: "number",
            17: "boolean", 18: "array", 19: "object", 20: "key",
            21: "null", 22: "enum_member", 23: "struct", 24: "event",
            25: "operator", 26: "type_parameter",
        }

        for item in items:
            name = item.get("name", "")
            kind = symbol_kinds.get(item.get("kind", 0), "unknown")

            # Handle both DocumentSymbol and SymbolInformation
            if "range" in item:
                start = item["range"]["start"]
                location = Location(
                    file=file,
                    line=start["line"] + 1,
                    column=start["character"] + 1,
                )
            elif "location" in item:
                loc = item["location"]
                start = loc["range"]["start"]
                location = Location(
                    file=loc["uri"].replace("file://", ""),
                    line=start["line"] + 1,
                    column=start["character"] + 1,
                )
            else:
                continue

            symbols.append(SymbolInfo(
                name=name,
                kind=kind,
                location=location,
                container=container,
            ))

            # Recurse into children
            if "children" in item:
                self._parse_symbols(file, item["children"], symbols, name)

