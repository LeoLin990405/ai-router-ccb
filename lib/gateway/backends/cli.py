"""
CLI Execution Backend for CCB Gateway.

Executes AI CLI tools as subprocesses (Codex, Gemini CLI, etc.)
"""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from typing import Optional, List

from lib.common.auth import (
    open_auth_terminal as _open_auth_terminal,
    should_auto_open_auth as _should_auto_open_auth,
)
from lib.common.errors import BackendError
from lib.common.logging import get_logger
from .extractors.cli_output import clean_cli_output, extract_thinking, process_cli_output
from .executors.cli_process import (
    execute_with_pty as _execute_with_pty_runner,
    execute_with_streaming as _execute_with_streaming_runner,
    execute_with_wezterm as _execute_with_wezterm_runner,
)
from .base_backend import BaseBackend, BackendResult
from ..models import GatewayRequest
from ..gateway_config import ProviderConfig
from ..stream_output import StreamOutput, get_stream_manager

logger = get_logger("gateway.backends.cli")


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

    async def _ensure_gemini_token(self) -> None:
        """Ensure Gemini OAuth token is valid, refresh if needed."""
        try:
            from ..gemini_auth import ensure_valid_token
            success, msg = ensure_valid_token()
            if not success:
                logger.warning("Gemini token refresh warning: %s", msg)
        except ImportError:
            logger.debug("gemini_auth module not available")
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            logger.exception("Gemini token check error")

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

        # Search in PATH first
        self._cli_path = shutil.which(cmd)
        if self._cli_path:
            return self._cli_path

        # Search in common user bin directories (may not be in PATH for background processes)
        home = os.path.expanduser("~")
        common_paths = [
            os.path.join(home, ".local", "bin"),
            os.path.join(home, ".npm-global", "bin"),
            os.path.join(home, "bin"),
            "/opt/homebrew/bin",
            "/usr/local/bin",
            os.path.join(home, ".qoder", "bin", "qodercli"),
        ]
        for path in common_paths:
            full_path = os.path.join(path, cmd)
            if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                self._cli_path = full_path
                return self._cli_path

        return None

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

    def _resolve_cwd(self) -> Optional[str]:
        """Resolve configured working directory for CLI execution."""
        if not self.config.cli_cwd:
            return None
        cwd = os.path.expanduser(os.path.expandvars(self.config.cli_cwd))
        return cwd or None

    async def execute(self, request: GatewayRequest) -> BackendResult:
        """Execute request via CLI subprocess with streaming output."""
        start_time = time.time()

        # Create stream output for real-time logging
        stream_manager = get_stream_manager()
        stream = stream_manager.create_stream(request.id, self.config.name)
        stream.status(f"Starting {self.config.name} CLI execution")

        cli = self._find_cli()
        if not cli:
            error_msg = f"CLI command not found: {self.config.cli_command}"
            stream.error(error_msg)
            stream.complete(error=error_msg)
            return BackendResult.fail(
                error_msg,
                latency_ms=(time.time() - start_time) * 1000,
            )

        try:
            # For Gemini, ensure OAuth token is valid before executing
            if self.config.name == "gemini":
                stream.status("Checking Gemini OAuth token...")
                await self._ensure_gemini_token()

            cmd = self._build_command(request.message)
            logger.debug("Provider=%s full command=%s", self.config.name, cmd)
            stream.status(f"Executing: {' '.join(cmd[:2])}...")

            # Set up environment for non-interactive execution
            env = os.environ.copy()
            env["TERM"] = "dumb"
            env["NO_COLOR"] = "1"
            env["CI"] = "1"  # Many CLIs detect CI mode and disable interactivity
            cwd = self._resolve_cwd()
            if cwd and not os.path.isdir(cwd):
                stream.status(f"Configured cwd not found: {cwd}, using default")
                cwd = None

            # Try PTY mode first for CLIs that need terminal (like Gemini)
            # This allows us to capture auth URLs that are only shown in TTY mode
            # Enable by default for Gemini since it requires TTY
            use_pty = os.environ.get("CCB_CLI_USE_PTY", "0").lower() in ("1", "true", "yes")

            # For Gemini with -p flag, use regular subprocess (no TTY needed)
            # WezTerm mode is only for interactive Gemini sessions
            use_wezterm_for_gemini = os.environ.get("CCB_GEMINI_USE_WEZTERM", "0").lower() in ("1", "true", "yes")

            if self.config.name == "gemini" and use_wezterm_for_gemini:
                debug = os.environ.get("CCB_DEBUG", "0").lower() in ("1", "true", "yes")
                if debug:
                    logger.debug("Using WezTerm for Gemini, cmd=%s", cmd)
                stream.status("Using WezTerm mode for Gemini...")
                result = await self._execute_with_wezterm(cmd, request.timeout_s or self.config.timeout_s, cwd)
                if debug:
                    logger.debug("WezTerm result=%s", result)
                if result is not None:
                    stdout, stderr, returncode = result
                    latency_ms = (time.time() - start_time) * 1000
                    backend_result = self._process_output(stdout, stderr, returncode, latency_ms, request.message)
                    if backend_result.success:
                        if backend_result.thinking:
                            stream.thinking(backend_result.thinking)
                        stream.output(backend_result.response or "")
                        stream.complete(response=backend_result.response)
                    else:
                        stream.error(backend_result.error or "Unknown error")
                        stream.complete(error=backend_result.error)
                    return backend_result
                if debug:
                    logger.debug("WezTerm returned None, falling back to subprocess")

            if use_pty:
                stream.status("Using PTY mode...")
                result = await self._execute_with_pty(cmd, env, request.timeout_s or self.config.timeout_s, cwd)
                if result is not None:
                    stdout, stderr, returncode = result
                    latency_ms = (time.time() - start_time) * 1000
                    backend_result = self._process_output(stdout, stderr, returncode, latency_ms, request.message)
                    if backend_result.success:
                        if backend_result.thinking:
                            stream.thinking(backend_result.thinking)
                        stream.output(backend_result.response or "")
                        stream.complete(response=backend_result.response)
                    else:
                        stream.error(backend_result.error or "Unknown error")
                        stream.complete(error=backend_result.error)
                    return backend_result

            # Fallback to regular subprocess with streaming
            stream.status("Starting subprocess...")
            result = await self._execute_with_streaming(cmd, env, request.timeout_s or self.config.timeout_s, stream, cwd)

            if result is not None:
                stdout, stderr, returncode = result
                latency_ms = (time.time() - start_time) * 1000
                backend_result = self._process_output(stdout, stderr, returncode, latency_ms, request.message)

                if backend_result.success:
                    if backend_result.thinking:
                        stream.thinking(backend_result.thinking)
                    stream.complete(response=backend_result.response)
                else:
                    stream.complete(error=backend_result.error)

                return backend_result

            # Fallback without streaming
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                env=env,
                cwd=cwd,
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
                error_msg = f"CLI command timed out after {request.timeout_s}s"
                stream.error(error_msg)
                if provider_name in ("gemini", "claude", "codex") and _should_auto_open_auth():
                    opened = _open_auth_terminal(provider_name)
                    if opened:
                        auth_error = f"CLI command timed out. This may be due to authentication. A terminal window has been opened for you to complete authentication for {provider_name}. Please retry after authenticating."
                        stream.complete(error=auth_error)
                        return BackendResult.fail(
                            auth_error,
                            latency_ms=latency_ms,
                            metadata={"auth_required": True, "auth_terminal_opened": True},
                        )
                stream.complete(error=error_msg)
                return BackendResult.fail(error_msg, latency_ms=latency_ms)

            latency_ms = (time.time() - start_time) * 1000
            backend_result = self._process_output(
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
                process.returncode,
                latency_ms,
                request.message,
            )

            if backend_result.success:
                if backend_result.thinking:
                    stream.thinking(backend_result.thinking)
                stream.output(backend_result.response or "")
                stream.complete(response=backend_result.response)
            else:
                stream.error(backend_result.error or "Unknown error")
                stream.complete(error=backend_result.error)

            return backend_result

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            logger.exception("Unexpected CLI backend error for %s", self.config.name)
            error_msg = str(BackendError(f"Unexpected backend error: {exc}"))
            stream.error(error_msg)
            stream.complete(error=error_msg)
            return BackendResult.fail(
                error_msg,
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def _execute_with_streaming(
        self, cmd: List[str], env: dict, timeout: float, stream: StreamOutput, cwd: Optional[str]
    ) -> Optional[tuple]:
        """Execute command with real-time streaming output."""
        return await _execute_with_streaming_runner(cmd, env, timeout, stream, cwd, logger)

    async def _execute_with_wezterm(
        self, cmd: List[str], timeout: float, cwd: Optional[str]
    ) -> Optional[tuple]:
        """Execute command in WezTerm pane and capture output."""
        return await _execute_with_wezterm_runner(cmd, timeout, cwd, logger)

    async def _execute_with_pty(
        self, cmd: List[str], env: dict, timeout: float, cwd: Optional[str]
    ) -> Optional[tuple]:
        """Execute command with PTY to capture output from TTY-dependent CLIs."""
        return await _execute_with_pty_runner(cmd, env, timeout, cwd, logger)

    def _process_output(
        self, stdout: str, stderr: str, returncode: int, latency_ms: float,
        input_text: str = ""
    ) -> BackendResult:
        """Process CLI output and convert to BackendResult."""
        return process_cli_output(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            latency_ms=latency_ms,
            input_text=input_text,
            provider_name=self.config.name,
        )

    def _extract_thinking(self, text: str) -> tuple:
        """Extract thinking/reasoning chain from text."""
        return extract_thinking(text)

    def _clean_output(self, output: str) -> tuple:
        """Clean CLI output to extract just the response."""
        return clean_cli_output(output, provider_name=self.config.name)

    async def health_check(self) -> bool:
        """Check if the CLI is available.

        For CLIs that have slow startup (like Gemini with OAuth),
        we just check if the binary exists and is executable.
        """
        cli = self._find_cli()
        if not cli:
            return False

        # Check if the file exists and is executable
        if not os.path.isfile(cli):
            return False

        if not os.access(cli, os.X_OK):
            return False

        # CLI exists and is executable - consider it healthy
        # We don't run --version because some CLIs (like Gemini) have slow startup
        return True

    async def shutdown(self) -> None:
        """No cleanup needed for CLI backend."""
        pass

def __getattr__(name: str):
    if name != "InteractiveCLIBackend":
        raise AttributeError(name)
    from .interactive_cli_backend import InteractiveCLIBackend

    return InteractiveCLIBackend


__all__ = ["CLIBackend", "InteractiveCLIBackend"]
