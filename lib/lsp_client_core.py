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


class LSPClientCoreMixin:
    """Mixin methods extracted from LSPClient."""

    def __init__(self, workspace: Optional[str] = None):
        """
        Initialize the LSP client.

        Args:
            workspace: Workspace root directory
        """
        self.workspace = workspace or str(Path.cwd())
        self._servers: Dict[str, subprocess.Popen] = {}
        self._request_id = 0

    def _get_language(self, file_path: str) -> Optional[str]:
        """Determine the language from file extension."""
        ext = Path(file_path).suffix.lower()
        for lang, config in self.LANGUAGE_SERVERS.items():
            if ext in config["extensions"]:
                return lang
        return None

    def _start_server(self, language: str) -> Optional[subprocess.Popen]:
        """Start an LSP server for a language."""
        if language in self._servers:
            proc = self._servers[language]
            if proc.poll() is None:
                return proc

        config = self.LANGUAGE_SERVERS.get(language)
        if not config:
            return None

        try:
            proc = subprocess.Popen(
                config["command"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._servers[language] = proc

            # Initialize the server
            self._send_request(proc, "initialize", {
                "processId": None,
                "rootUri": f"file://{self.workspace}",
                "capabilities": {},
            })

            # Send initialized notification
            self._send_notification(proc, "initialized", {})

            return proc

        except HANDLED_EXCEPTIONS as e:
            _warn(f"Failed to start LSP server for {language}: {e}")
            return None

    def _send_request(
        self,
        proc: subprocess.Popen,
        method: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Send a request to the LSP server."""
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        content = json.dumps(request)
        message = f"Content-Length: {len(content)}\r\n\r\n{content}"

        try:
            proc.stdin.write(message.encode())
            proc.stdin.flush()

            # Read response
            response = self._read_response(proc)
            return response

        except HANDLED_EXCEPTIONS as e:
            _warn(f"LSP request failed: {e}")
            return None

    def _send_notification(
        self,
        proc: subprocess.Popen,
        method: str,
        params: Dict[str, Any],
    ) -> None:
        """Send a notification to the LSP server."""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        content = json.dumps(notification)
        message = f"Content-Length: {len(content)}\r\n\r\n{content}"

        try:
            proc.stdin.write(message.encode())
            proc.stdin.flush()
        except HANDLED_EXCEPTIONS:
            pass

    def _read_response(self, proc: subprocess.Popen, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """Read a response from the LSP server."""
        import select

        start_time = time.time()

        while time.time() - start_time < timeout:
            ready, _, _ = select.select([proc.stdout], [], [], 0.1)
            if not ready:
                continue

            # Read headers
            headers = {}
            while True:
                line = proc.stdout.readline().decode()
                if line == "\r\n" or line == "\n":
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()

            # Read content
            content_length = int(headers.get("content-length", 0))
            if content_length > 0:
                content = proc.stdout.read(content_length).decode()
                response = json.loads(content)

                # Skip notifications, wait for response
                if "id" in response:
                    return response

        return None

    def find_references(
        self,
        file: str,
        line: int,
        column: int,
        include_declaration: bool = True,
    ) -> List[Location]:
        """
        Find all references to a symbol.

        Args:
            file: File path
            line: Line number (1-based)
            column: Column number (1-based)
            include_declaration: Include the declaration

        Returns:
            List of locations
        """
        language = self._get_language(file)
        if not language:
            return []

        proc = self._start_server(language)
        if not proc:
            return []

        # Open the document
        self._open_document(proc, file)

        # Send references request
        response = self._send_request(proc, "textDocument/references", {
            "textDocument": {"uri": f"file://{file}"},
            "position": {"line": line - 1, "character": column - 1},
            "context": {"includeDeclaration": include_declaration},
        })

        if not response or "result" not in response:
            return []

        locations = []
        for loc in response["result"] or []:
            uri = loc["uri"].replace("file://", "")
            start = loc["range"]["start"]
            end = loc["range"]["end"]

            locations.append(Location(
                file=uri,
                line=start["line"] + 1,
                column=start["character"] + 1,
                end_line=end["line"] + 1,
                end_column=end["character"] + 1,
            ))

        return locations

    def get_definition(
        self,
        file: str,
        line: int,
        column: int,
    ) -> Optional[Location]:
        """
        Get the definition of a symbol.

        Args:
            file: File path
            line: Line number (1-based)
            column: Column number (1-based)

        Returns:
            Location of the definition
        """
        language = self._get_language(file)
        if not language:
            return None

        proc = self._start_server(language)
        if not proc:
            return None

        self._open_document(proc, file)

        response = self._send_request(proc, "textDocument/definition", {
            "textDocument": {"uri": f"file://{file}"},
            "position": {"line": line - 1, "character": column - 1},
        })

        if not response or "result" not in response:
            return None

        result = response["result"]
        if not result:
            return None

        # Handle both single location and array
        if isinstance(result, list):
            result = result[0] if result else None

        if not result:
            return None

        uri = result["uri"].replace("file://", "")
        start = result["range"]["start"]

        return Location(
            file=uri,
            line=start["line"] + 1,
            column=start["character"] + 1,
        )

    def rename_symbol(
        self,
        file: str,
        line: int,
        column: int,
        new_name: str,
    ) -> List[TextEdit]:
        """
        Rename a symbol across files.

        Args:
            file: File path
            line: Line number (1-based)
            column: Column number (1-based)
            new_name: New name for the symbol

        Returns:
            List of text edits to apply
        """
        language = self._get_language(file)
        if not language:
            return []

        proc = self._start_server(language)
        if not proc:
            return []

        self._open_document(proc, file)

        response = self._send_request(proc, "textDocument/rename", {
            "textDocument": {"uri": f"file://{file}"},
            "position": {"line": line - 1, "character": column - 1},
            "newName": new_name,
        })

        if not response or "result" not in response:
            return []

        result = response["result"]
        if not result:
            return []

        edits = []
        changes = result.get("changes", {})

        for uri, file_edits in changes.items():
            file_path = uri.replace("file://", "")
            for edit in file_edits:
                start = edit["range"]["start"]
                end = edit["range"]["end"]

                edits.append(TextEdit(
                    file=file_path,
                    start_line=start["line"] + 1,
                    start_column=start["character"] + 1,
                    end_line=end["line"] + 1,
                    end_column=end["character"] + 1,
                    new_text=edit["newText"],
                ))

        return edits

    def _open_document(self, proc: subprocess.Popen, file: str) -> None:
        """Open a document in the LSP server."""
        try:
            content = Path(file).read_text()
        except HANDLED_EXCEPTIONS:
            content = ""

        language = self._get_language(file) or "plaintext"

        self._send_notification(proc, "textDocument/didOpen", {
            "textDocument": {
                "uri": f"file://{file}",
                "languageId": language,
                "version": 1,
                "text": content,
            },
        })

    def shutdown(self) -> None:
        """Shutdown all LSP servers."""
        for lang, proc in self._servers.items():
            try:
                self._send_request(proc, "shutdown", {})
                self._send_notification(proc, "exit", {})
                proc.wait(timeout=5)
            except HANDLED_EXCEPTIONS:
                proc.kill()

        self._servers.clear()


# Singleton instance
_lsp_client: Optional[LSPClient] = None


