"""Unified logging helpers for Hivemind."""

from __future__ import annotations

import logging
import sys
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = False,
) -> logging.Logger:
    """Configure and return the root Hivemind logger."""
    root = logging.getLogger("hivemind")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if root.handlers:
        return root

    if json_format:
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
    else:
        fmt = "[%(asctime)s] %(levelname)s [%(name)s] %(message)s"

    datefmt = "%H:%M:%S"

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        root.addHandler(file_handler)

    return root


def get_logger(name: str) -> logging.Logger:
    """Get a module logger under the ``hivemind`` namespace."""
    root = logging.getLogger("hivemind")
    if not root.handlers:
        setup_logging()
    return logging.getLogger(f"hivemind.{name}")
