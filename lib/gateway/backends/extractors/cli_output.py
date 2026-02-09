"""Helpers for normalizing and processing CLI backend output."""

from __future__ import annotations

import json
import re
from typing import Optional, Tuple

from lib.common.auth import (
    extract_auth_url,
    is_auth_required,
    open_auth_terminal,
    open_auth_url,
    should_auto_open_auth,
)
from lib.common.tokens import estimate_input_output_tokens, estimate_tokens
from ..base_backend import BackendResult


def extract_thinking(text: str) -> Tuple[str, Optional[str]]:
    """Extract reasoning/thinking fragments and return cleaned text."""
    thinking_parts = []
    cleaned_text = text

    thinking_pattern = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL | re.IGNORECASE)
    matches = thinking_pattern.findall(text)
    if matches:
        thinking_parts.extend(matches)
        cleaned_text = thinking_pattern.sub("", cleaned_text)

    ant_pattern = re.compile(r"<antThinking>(.*?)</antThinking>", re.DOTALL | re.IGNORECASE)
    matches = ant_pattern.findall(cleaned_text)
    if matches:
        thinking_parts.extend(matches)
        cleaned_text = ant_pattern.sub("", cleaned_text)

    bracket_pattern = re.compile(r"\[Thinking\](.*?)\[/Thinking\]", re.DOTALL | re.IGNORECASE)
    matches = bracket_pattern.findall(cleaned_text)
    if matches:
        thinking_parts.extend(matches)
        cleaned_text = bracket_pattern.sub("", cleaned_text)

    lines = cleaned_text.split("\n")
    new_lines = []
    in_thinking = False
    thinking_buffer = []

    for line in lines:
        lower_line = line.lower().strip()
        if lower_line.startswith("thinking:") or lower_line.startswith("reasoning:"):
            in_thinking = True
            thinking_buffer.append(line)
        elif in_thinking and (line.startswith("  ") or line.startswith("\t") or not line.strip()):
            thinking_buffer.append(line)
        else:
            if thinking_buffer:
                thinking_parts.append("\n".join(thinking_buffer))
                thinking_buffer = []
            in_thinking = False
            new_lines.append(line)

    if thinking_buffer:
        thinking_parts.append("\n".join(thinking_buffer))

    cleaned_text = "\n".join(new_lines)
    thinking = "\n\n---\n\n".join(thinking_parts) if thinking_parts else None
    return cleaned_text.strip(), thinking


def clean_cli_output(output: str, provider_name: str) -> Tuple[str, Optional[str]]:
    """Clean raw CLI output and optionally extract reasoning content."""
    if provider_name == "qoder":
        cleaned_lines = []
        for line in output.strip().split("\n"):
            if any(
                skip in line.lower()
                for skip in [
                    "loading",
                    "context engine",
                    "analyzing",
                    "mcp:",
                    "job id:",
                ]
            ):
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip(), None

    lines = output.strip().split("\n")
    text_parts = []
    thinking_parts = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(data, dict):
            continue

        if data.get("type") == "item.completed":
            item = data.get("item", {})
            if item.get("type") == "agent_message":
                text_parts.append(item.get("text", ""))
            elif item.get("type") == "thinking":
                thinking_parts.append(item.get("text", ""))

        if data.get("type") == "thinking":
            thinking_parts.append(data.get("text", ""))

        if data.get("type") == "text":
            part = data.get("part", {})
            if part.get("type") == "text" and part.get("text"):
                text_parts.append(part.get("text"))
            elif part.get("type") == "thinking" and part.get("text"):
                thinking_parts.append(part.get("text"))

    if text_parts:
        response = "\n".join(text_parts)
        thinking = "\n\n---\n\n".join(thinking_parts) if thinking_parts else None
        return response, thinking

    json_objects = []
    i = 0
    while i < len(output):
        if output[i] == "{":
            brace_count = 0
            start = i
            for j in range(i, len(output)):
                if output[j] == "{":
                    brace_count += 1
                elif output[j] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_objects.append(output[start : j + 1])
                        i = j
                        break
        i += 1

    for json_str in json_objects:
        try:
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and "response" in data and "error" not in data:
            return data["response"], None

    cleaned_text, thinking = extract_thinking(output)

    cleaned_lines = []
    for line in cleaned_text.split("\n"):
        if any(
            skip in line.lower()
            for skip in [
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
                "loaded cached credentials",
                "hook registry initialized",
                "credentials loaded",
            ]
        ):
            continue
        if line.startswith("OpenAI") or line.startswith("user"):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip(), thinking


def _snip(text: str, limit: int = 1200) -> str:
    """Trim long error text while keeping the latest diagnostic context."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def process_cli_output(
    *,
    stdout: str,
    stderr: str,
    returncode: int,
    latency_ms: float,
    input_text: str,
    provider_name: str,
) -> BackendResult:
    """Convert raw CLI process output into ``BackendResult``."""
    stdout = stdout.strip()
    stderr = stderr.strip()

    combined_output = stdout + "\n" + stderr
    auth_url = extract_auth_url(combined_output)
    if auth_url:
        if should_auto_open_auth():
            opened = open_auth_url(auth_url)
            auth_msg = (
                f"Authentication required. {'Browser opened automatically.' if opened else 'Please open this URL:'}\n{auth_url}"
            )
        else:
            auth_msg = f"Authentication required. Please open this URL:\n{auth_url}"

        return BackendResult.fail(
            auth_msg,
            latency_ms=latency_ms,
            metadata={"auth_required": True, "auth_url": auth_url},
        )

    if returncode != 0 or (not stdout and not stderr):
        needs_auth = is_auth_required(combined_output, provider_name)

        if not stdout and not stderr and provider_name == "gemini":
            needs_auth = True

        if needs_auth and should_auto_open_auth() and open_auth_terminal(provider_name):
            return BackendResult.fail(
                (
                    f"Authentication required for {provider_name}. "
                    "A terminal window has been opened for you to complete authentication. "
                    "Please retry after authenticating."
                ),
                latency_ms=latency_ms,
                metadata={"auth_required": True, "auth_terminal_opened": True},
            )

    response_text, thinking = clean_cli_output(stdout, provider_name=provider_name)
    raw_output = stdout

    if response_text:
        token_stats = estimate_input_output_tokens(input_text, response_text)
        input_tokens = token_stats["input_tokens"]
        output_tokens = token_stats["output_tokens"]
        total_tokens = token_stats["total_tokens"]

        return BackendResult.ok(
            response=response_text,
            latency_ms=latency_ms,
            tokens_used=total_tokens,
            metadata={
                "exit_code": returncode,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "tokens_estimated": True,
            },
            thinking=thinking,
            raw_output=raw_output,
        )

    if returncode != 0:
        detail_parts = []
        if stderr:
            detail_parts.append(f"stderr:\n{_snip(stderr)}")
        if stdout and (not stderr or _snip(stdout) != _snip(stderr)):
            detail_parts.append(f"stdout:\n{_snip(stdout)}")

        detail = "\n\n".join(part for part in detail_parts if part).strip()
        error_msg = f"CLI exited with code {returncode}\n{detail}" if detail else f"CLI exited with code {returncode}"
        return BackendResult.fail(error_msg, latency_ms=latency_ms)

    input_tokens = estimate_tokens(input_text)
    return BackendResult.ok(
        response="",
        latency_ms=latency_ms,
        tokens_used=input_tokens,
        metadata={
            "exit_code": returncode,
            "input_tokens": input_tokens,
            "output_tokens": 0,
            "tokens_estimated": True,
        },
        raw_output=raw_output,
    )
