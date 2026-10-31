"""Minuta con puntos clave usando Gemma. Para textos muy largos: notas por partes y minuta final."""
from __future__ import annotations

from . import prompts
from .config import settings
from .gemini_client import generate_stream, retry_notifier
from .textutils import split_text


async def build_minuta(text: str, emit) -> str:
    on_retry = retry_notifier(emit)

    async def on_delta(t: str) -> None:
        await emit("delta", stage="minuta", chunk=0, text=t)

    async def on_reset() -> None:
        await emit("reset", stage="minuta", chunk=0)

    if len(text) <= settings.minuta_single_pass_chars:
        material, kind = text, "transcripción"
    else:
        blocks = split_text(text, settings.minuta_block_chars)
        notes = []
        for i, block in enumerate(blocks, 1):
            await emit("status", message=f"Analizando parte {i} de {len(blocks)} de la transcripción…")
            note = await generate_stream(
                settings.summary_model, prompts.PARTIAL.format(i=i, n=len(blocks), text=block),
                on_retry=on_retry,
            )
            notes.append(f"### Parte {i}\n{note.strip()}")
        material, kind = "\n\n".join(notes), "serie de notas parciales de una transcripción larga"

    await emit("status", message="Redactando la minuta con Gemma…")
    out = (await generate_stream(
        settings.summary_model, prompts.MINUTA.format(kind=kind, material=material),
        on_delta=on_delta, on_reset=on_reset, on_retry=on_retry,
    )).strip()
    if not out:
        raise RuntimeError("Gemma devolvió una minuta vacía.")
    return out
