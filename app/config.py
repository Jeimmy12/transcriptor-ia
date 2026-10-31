"""Configuración centralizada. Todo sale de variables de entorno / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _s(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _i(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _b(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def _p(name: str, default: str) -> Path:
    p = Path(_s(name, default))
    return p if p.is_absolute() else BASE_DIR / p


@dataclass(frozen=True)
class Settings:
    google_api_key: str = _s("GOOGLE_API_KEY", "")
    transcribe_model: str = _s("TRANSCRIBE_MODEL", "gemini-flash-latest")
    polish_model: str = _s("POLISH_MODEL", "gemma-4-26b-a4b-it")
    summary_model: str = _s("SUMMARY_MODEL", "gemma-4-26b-a4b-it")
    polish_enabled: bool = _b("POLISH_ENABLED", True)
    chunk_seconds: int = max(60, min(1800, _i("CHUNK_SECONDS", 600)))
    minuta_single_pass_chars: int = _i("MINUTA_SINGLE_PASS_CHARS", 120_000)
    minuta_block_chars: int = _i("MINUTA_BLOCK_CHARS", 60_000)
    max_retries: int = _i("MAX_RETRIES", 5)
    retry_base_delay: int = _i("RETRY_BASE_DELAY", 4)
    request_timeout_s: int = _i("REQUEST_TIMEOUT_S", 600)
    max_concurrent_jobs: int = max(1, _i("MAX_CONCURRENT_JOBS", 1))
    keep_temp_files: bool = _b("KEEP_TEMP_FILES", False)
    host: str = _s("HOST", "127.0.0.1")
    port: int = _i("PORT", 8000)
    data_dir: Path = _p("DATA_DIR", "data")
    output_dir: Path = _p("OUTPUT_DIR", "outputs")


settings = Settings()
