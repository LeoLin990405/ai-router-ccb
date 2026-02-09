"""
askd_runtime - Runtime utilities for daemon management.

This module provides functions for managing daemon runtime state.
"""

from __future__ import annotations

import os
from pathlib import Path


def state_file_path(daemon_key: str) -> Path:
    """
    Get the path to the state file for a daemon.
    
    Args:
        daemon_key: Unique key identifying the daemon
        
    Returns:
        Path to the state file
    """
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "ccb"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{daemon_key}_state.json"