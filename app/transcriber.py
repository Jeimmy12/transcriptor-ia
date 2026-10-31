"""Transcripción de un bloque de audio con Gemini (Gemma no acepta audio en la API)."""
from __future__ import annotations

from pathlib import Path

from google.genai import types

from . import prompts
from .config import settings
from .gemini_client import generate_stream, retry_notifier


async def transcribe_chunk(path: Path, index: int, total: int, previous_tail: str, emit) -> str:
    audio = types.Part.from_bytes(data=path.read_bytes(), mime_type="audio/mp3")
    context = prompts.CONTEXT.format(tail=previous_tail) if previous_tail else ""
    prompt = prompts.TRANSCRIBE.format(i=index, n=total, context=context)

    async def on_delta(t: str) -> None:
        await emit("delta", stage="raw", chunk=index, text=t)

    async def on_reset() -> None:
        await emit("reset", stage="raw", chunk=index)

    text = (await generate_stream(
        settings.transcribe_model, [audio, prompt],
        on_delta=on_delta, on_reset=on_reset, on_retry=retry_notifier(emit),
    )).strip()

    if not text or text.upper().startswith("[SILENCIO]"):
        await on_reset()
        return ""
    return text
