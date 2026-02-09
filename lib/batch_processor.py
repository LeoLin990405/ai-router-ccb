"""
Batch Processing System for CCB

Supports batch submission and parallel execution of multiple tasks.
Persists batch jobs to SQLite for durability across restarts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable, Any
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import time
import uuid
import json
import sqlite3
from pathlib import Path


HANDLED_EXCEPTIONS = (Exception,)


class BatchStatus(Enum):
    """Status of a batch job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class BatchTask:
    """A single task within a batch."""
    id: str
    message: str
    provider: Optional[str] = None
    status: BatchStatus = BatchStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "message": self.message[:100] + "..." if len(self.message) > 100 else self.message,
            "provider": self.provider,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


@dataclass
class BatchJob:
    """A batch job containing multiple tasks."""
    id: str
    tasks: List[BatchTask]
    created_at: float
    completed_at: Optional[float] = None
    status: BatchStatus = BatchStatus.PENDING
    default_provider: Optional[str] = None

    @property
    def progress(self) -> float:
        """Calculate progress as percentage."""
        if not self.tasks:
            return 0.0
        completed = sum(1 for t in self.tasks if t.status in [BatchStatus.COMPLETED, BatchStatus.FAILED])
        return completed / len(self.tasks)

    @property
    def successful_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == BatchStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == BatchStatus.FAILED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status.value,
            "task_count": len(self.tasks),
            "progress": f"{self.progress * 100:.1f}%",
            "successful": self.successful_count,
            "failed": self.failed_count,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }



try:
    from .batch_processor_core import BatchProcessorCoreMixin
    from .batch_processor_exec import BatchProcessorExecMixin
except ImportError:  # pragma: no cover - script mode
    from batch_processor_core import BatchProcessorCoreMixin
    from batch_processor_exec import BatchProcessorExecMixin


class BatchProcessor(BatchProcessorCoreMixin, BatchProcessorExecMixin):
    """Processes batch jobs with persistent storage and worker pools."""


def format_batch_status(job: BatchJob, verbose: bool = False) -> str:
    """Format batch job status for display."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"Batch Job: {job.id}")
    lines.append("=" * 60)
    lines.append(f"Status:      {job.status.value}")
    lines.append(f"Progress:    {job.progress * 100:.1f}%")
    lines.append(f"Tasks:       {len(job.tasks)}")
    lines.append(f"Successful:  {job.successful_count}")
    lines.append(f"Failed:      {job.failed_count}")

    if job.completed_at:
        duration = job.completed_at - job.created_at
        lines.append(f"Duration:    {duration:.1f}s")

    if verbose:
        lines.append("-" * 60)
        lines.append(f"{'Task ID':<15} {'Status':<12} {'Latency':<10} {'Provider':<10}")
        lines.append("-" * 60)
        for task in job.tasks:
            latency = f"{task.latency_ms:.0f}ms" if task.latency_ms else "-"
            provider = task.provider or "-"
            lines.append(f"{task.id:<15} {task.status.value:<12} {latency:<10} {provider:<10}")
            if task.error:
                lines.append(f"  Error: {task.error}")

    lines.append("=" * 60)
    return "\n".join(lines)
