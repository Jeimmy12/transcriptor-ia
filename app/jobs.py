"""Trabajos en memoria con bus de eventos (para streaming SSE en vivo)."""
from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

from .config import settings
from .textutils import safe_stem, safe_suffix


class Job:
    def __init__(self, filename: str) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.filename = filename
        self.stem = safe_stem(filename)
        self.suffix = safe_suffix(filename)
        self.created = time.time()
        self.work_dir = settings.data_dir / "jobs" / self.id
        self.chunks_dir = self.work_dir / "chunks"
        self.out_dir = settings.output_dir / f"{self.stem}_{self.id[:6]}"
        self.input_path: Path | None = None
        self.files: dict[str, Path] = {}
        self.events: list[dict] = []
        self.finished = False
        self.task: asyncio.Task | None = None
        self.cond = asyncio.Condition()

    async def emit(self, type_: str, **data) -> None:
        async with self.cond:
            self.events.append({"type": type_, **data})
            self.cond.notify_all()

    async def finish(self) -> None:
        async with self.cond:
            self.finished = True
            self.cond.notify_all()


class Registry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, filename: str) -> Job:
        now = time.time()  # libera memoria de trabajos terminados hace más de 24 h
        for jid in [k for k, j in self._jobs.items() if j.finished and now - j.created > 86400]:
            del self._jobs[jid]
        job = Job(filename)
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def discard(self, job: Job) -> None:
        self._jobs.pop(job.id, None)


registry = Registry()
