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


class BatchProcessor:
    """
    Processes batch jobs with parallel execution.

    Supports progress tracking, cancellation, and SQLite persistence.
    """

    # Provider to ask command mapping
    PROVIDER_COMMANDS = {
        "claude": "lask",
        "codex": "cask",
        "gemini": "gask",
        "opencode": "oask",
        "droid": "dask",
        "iflow": "iask",
        "kimi": "kask",
        "qwen": "qask",
        "deepseek": "dskask",
    }

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

    def _execute_task(self, task: BatchTask) -> BatchTask:
        """Execute a single task."""
        if task.id in self._cancelled:
            task.status = BatchStatus.CANCELLED
            return task

        provider = task.provider or self.default_provider or "claude"
        ask_cmd = self._get_ask_command(provider)
        start_time = time.time()

        try:
            cmd = f"{ask_cmd} <<'EOF'\n{task.message}\nEOF"
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )

            task.latency_ms = (time.time() - start_time) * 1000
            task.provider = provider

            if result.returncode == 0:
                task.status = BatchStatus.COMPLETED
                task.result = result.stdout
            else:
                task.status = BatchStatus.FAILED
                task.error = result.stderr or f"Exit code: {result.returncode}"

        except subprocess.TimeoutExpired:
            task.latency_ms = (time.time() - start_time) * 1000
            task.status = BatchStatus.FAILED
            task.error = "Timeout"
        except Exception as e:
            task.latency_ms = (time.time() - start_time) * 1000
            task.status = BatchStatus.FAILED
            task.error = str(e)

        return task

    def execute_batch(
        self,
        job: BatchJob,
        on_progress: Optional[Callable[[BatchJob, BatchTask], None]] = None,
    ) -> BatchJob:
        """
        Execute a batch job.

        Args:
            job: The batch job to execute
            on_progress: Optional callback called after each task completes

        Returns:
            Updated BatchJob
        """
        job.status = BatchStatus.RUNNING
        self._save_job(job)  # Save running status

        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self._execute_task, task): task
                for task in job.tasks
            }

            # Collect results
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    completed_task = future.result()
                    # Update task in job
                    for i, t in enumerate(job.tasks):
                        if t.id == completed_task.id:
                            job.tasks[i] = completed_task
                            break

                    # Save progress to database
                    self._save_job(job)

                    if on_progress:
                        on_progress(job, completed_task)

                except Exception as e:
                    task.status = BatchStatus.FAILED
                    task.error = str(e)

                # Check for cancellation
                if job.id in self._cancelled:
                    for f in future_to_task:
                        f.cancel()
                    job.status = BatchStatus.CANCELLED
                    break

        job.completed_at = time.time()

        if job.status != BatchStatus.CANCELLED:
            if job.failed_count == len(job.tasks):
                job.status = BatchStatus.FAILED
            else:
                job.status = BatchStatus.COMPLETED

        self._save_job(job)  # Save final status
        return job

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get a batch job by ID."""
        # Check memory cache first
        if job_id in self._jobs:
            return self._jobs[job_id]

        # Try to load from database
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM batch_jobs WHERE id = ?
            """, (job_id,))
            row = cursor.fetchone()

            if row:
                # Load tasks
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
                return job

        return None

    def get_progress(self, job_id: str) -> float:
        """Get progress of a batch job."""
        job = self._jobs.get(job_id)
        return job.progress if job else 0.0

    def cancel_batch(self, job_id: str) -> bool:
        """
        Cancel a batch job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if job was found and marked for cancellation
        """
        if job_id in self._jobs:
            self._cancelled.add(job_id)
            job = self._jobs[job_id]
            # Mark pending tasks as cancelled
            for task in job.tasks:
                if task.status == BatchStatus.PENDING:
                    task.status = BatchStatus.CANCELLED
                    self._cancelled.add(task.id)
            job.status = BatchStatus.CANCELLED
            self._save_job(job)  # Persist cancellation
            return True
        return False

    def list_jobs(self, limit: int = 20) -> List[BatchJob]:
        """List recent batch jobs from database."""
        jobs = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM batch_jobs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            for row in cursor.fetchall():
                job_id = row["id"]
                # Check memory cache first
                if job_id in self._jobs:
                    jobs.append(self._jobs[job_id])
                else:
                    # Load from database
                    job = self.get_job(job_id)
                    if job:
                        jobs.append(job)

        return jobs

    def delete_job(self, job_id: str) -> bool:
        """Delete a batch job from database and memory."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM batch_tasks WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM batch_jobs WHERE id = ?", (job_id,))
            conn.commit()

        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def cleanup_old_jobs(self, hours: int = 24) -> int:
        """
        Remove jobs older than specified hours.

        Args:
            hours: Age threshold in hours

        Returns:
            Number of jobs removed
        """
        cutoff = time.time() - (hours * 3600)
        count = 0

        with sqlite3.connect(self.db_path) as conn:
            # Get IDs of old jobs
            cursor = conn.execute("""
                SELECT id FROM batch_jobs WHERE created_at < ?
            """, (cutoff,))
            old_job_ids = [row[0] for row in cursor.fetchall()]

            # Delete tasks and jobs
            for job_id in old_job_ids:
                conn.execute("DELETE FROM batch_tasks WHERE job_id = ?", (job_id,))
                conn.execute("DELETE FROM batch_jobs WHERE id = ?", (job_id,))
                if job_id in self._jobs:
                    del self._jobs[job_id]
                count += 1

            conn.commit()

        return count


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
