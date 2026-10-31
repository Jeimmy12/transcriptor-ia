"""Pulido del español por bloque con Gemma."""
from __future__ import annotations

from . import prompts
from .config import settings
from .gemini_client import generate_stream, retry_notifier


async def polish_chunk(index: int, raw: str, emit) -> str:
    async def on_delta(t: str) -> None:
        await emit("delta", stage="polished", chunk=index, text=t)

    async def on_reset() -> None:
        await emit("reset", stage="polished", chunk=index)

    try:
        text = (await generate_stream(
            settings.polish_model, prompts.POLISH.format(text=raw),
            on_delta=on_delta, on_reset=on_reset, on_retry=retry_notifier(emit),
        )).strip()
    except Exception as exc:
        await emit("status", message=f"No se pudo pulir el bloque {index}; se usa el texto sin pulir ({exc.__class__.__name__}).")
        text = ""

    # Si el modelo resumió o devolvió vacío, se conserva el texto original.
    if len(text) < 0.6 * len(raw):
        await on_reset()
        await on_delta(raw)
        return raw
    return text
