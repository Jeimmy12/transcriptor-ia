"""Cliente único de la API de Google (Gemini + Gemma) con reintentos y streaming."""
from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable

import httpx
from google import genai
from google.genai import errors, types

from .config import settings

_client: genai.Client | None = None
_RETRYABLE = {408, 429, 500, 502, 503, 504}

OnDelta = Callable[[str], Awaitable[None]]
OnReset = Callable[[], Awaitable[None]]
OnRetry = Callable[[int, float, Exception], Awaitable[None]]


class MissingApiKeyError(RuntimeError):
    pass


def get_client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.google_api_key:
            raise MissingApiKeyError("Falta GOOGLE_API_KEY. Crea el archivo .env a partir de .env.example.")
        _client = genai.Client(
            api_key=settings.google_api_key,
            http_options=types.HttpOptions(timeout=settings.request_timeout_s * 1000),
        )
    return _client


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, errors.APIError):
        return exc.code in _RETRYABLE
    return isinstance(exc, (httpx.TransportError, ConnectionError, TimeoutError))


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, errors.APIError):
        hints = {
            400: "Solicitud inválida (¿clave o modelo incorrectos?)",
            401: "Clave API inválida.",
            403: "Clave API sin permisos para este modelo.",
            404: "Modelo no encontrado: revisa TRANSCRIBE_MODEL / POLISH_MODEL / SUMMARY_MODEL en .env.",
            429: "Cuota o límite de tasa agotado.",
        }
        msg = str(getattr(exc, "message", "") or exc)[:300]
        return f"{hints.get(exc.code, 'Error de la API de Google')} ({exc.code}): {msg}"
    return str(exc) or type(exc).__name__


def retry_notifier(emit):
    async def _cb(attempt: int, delay: float, exc: Exception) -> None:
        await emit("status", message=f"Reintento {attempt} en {delay:.0f} s — {friendly_error(exc)[:140]}")
    return _cb


async def generate_stream(
    model: str,
    contents,
    *,
    on_delta: OnDelta | None = None,
    on_reset: OnReset | None = None,
    on_retry: OnRetry | None = None,
) -> str:
    """Genera texto en streaming. Si falla a mitad, avisa con on_reset y reintenta desde cero."""
    client = get_client()
    for attempt in range(settings.max_retries + 1):
        parts: list[str] = []
        try:
            stream = await client.aio.models.generate_content_stream(model=model, contents=contents)
            async for piece in stream:
                text = piece.text
                if text:
                    parts.append(text)
                    if on_delta:
                        await on_delta(text)
            return "".join(parts)
        except Exception as exc:  # CancelledError no hereda de Exception
            if not _is_retryable(exc) or attempt >= settings.max_retries:
                raise
            if parts and on_reset:
                await on_reset()
            delay = min(60.0, settings.retry_base_delay * 2**attempt) + random.uniform(0, 1.5)
            if on_retry:
                await on_retry(attempt + 1, delay, exc)
            await asyncio.sleep(delay)
    return ""
