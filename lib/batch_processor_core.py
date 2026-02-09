"""Auto-split mixins for BatchProcessor."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    from .batch_processor import BatchJob, BatchStatus, BatchTask, HANDLED_EXCEPTIONS
except ImportError:  # pragma: no cover - script mode
    from batch_processor import BatchJob, BatchStatus, BatchTask, HANDLED_EXCEPTIONS


class BatchProcessorCoreMixin:
    """Mixin methods extracted from BatchProcessor."""

    def __init__(
        self,
        max_concurrent: int = 5,
        default_provider: Optional[str] = None,
        timeout_s: float = 60.0,
        db_path: Optional[str] = None,
    ):
        """
        Initialize the batch processor.

        Args:
            max_concurrent: Maximum concurrent task executions
            default_provider: Default provider for tasks without explicit provider
            timeout_s: Timeout per task in seconds
            db_path: Path to SQLite database for persistence
        """
        self.max_concurrent = max_concurrent
        self.default_provider = default_provider
        self.timeout_s = timeout_s
        self._cancelled: set = set()

        # Setup database
        if db_path is None:
            config_dir = Path.home() / ".ccb_config"
            config_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(config_dir / "batch.db")
        self.db_path = db_path
        self._init_db()

        # Load jobs from database into memory cache
        self._jobs: Dict[str, BatchJob] = {}
        self._load_jobs_from_db()

    def _init_db(self):
        """Initialize the SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS batch_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    default_provider TEXT,
                    created_at REAL NOT NULL,
                    completed_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS batch_tasks (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    provider TEXT,
                    status TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    latency_ms REAL DEFAULT 0,
                    FOREIGN KEY (job_id) REFERENCES batch_jobs(id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_job_id ON batch_tasks(job_id)
            """)
            conn.commit()

    def _load_jobs_from_db(self, limit: int = 100):
        """Load recent jobs from database into memory."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            # Load recent jobs
            cursor = conn.execute("""
                SELECT * FROM batch_jobs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            for row in cursor.fetchall():
                job_id = row["id"]
                # Load tasks for this job
                task_cursor = conn.execute("""
                    SELECT * FROM batch_tasks WHERE job_id = ?
                """, (job_id,))

                tasks = []
                for task_row in task_cursor.fetchall():
                    task = BatchTask(
                        id=task_row["id"],
                        message=task_row["message"],
                        provider=task_row["provider"],
                        status=BatchStatus(task_row["status"]),
                        result=task_row["result"],
                        error=task_row["error"],
                        latency_ms=task_row["latency_ms"] or 0.0,
                    )
                    tasks.append(task)

                job = BatchJob(
                    id=job_id,
                    tasks=tasks,
                    created_at=row["created_at"],
                    completed_at=row["completed_at"],
                    status=BatchStatus(row["status"]),
                    default_provider=row["default_provider"],
                )
                self._jobs[job_id] = job

    def _save_job(self, job: BatchJob):
        """Save a job and its tasks to the database."""
        with sqlite3.connect(self.db_path) as conn:
            # Upsert job
            conn.execute("""
                INSERT OR REPLACE INTO batch_jobs
                (id, status, default_provider, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                job.id,
                job.status.value,
                job.default_provider,
                job.created_at,
                job.completed_at,
            ))

            # Upsert tasks
            for task in job.tasks:
                conn.execute("""
                    INSERT OR REPLACE INTO batch_tasks
                    (id, job_id, message, provider, status, result, error, latency_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.id,
                    job.id,
                    task.message,
                    task.provider,
                    task.status.value,
                    task.result,
                    task.error,
                    task.latency_ms,
                ))

            conn.commit()

    def _get_ask_command(self, provider: str) -> str:
        """Get the ask command for a provider."""
        return self.PROVIDER_COMMANDS.get(provider, "lask")

    def create_batch(
        self,
        messages: List[str],
        provider: Optional[str] = None,
    ) -> BatchJob:
        """
        Create a new batch job.

        Args:
            messages: List of messages to process
            provider: Optional provider override for all tasks

        Returns:
            BatchJob object
        """
        job_id = str(uuid.uuid4())[:8]
        tasks = []

        for i, msg in enumerate(messages):
            task = BatchTask(
                id=f"{job_id}-{i}",
                message=msg.strip(),
                provider=provider or self.default_provider,
            )
            tasks.append(task)

        job = BatchJob(
            id=job_id,
            tasks=tasks,
            created_at=time.time(),
            default_provider=provider or self.default_provider,
        )

        self._jobs[job_id] = job
        self._save_job(job)  # Persist to database
        return job

