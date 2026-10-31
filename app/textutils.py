"""Utilidades de texto sin dependencias externas."""
from __future__ import annotations

import re
from pathlib import Path

_SENTENCE_END = (".", "!", "?", "…", '"', "»", ")", "”")


def safe_stem(filename: str) -> str:
    stem = re.sub(r"[^\w\-. ]", "_", Path(filename).stem).strip(" ._")
    return stem[:80] or "audio"


def safe_suffix(filename: str) -> str:
    return re.sub(r"[^\w.]", "", Path(filename).suffix.lower())[:10]


def join_chunks(parts: list[str]) -> str:
    """Párrafo nuevo si el bloque anterior cerró una frase; espacio si quedó cortada."""
    out = ""
    for p in (x.strip() for x in parts):
        if not p:
            continue
        if not out:
            out = p
        elif out.endswith(_SENTENCE_END):
            out += "\n\n" + p
        else:
            out += " " + p
    return out


def split_text(text: str, max_chars: int) -> list[str]:
    """Parte un texto largo en bloques ≤ max_chars respetando párrafos (y frases si hace falta)."""
    pieces: list[str] = []
    for para in text.split("\n\n"):
        while len(para) > max_chars:
            cut = para.rfind(". ", 0, max_chars)
            cut = cut + 1 if cut > max_chars // 2 else max_chars
            pieces.append(para[:cut])
            para = para[cut:].lstrip()
        pieces.append(para)

    blocks, cur, size = [], [], 0
    for p in pieces:
        if cur and size + len(p) + 2 > max_chars:
            blocks.append("\n\n".join(cur))
            cur, size = [], 0
        cur.append(p)
        size += len(p) + 2
    if cur:
        blocks.append("\n\n".join(cur))
    return blocks
