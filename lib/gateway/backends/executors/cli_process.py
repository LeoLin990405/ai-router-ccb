"""CLI process execution helpers for transport-specific flows."""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import time
import uuid
from logging import Logger
from typing import List, Optional

from ...stream_output import StreamOutput


async def execute_with_streaming(
    cmd: List[str],
    env: dict,
    timeout: float,
    stream: StreamOutput,
    cwd: Optional[str],
    logger: Logger,
) -> Optional[tuple]:
    """Execute command with real-time streaming output."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            env=env,
            cwd=cwd,
        )

        stdout_parts = []
        stderr_parts = []
        deadline = time.time() + timeout
        chunk_buffer = ""

        async def read_stream(stream_reader, parts, stream_type):
            nonlocal chunk_buffer
            while True:
                try:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        break
                    chunk = await asyncio.wait_for(
                        stream_reader.read(1024),
                        timeout=min(5.0, remaining),
                    )
                    if not chunk:
                        break
                    decoded = chunk.decode("utf-8", errors="replace")
                    parts.append(decoded)

                    # Stream output chunks (dedupe rapid small chunks)
                    chunk_buffer += decoded
                    if len(chunk_buffer) > 100 or "\n" in chunk_buffer:
                        stream.chunk(chunk_buffer, source=stream_type)
                        chunk_buffer = ""

                except asyncio.TimeoutError:
                    continue

        # Read both streams concurrently
        await asyncio.gather(
            read_stream(process.stdout, stdout_parts, "stdout"),
            read_stream(process.stderr, stderr_parts, "stderr"),
        )

        # Flush remaining buffer
        if chunk_buffer:
            stream.chunk(chunk_buffer, source="stdout")

        # Wait for process
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

        return "".join(stdout_parts), "".join(stderr_parts), process.returncode or 0

    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
        logger.exception("Streaming execution error")
        stream.error(f"Streaming execution error: {exc}")
        return None


async def execute_with_wezterm(
    cmd: List[str],
    timeout: float,
    cwd: Optional[str],
    logger: Logger,
) -> Optional[tuple]:
    """Execute command in WezTerm pane and capture output."""
    wezterm_path = shutil_which("wezterm")
    if not wezterm_path:
        return None

    # Create a temp file to capture output
    output_file = f"/tmp/ccb_wezterm_{uuid.uuid4().hex[:8]}.txt"
    debug = os.environ.get("CCB_DEBUG", "0").lower() in ("1", "true", "yes")

    try:
        # Build command that writes output to file
        cmd_str = " ".join(f'"{chunk}"' if " " in chunk else chunk for chunk in cmd)
        if cwd:
            wrapper_cmd = (
                f'cd "{cwd}" && {cmd_str} > "{output_file}" 2>&1; '
                f'echo "CCB_EXIT_CODE:$?" >> "{output_file}"'
            )
        else:
            wrapper_cmd = f'{cmd_str} > "{output_file}" 2>&1; echo "CCB_EXIT_CODE:$?" >> "{output_file}"'

        if debug:
            logger.debug("[WezTerm] Spawning: %s", wrapper_cmd)

        spawn_result = subprocess.run(
            [wezterm_path, "cli", "spawn", "--", "bash", "-c", wrapper_cmd],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if debug:
            logger.debug(
                "[WezTerm] Spawn result: %s stdout=%s stderr=%s",
                spawn_result.returncode,
                spawn_result.stdout,
                spawn_result.stderr,
            )

        if spawn_result.returncode != 0:
            return None

        pane_id = spawn_result.stdout.strip()

        deadline = time.time() + timeout
        while time.time() < deadline:
            await asyncio.sleep(0.5)

            if os.path.exists(output_file):
                try:
                    with open(output_file, "r") as output_handle:
                        content = output_handle.read()

                    if debug:
                        logger.debug("[WezTerm] File content (%s chars): %s...", len(content), content[:200])

                    match = re.search(r"CCB_EXIT_CODE:(\d+)", content)
                    if match:
                        exit_code = int(match.group(1))
                        output = re.sub(r"CCB_EXIT_CODE:\d+\s*$", "", content)
                        if debug:
                            logger.debug("[WezTerm] Success! Exit code: %s", exit_code)
                        return output.strip(), "", exit_code
                except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                    if debug:
                        logger.exception("[WezTerm] Error reading output file")

        if debug:
            logger.debug("[WezTerm] Timeout, killing pane %s", pane_id)
        try:
            subprocess.run(
                [wezterm_path, "cli", "kill-pane", "--pane-id", pane_id],
                capture_output=True,
                timeout=2,
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            pass

        return None

    finally:
        try:
            if os.path.exists(output_file):
                os.remove(output_file)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            pass


async def execute_with_pty(
    cmd: List[str],
    env: dict,
    timeout: float,
    cwd: Optional[str],
    logger: Logger,
) -> Optional[tuple]:
    """Execute command with PTY to capture output from TTY-dependent CLIs."""
    import pty
    import select

    try:
        master_fd, slave_fd = pty.openpty()

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=slave_fd,
            stderr=slave_fd,
            stdin=asyncio.subprocess.DEVNULL,
            env=env,
            cwd=cwd,
        )

        os.close(slave_fd)

        output_parts = []
        deadline = time.time() + timeout

        loop = asyncio.get_event_loop()

        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            try:
                ready, _, _ = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: select.select([master_fd], [], [], min(1.0, remaining)),
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

            if process.returncode is not None:
                break

        os.close(master_fd)

        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

        output = "".join(output_parts)
        if os.environ.get("CCB_DEBUG", "0").lower() in ("1", "true", "yes"):
            logger.debug("[PTY] Captured output (%s chars): %s", len(output), output[:500])
        return output, "", process.returncode or 0

    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
        logger.debug("PTY execution unavailable, falling back", exc_info=True)
        return None


def shutil_which(command: str) -> Optional[str]:
    """Wrapper to allow isolated testing/mocking if needed."""
    import shutil

    return shutil.which(command)
