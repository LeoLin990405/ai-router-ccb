"""Interactive CLI backend implementation."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from lib.common.errors import BackendError
from lib.common.logging import get_logger
from .base_backend import BackendResult
from .cli_backend import CLIBackend
from ..gateway_config import ProviderConfig
from ..models import GatewayRequest


logger = get_logger("gateway.backends.cli")


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

                message = request.message + "\n"
                process.stdin.write(message.encode("utf-8"))
                await process.stdin.drain()

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

                        if self._is_response_complete(decoded):
                            break

                except asyncio.TimeoutError:
                    pass

                latency_ms = (time.time() - start_time) * 1000
                response_text = "\n".join(response_lines)

                return BackendResult.ok(
                    response=self._clean_output(response_text)[0],
                    latency_ms=latency_ms,
                )

            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                logger.exception("Interactive CLI execution error for %s", self.config.name)
                return BackendResult.fail(
                    str(BackendError(f"Unexpected interactive backend error: {self.config.name}")),
                    latency_ms=(time.time() - start_time) * 1000,
                )

    def _is_response_complete(self, line: str) -> bool:
        """Check if the response is complete based on line content."""
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
