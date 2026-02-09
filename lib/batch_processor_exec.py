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


class BatchProcessorExecMixin:
    """Mixin methods extracted from BatchProcessor."""

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
        except HANDLED_EXCEPTIONS as e:
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

                except HANDLED_EXCEPTIONS as e:
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


