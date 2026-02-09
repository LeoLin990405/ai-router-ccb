"""Shared project path helpers."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """Return the shared data directory, creating it if needed."""
    path = project_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_gateway_db_path() -> Path:
    """Default SQLite path for gateway state."""
    return data_dir() / "hivemind.db"


def default_performance_db_path() -> Path:
    """Default SQLite path for performance metrics."""
    return data_dir() / "performance.db"

