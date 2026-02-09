"""
LSP Client for CCB

Provides Language Server Protocol client functionality for code intelligence.
"""
from __future__ import annotations

import json
import subprocess
import time
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any


def _warn(message: str) -> None:
    sys.stderr.write(f"{message}\n")


@dataclass
class Location:
    """A location in a file."""
    file: str
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None


@dataclass
class TextEdit:
    """A text edit operation."""
    file: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    new_text: str


@dataclass
class SymbolInfo:
    """Information about a symbol."""
    name: str
    kind: str
    location: Location
    container: Optional[str] = None


@dataclass
class DiagnosticInfo:
    """A diagnostic message."""
    file: str
    line: int
    column: int
    message: str
    severity: str  # error, warning, info, hint


HANDLED_EXCEPTIONS = (Exception,)



try:
    from .lsp_client_core import LSPClientCoreMixin
    from .lsp_client_symbols import LSPClientSymbolsMixin
except ImportError:  # pragma: no cover - script mode
    from lsp_client_core import LSPClientCoreMixin
    from lsp_client_symbols import LSPClientSymbolsMixin


class LSPClient(LSPClientCoreMixin, LSPClientSymbolsMixin):
    """Language Server Protocol client for symbol and refactoring ops."""

    LANGUAGE_SERVERS = {
        "python": ["pylsp", "python-lsp-server"],
        "javascript": ["typescript-language-server", "typescript-language-server --stdio"],
        "typescript": ["typescript-language-server", "typescript-language-server --stdio"],
        "go": ["gopls"],
        "rust": ["rust-analyzer"],
    }


def get_lsp_client(workspace: Optional[str] = None) -> LSPClient:
    """Get the global LSP client instance."""
    global _lsp_client
    if _lsp_client is None:
        _lsp_client = LSPClient(workspace)
    return _lsp_client
