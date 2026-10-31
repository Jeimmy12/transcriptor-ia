"""Orquestación: audio → bloques → transcripción (Gemini) → pulido (Gemma) → minuta (Gemma)."""
from __future__ import annotations

import asyncio
import logging
import shutil

from .audio import ffmpeg_available, probe_duration, split_audio
from .config import settings
from .gemini_client import MissingApiKeyError, friendly_error, get_client
from .jobs import Job
from .polisher import polish_chunk
from .summarizer import build_minuta
from .textutils import join_chunks
from .transcriber import transcribe_chunk

log = logging.getLogger("pipeline")
_gate = asyncio.Semaphore(settings.max_concurrent_jobs)


async def run_job(job: Job) -> None:
    await job.emit("status", message="En cola…")
    try:
        async with _gate:
            await _process(job)
    except asyncio.CancelledError:
        await job.emit("cancelled")
    except MissingApiKeyError as exc:
        await job.emit("job_error", message=str(exc))
    except Exception as exc:
        log.exception("Falló el trabajo %s", job.id)
        await job.emit("job_error", message=friendly_error(exc))
    finally:
        if not settings.keep_temp_files:
            await asyncio.to_thread(shutil.rmtree, job.work_dir, True)
        await job.finish()


async def _process(job: Job) -> None:
    emit = job.emit
    get_client()  # falla pronto si no hay API key
    if not ffmpeg_available():
        raise RuntimeError("No se encontró ffmpeg/ffprobe en el PATH. Instálalo (ver README).")
    job.out_dir.mkdir(parents=True, exist_ok=True)

    await emit("status", message="Convirtiendo y segmentando el audio…")
    duration = await probe_duration(job.input_path)
    chunks = await split_audio(job.input_path, job.chunks_dir, settings.chunk_seconds)
    total = len(chunks)
    await emit("meta", duration=duration, total_chunks=total, chunk_seconds=settings.chunk_seconds,
               polish=settings.polish_enabled, models={"transcribe": settings.transcribe_model,
               "polish": settings.polish_model, "summary": settings.summary_model})

    raw: dict[int, str] = {}
    polished: dict[int, str] = {}
    queue: asyncio.Queue = asyncio.Queue()

    async def polish_worker() -> None:
        while (item := await queue.get()) is not None:
            idx, text = item
            polished[idx] = await polish_chunk(idx, text, emit) if text else ""
            await emit("chunk_done", stage="polished", chunk=idx, empty=not text)

    worker = asyncio.create_task(polish_worker()) if settings.polish_enabled else None
    raw_file = job.out_dir / "transcripcion_cruda.txt"
    try:
        tail = ""
        for idx, path in enumerate(chunks, 1):
            if worker and worker.done():
                worker.result()  # propaga errores inesperados del worker
            await emit("status", message=f"Transcribiendo bloque {idx} de {total}…")
            raw[idx] = await transcribe_chunk(path, idx, total, tail, emit)
            tail = raw[idx][-600:] if raw[idx] else tail
            await emit("chunk_done", stage="raw", chunk=idx, empty=not raw[idx])
            await asyncio.to_thread(raw_file.write_text, join_chunks([raw[i] for i in sorted(raw)]), "utf-8")
            if worker:
                await queue.put((idx, raw[idx]))
        if worker:
            await queue.put(None)
            await worker
    except BaseException:
        if worker and not worker.done():
            worker.cancel()
        raise

    raw_text = join_chunks([raw[i] for i in sorted(raw)])
    final_text = join_chunks([polished.get(i, raw[i]) if worker else raw[i] for i in sorted(raw)])
    if not final_text:
        raise RuntimeError("No se detectó voz en el audio.")

    final_file = job.out_dir / "transcripcion.txt"
    await asyncio.to_thread(raw_file.write_text, raw_text, "utf-8")
    await asyncio.to_thread(final_file.write_text, final_text, "utf-8")
    job.files.update(raw=raw_file, transcript=final_file)
    await emit("files_ready")

    minuta = await build_minuta(final_text, emit)
    minuta_file = job.out_dir / "minuta.md"
    await asyncio.to_thread(minuta_file.write_text, minuta, "utf-8")
    job.files["minuta"] = minuta_file
    await emit("done", folder=str(job.out_dir))
