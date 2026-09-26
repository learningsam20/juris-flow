"""Minimal in-process background job runner for long-running tasks (reviews, exports).

Jobs live only in memory for this MVP; a queue backend (Celery/Vertex Workflows)
can replace this transparently via jobs.resync_module later.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import Future
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_registry: dict[str, Job] = {}
_lock = threading.Lock()


class Job:
    def __init__(self, job_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        self.id = job_id
        self.status = "queued"
        self.result: Any = None
        self.error: str | None = None
        self._future: Future | None = None
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.created_at: datetime | None = None

    def run(self) -> None:
        converter = ThreadPool().executor()
        self.status = "running"
        _update_job_in_db(self.id, "running")
        self._future = converter.submit(self._fn, *self._args, **self._kwargs)
        try:
            self.result = self._future.result()
            self.status = "completed"
            _update_job_in_db(self.id, "completed", result=self.result)
        except Exception as exc:
            logger.exception("job %s failed", self.id)
            self.error = str(exc)
            self.status = "failed"
            _update_job_in_db(self.id, "failed", error=self.error)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "status": self.status,
            "error": self.error,
            "result": self.result,
        }
        if isinstance(self.result, dict) and "review_id" in self.result:
            d["review_id"] = self.result["review_id"]
        return d


def _update_job_in_db(
    job_id: str,
    status: str,
    result: Any = None,
    error: str | None = None,
) -> None:
    try:
        from app.db.session import SessionLocal
        from app.models.job import BackgroundJob
        from app.models.org import utcnow

        with SessionLocal() as db:
            bj = (
                db.query(BackgroundJob).filter(BackgroundJob.id == job_id).one_or_none()
            )
            if bj is None:
                bj = BackgroundJob(
                    id=job_id,
                    status=status,
                    result=result,
                    error=error,
                )
                db.add(bj)
            else:
                bj.status = status
                if result is not None:
                    bj.result = result
                if error is not None:
                    bj.error = error
                bj.updated_at = utcnow()
            db.commit()
    except Exception as exc:
        logger.warning("Failed to persist background job %s to DB: %s", job_id, exc)


class ThreadPool:
    _executor = None

    def executor(self):
        if ThreadPool._executor is None:
            from concurrent.futures import ThreadPoolExecutor

            cpu_count = os.cpu_count() or 4
            worker_count = max(4, min(12, cpu_count))
            ThreadPool._executor = ThreadPoolExecutor(max_workers=worker_count)
        return ThreadPool._executor


def shutdown(wait: bool = False, cancel_futures: bool = True) -> None:
    """Shut down the thread pool executor (useful for clean process exits / tests)."""
    with _lock:
        if ThreadPool._executor is not None:
            ThreadPool._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
            ThreadPool._executor = None


def enqueue(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    job_id = uuid.uuid4().hex
    _update_job_in_db(job_id, "queued")
    with _lock:
        job = Job(job_id, fn, *args, **kwargs)
        _registry[job_id] = job
    threading.Thread(target=_run, args=(job,), daemon=True).start()
    return job_id


def _run(job: Job) -> None:
    try:
        job.run()
    finally:
        import sys

        # keep completed jobs for a short while in memory
        if not sys.is_finalizing() and job.status in ("completed", "failed"):
            import time

            time.sleep(300)
            with _lock:
                _registry.pop(job.id, None)


def get(job_id: str) -> Job | None:
    with _lock:
        job = _registry.get(job_id)
    if job is not None and job.status in ("completed", "failed"):
        return job

    # Fall back to database query across processes/instances
    try:
        from app.db.session import SessionLocal
        from app.models.job import BackgroundJob

        with SessionLocal() as db:
            bj = (
                db.query(BackgroundJob).filter(BackgroundJob.id == job_id).one_or_none()
            )
            if bj is not None and (job is None or bj.status in ("completed", "failed")):
                persisted = Job(bj.id, lambda: None)
                persisted.status = bj.status
                persisted.error = bj.error
                persisted.result = bj.result
                persisted.created_at = bj.created_at
                return persisted
    except Exception as exc:
        logger.debug("Failed to read job %s from db: %s", job_id, exc)

    return job


def healthcheck() -> dict:
    with _lock:
        return {
            "queued": sum(1 for j in _registry.values() if j.status == "queued"),
            "running": sum(1 for j in _registry.values() if j.status == "running"),
            "completed": sum(1 for j in _registry.values() if j.status == "completed"),
        }
