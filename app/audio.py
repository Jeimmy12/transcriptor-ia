"""ffmpeg/ffprobe: normaliza cualquier audio/video y lo corta en bloques pequeños."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} falló: {p.stderr.strip()[-600:]}")
    return p.stdout


async def probe_duration(path: Path) -> float:
    try:
        out = await asyncio.to_thread(
            _run,
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
        )
        return float(out.strip())
    except (RuntimeError, ValueError):
        return 0.0


async def split_audio(src: Path, out_dir: Path, chunk_seconds: int) -> list[Path]:
    """MP3 mono 16 kHz 48 kbps (~0.36 MB/min), segmentado. Sin límite de duración total."""
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src), "-vn", "-map", "0:a:0?",
        "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k",
        "-f", "segment", "-segment_time", str(chunk_seconds), "-reset_timestamps", "1",
        str(out_dir / "part_%04d.mp3"),
    ]
    await asyncio.to_thread(_run, cmd)
    parts = sorted(out_dir.glob("part_*.mp3"))
    if not parts:
        raise RuntimeError("El archivo no contiene una pista de audio utilizable.")
    return parts
