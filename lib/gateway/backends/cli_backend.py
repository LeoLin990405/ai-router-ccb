"""
CLI Execution Backend for CCB Gateway.

Executes AI CLI tools as subprocesses (Codex, Gemini CLI, etc.)
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import time
import webbrowser
from typing import Optional, List

from .base_backend import BaseBackend, BackendResult
from ..models import GatewayRequest
from ..gateway_config import ProviderConfig


# Patterns for detecting OAuth/auth URLs
AUTH_URL_PATTERNS = [
    r'https://accounts\.google\.com/o/oauth2[^\s\'"]+',
    r'https://[^\s\'"]*auth[^\s\'"]*code[^\s\'"]*',
    r'https://[^\s\'"]*authorize[^\s\'"]*',
]


def _should_auto_open_auth() -> bool:
    """Check if auto-open auth is enabled."""
    val = os.environ.get("CCB_AUTO_OPEN_AUTH", "1").lower()
    return val in ("1", "true", "yes", "on")


def _extract_auth_url(text: str) -> Optional[str]:
    """Extract OAuth/auth URL from text."""
    for pattern in AUTH_URL_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def _open_auth_url(url: str) -> bool:
    """Open auth URL in browser."""
    try:
        # Try webbrowser module first
        webbrowser.open(url)
        return True
    except Exception:
        pass

    try:
        # Fallback to system open command (macOS)
        subprocess.run(["open", url], check=True, capture_output=True)
        return True
    except Exception:
        pass

    return False


def _open_auth_terminal(provider: str) -> bool:
    """Open a new terminal window for authentication."""
    auth_commands = {
        "gemini": "gemini auth login",
        "claude": "claude auth login",
        "codex": "codex auth login",
    }

    cmd = auth_commands.get(provider)
    if not cmd:
        return False

    try:
        # Try WezTerm first
        wezterm_path = shutil.which("wezterm")
        if wezterm_path:
            subprocess.Popen(
                [wezterm_path, "cli", "spawn", "--", "bash", "-c", f"{cmd}; echo 'Press Enter to close'; read"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
    except Exception:
        pass

    try:
        # Fallback to macOS Terminal
        script = f'''
        tell application "Terminal"
            activate
            do script "{cmd}"
        end tell
        '''
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        return True
    except Exception:
        pass

    return False


class CLIBackend(BaseBackend):
    """
    CLI execution backend for command-line AI tools.

    Supports:
    - Codex CLI
    - Gemini CLI
    - OpenCode
    - iFlow
    - Kimi
    - Qwen
    - Any CLI tool that accepts input via stdin or arguments
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._cli_path: Optional[str] = None

    def _find_cli(self) -> Optional[str]:
        """Find the CLI executable."""
        if self._cli_path:
            return self._cli_path

        cmd = self.config.cli_command
        if not cmd:
            return None

        # Check if it's an absolute path
        if os.path.isabs(cmd) and os.path.isfile(cmd):
            self._cli_path = cmd
            return self._cli_path

        # Search in PATH
        self._cli_path = shutil.which(cmd)
        return self._cli_path

    def _build_command(self, message: str) -> List[str]:
        """Build the command line arguments."""
        cli = self._find_cli()
        if not cli:
            raise ValueError(f"CLI command not found: {self.config.cli_command}")

        cmd = [cli]

        # Add configured arguments
        if self.config.cli_args:
            cmd.extend(self.config.cli_args)

        # Add the message as the final argument
        # Most CLI tools accept the prompt as the last argument
        cmd.append(message)

        return cmd

    async def execute(self, request: GatewayRequest) -> BackendResult:
        """Execute request via CLI subprocess."""
        start_time = time.time()

        cli = self._find_cli()
        if not cli:
            return BackendResult.fail(
                f"CLI command not found: {self.config.cli_command}",
                latency_ms=(time.time() - start_time) * 1000,
            )

        try:
            cmd = self._build_command(request.message)

            # Set up environment for non-interactive execution
            env = os.environ.copy()
            env["TERM"] = "dumb"
            env["NO_COLOR"] = "1"
            env["CI"] = "1"  # Many CLIs detect CI mode and disable interactivity

            # Try PTY mode first for CLIs that need terminal (like Gemini)
            # This allows us to capture auth URLs that are only shown in TTY mode
            # Disabled by default as it doesn't work reliably
            use_pty = os.environ.get("CCB_CLI_USE_PTY", "0").lower() in ("1", "true", "yes")

            if use_pty:
                result = await self._execute_with_pty(cmd, env, request.timeout_s or self.config.timeout_s)
                if result is not None:
                    stdout, stderr, returncode = result
                    latency_ms = (time.time() - start_time) * 1000
                    return self._process_output(stdout, stderr, returncode, latency_ms)

            # Fallback to regular subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=request.timeout_s or self.config.timeout_s,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                # On timeout, check if this provider needs auth
                latency_ms = (time.time() - start_time) * 1000
                provider_name = self.config.name
                if provider_name in ("gemini", "claude", "codex") and _should_auto_open_auth():
                    opened = _open_auth_terminal(provider_name)
                    if opened:
                        return BackendResult.fail(
                            f"CLI command timed out. This may be due to authentication. A terminal window has been opened for you to complete authentication for {provider_name}. Please retry after authenticating.",
                            latency_ms=latency_ms,
                            metadata={"auth_required": True, "auth_terminal_opened": True},
                        )
                return BackendResult.fail(
                    f"CLI command timed out after {request.timeout_s}s",
                    latency_ms=latency_ms,
                )

            latency_ms = (time.time() - start_time) * 1000
            return self._process_output(
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
                process.returncode,
                latency_ms,
            )

        except Exception as e:
            return BackendResult.fail(
                str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def _execute_with_pty(
        self, cmd: List[str], env: dict, timeout: float
    ) -> Optional[tuple]:
        """Execute command with PTY to capture output from TTY-dependent CLIs."""
        import pty
        import select

        try:
            # Create PTY
            master_fd, slave_fd = pty.openpty()

            # Start process with PTY
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=slave_fd,
                stderr=slave_fd,
                stdin=asyncio.subprocess.DEVNULL,
                env=env,
            )

            os.close(slave_fd)

            # Read output with timeout
            output_parts = []
            deadline = time.time() + timeout

            loop = asyncio.get_event_loop()

            while time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break

                # Use select to check if data is available
                try:
                    ready, _, _ = await asyncio.wait_for(
                        loop.run_in_executor(
                            None,
                            lambda: select.select([master_fd], [], [], min(1.0, remaining))
                        ),
                        timeout=min(2.0, remaining),
                    )
                except asyncio.TimeoutError:
                    continue

                if master_fd in ready:
                    try:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        output_parts.append(data.decode("utf-8", errors="replace"))
                    except OSError:
                        break

                # Check if process has finished
                if process.returncode is not None:
                    break

            os.close(master_fd)

            # Wait for process to finish
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

            output = "".join(output_parts)
            return output, "", process.returncode or 0

        except Exception as e:
            # PTY not available or failed, return None to use fallback
            return None

    def _process_output(
        self, stdout: str, stderr: str, returncode: int, latency_ms: float
    ) -> BackendResult:
        """Process CLI output and check for auth URLs."""
        stdout = stdout.strip()
        stderr = stderr.strip()

        # Check for auth URL in output (stdout or stderr)
        combined_output = stdout + "\n" + stderr
        auth_url = _extract_auth_url(combined_output)
        if auth_url:
            if _should_auto_open_auth():
                opened = _open_auth_url(auth_url)
                auth_msg = f"Authentication required. {'Browser opened automatically.' if opened else 'Please open this URL:'}\n{auth_url}"
            else:
                auth_msg = f"Authentication required. Please open this URL:\n{auth_url}"
            return BackendResult.fail(
                auth_msg,
                latency_ms=latency_ms,
                metadata={"auth_required": True, "auth_url": auth_url},
            )

        # Check for auth-related errors (timeout with no output often means auth needed)
        auth_indicators = [
            "authorization",
            "authenticate",
            "login required",
            "not logged in",
            "credentials",
            "token expired",
            "unauthorized",
        ]
        if returncode != 0 or (not stdout and not stderr):
            combined_lower = combined_output.lower()
            needs_auth = any(ind in combined_lower for ind in auth_indicators)

            # If no output and timeout, likely auth issue for Gemini
            if not stdout and not stderr and self.config.name == "gemini":
                needs_auth = True

            if needs_auth and _should_auto_open_auth():
                opened = _open_auth_terminal(self.config.name)
                if opened:
                    return BackendResult.fail(
                        f"Authentication required for {self.config.name}. A terminal window has been opened for you to complete authentication. Please retry after authenticating.",
                        latency_ms=latency_ms,
                        metadata={"auth_required": True, "auth_terminal_opened": True},
                    )

        # Check return code
        if returncode != 0:
            error_msg = stderr if stderr else f"CLI exited with code {returncode}"
            return BackendResult.fail(error_msg, latency_ms=latency_ms)

        # Try to extract just the response if there's metadata
        response_text = self._clean_output(stdout)

        return BackendResult.ok(
            response=response_text,
            latency_ms=latency_ms,
            metadata={"exit_code": returncode},
        )

    def _clean_output(self, output: str) -> str:
        """Clean CLI output to extract just the response."""
        # Check if output is JSONL (Codex --json mode or OpenCode --format json)
        lines = output.strip().split("\n")

        # Try to parse as JSONL and extract response text
        import json
        text_parts = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # Codex JSON format: look for agent_message
                if data.get("type") == "item.completed":
                    item = data.get("item", {})
                    if item.get("type") == "agent_message":
                        return item.get("text", "")
                # OpenCode JSON format: look for text type
                if data.get("type") == "text":
                    part = data.get("part", {})
                    if part.get("type") == "text" and part.get("text"):
                        text_parts.append(part.get("text"))
            except json.JSONDecodeError:
                continue

        # Return collected text parts from OpenCode format
        if text_parts:
            return "\n".join(text_parts)

        # Fallback: clean regular output
        cleaned_lines = []
        for line in lines:
            # Skip common status lines
            if any(skip in line.lower() for skip in [
                "loading",
                "initializing",
                "connecting",
                "thinking...",
                "processing...",
                "mcp:",
                "--------",
                "workdir:",
                "model:",
                "provider:",
                "approval:",
                "sandbox:",
                "reasoning effort:",
                "reasoning summaries:",
                "session id:",
                "tokens used",
            ]):
                continue
            # Skip lines that look like metadata
            if line.startswith("OpenAI") or line.startswith("user"):
                continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    async def health_check(self) -> bool:
        """Check if the CLI is available."""
        cli = self._find_cli()
        if not cli:
            return False

        try:
            # Try to run with --version or --help to check if it works
            process = await asyncio.create_subprocess_exec(
                cli, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                await asyncio.wait_for(process.communicate(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                return False

            # Some CLIs don't support --version, so we accept any exit code
            # as long as the process ran
            return True

        except Exception:
            return False

    async def shutdown(self) -> None:
        """No cleanup needed for CLI backend."""
        pass


class InteractiveCLIBackend(CLIBackend):
    """
    Backend for interactive CLI tools that maintain a session.

    This is useful for tools like Codex that can maintain context
    across multiple requests.
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._process: Optional[asyncio.subprocess.Process] = None
        self._lock = asyncio.Lock()

    async def _ensure_process(self) -> asyncio.subprocess.Process:
        """Ensure the interactive process is running."""
        if self._process is None or self._process.returncode is not None:
            cli = self._find_cli()
            if not cli:
                raise ValueError(f"CLI command not found: {self.config.cli_command}")

            cmd = [cli]
            if self.config.cli_args:
                cmd.extend(self.config.cli_args)

            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )

        return self._process

    async def execute(self, request: GatewayRequest) -> BackendResult:
        """Execute request via interactive CLI session."""
        start_time = time.time()

        async with self._lock:
            try:
                process = await self._ensure_process()

                # Send message to stdin
                message = request.message + "\n"
                process.stdin.write(message.encode("utf-8"))
                await process.stdin.drain()

                # Read response (this is tricky for interactive CLIs)
                # We need to detect when the response is complete
                response_lines = []
                timeout = request.timeout_s or self.config.timeout_s

                try:
                    while True:
                        line = await asyncio.wait_for(
                            process.stdout.readline(),
                            timeout=timeout,
                        )
                        if not line:
                            break

                        decoded = line.decode("utf-8", errors="replace").rstrip()
                        response_lines.append(decoded)

                        # Check for end-of-response markers
                        if self._is_response_complete(decoded):
                            break

                except asyncio.TimeoutError:
                    pass

                latency_ms = (time.time() - start_time) * 1000
                response_text = "\n".join(response_lines)

                return BackendResult.ok(
                    response=self._clean_output(response_text),
                    latency_ms=latency_ms,
                )

            except Exception as e:
                return BackendResult.fail(
                    str(e),
                    latency_ms=(time.time() - start_time) * 1000,
                )

    def _is_response_complete(self, line: str) -> bool:
        """Check if the response is complete based on the line content."""
        # Override in subclasses for specific CLI tools
        # Common patterns: prompt characters, empty lines after content
        return line.endswith("> ") or line.endswith(">>> ")

    async def shutdown(self) -> None:
        """Terminate the interactive process."""
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None
