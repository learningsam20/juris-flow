"""Text chunking with configurable size and overlap (PRD §5.2)."""

from __future__ import annotations

import re

from app.config import get_settings

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n{2,}")


def chunk_text(
    text: str, chunk_size: int | None = None, overlap: int | None = None
) -> list[str]:
    settings = get_settings()
    size = chunk_size or settings.chunk_size
    ov = overlap or settings.chunk_overlap
    if ov >= size:
        ov = size // 2

    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not text:
        return []

    units = _split_units(text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for unit in units:
        ulen = len(unit)
        if current and current_len + ulen + 1 > size:
            chunks.append("\n".join(current))
            current = _take_tail(current, ov)
            current_len = sum(len(u) + 1 for u in current)
        current.append(unit)
        current_len += ulen + 1
    if current:
        chunks.append("\n".join(current))

    # Re-attach oversized single units (e.g. very long sections)
    merged: list[str] = []
    for chunk in chunks:
        if len(chunk) > size * 2:
            start, step = 0, size - ov
            while start < len(chunk):
                merged.append(chunk[start : start + size])
                start += step
        else:
            merged.append(chunk)
    return [c.strip() for c in merged if c.strip()]


def _split_units(text: str) -> list[str]:
    units = []
    for part in _SENTENCE_END.split(text):
        for line in part.splitlines():
            line = line.strip()
            if line:
                units.append(line)
    return units


def _take_tail(units: list[str], char_count: int) -> list[str]:
    out: list[str] = []
    used = 0
    for unit in reversed(units):
        if out and used + len(unit) + 1 > char_count:
            break
        out.insert(0, unit)
        used += len(unit) + 1
    if not out and units:
        out = [units[-1]]
    return out
