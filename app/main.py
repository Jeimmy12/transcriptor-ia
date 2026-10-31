"""API FastAPI: subida por streaming, eventos SSE en vivo y descargas."""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
from contextlib import asynccontextmanager
from urllib.parse import unquote

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .audio import ffmpeg_available
from .config import BASE_DIR, settings
from .jobs import Job, registry
from .pipeline import run_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Transcriptor IA", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

DOWNLOADS = {
    "raw": ("transcripcion_cruda.txt", "text/plain"),
    "transcript": ("transcripcion.txt", "text/plain"),
    "minuta": ("minuta.md", "text/markdown"),
}


def _job(job_id: str) -> Job:
    job = registry.get(job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado (¿se reinició el servidor?).")
    return job


@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
async def health():
    return {
        "api_key": bool(settings.google_api_key),
        "ffmpeg": ffmpeg_available(),
        "chunk_seconds": settings.chunk_seconds,
        "models": {"transcribe": settings.transcribe_model, "polish": settings.polish_model,
                   "summary": settings.summary_model},
    }


@app.post("/api/jobs")
async def create_job(request: Request, x_filename: str = Header(default="audio")):
    """Recibe el archivo como cuerpo crudo y lo escribe a disco por trozos (sirve para archivos enormes)."""
    job = registry.create(unquote(x_filename))
    job.work_dir.mkdir(parents=True, exist_ok=True)
    dest = job.work_dir / f"input{job.suffix}"
    size = 0
    try:
        with dest.open("wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
                size += len(chunk)
    except Exception:
        registry.discard(job)
        shutil.rmtree(job.work_dir, ignore_errors=True)
        raise HTTPException(400, "La subida se interrumpió.")
    if size == 0:
        registry.discard(job)
        shutil.rmtree(job.work_dir, ignore_errors=True)
        raise HTTPException(400, "El archivo está vacío.")
    job.input_path = dest
    job.task = asyncio.create_task(run_job(job))
    return {"job_id": job.id, "size": size}


async def _sse(job: Job, request: Request, start: int):
    idx = start
    while True:
        async with job.cond:
            if idx >= len(job.events) and not job.finished:
                try:
                    await asyncio.wait_for(job.cond.wait(), timeout=15)
                except asyncio.TimeoutError:
                    pass
            batch, finished = job.events[idx:], job.finished
        for ev in batch:
            yield f"id: {idx}\nevent: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
            idx += 1
        if finished and idx >= len(job.events):
            return
        if not batch:
            yield ": ping\n\n"
        if await request.is_disconnected():
            return


@app.get("/api/jobs/{job_id}/events")
async def events(job_id: str, request: Request, last_event_id: str | None = Header(default=None)):
    start = int(last_event_id) + 1 if last_event_id and last_event_id.isdigit() else 0
    return StreamingResponse(
        _sse(_job(job_id), request, start), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/jobs/{job_id}/cancel")
async def cancel(job_id: str):
    job = _job(job_id)
    if job.task and not job.task.done():
        job.task.cancel()
    return {"ok": True}


@app.get("/api/jobs/{job_id}/files/{kind}")
async def get_file(job_id: str, kind: str):
    job = _job(job_id)
    if kind not in DOWNLOADS or kind not in job.files:
        raise HTTPException(404, "Archivo aún no disponible.")
    suffix, media = DOWNLOADS[kind]
    return FileResponse(job.files[kind], media_type=media, filename=f"{job.stem}_{suffix}")
