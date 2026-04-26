"""Bounded JSONL tail readers for hook-safe state access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_TAIL_BYTES = 128 * 1024


def tail_lines(path: Path, *, limit: int, max_bytes: int = DEFAULT_TAIL_BYTES) -> list[str]:
    """Return up to ``limit`` trailing lines without reading the whole file."""

    if not path.exists():
        return []
    bounded_limit = max(1, int(limit))
    bounded_bytes = max(1024, int(max_bytes))
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > bounded_bytes:
            handle.seek(size - bounded_bytes)
            handle.readline()
        data = handle.read()
    text = data.decode("utf-8", errors="replace")
    return text.splitlines()[-bounded_limit:]


def tail_jsonl(path: Path, *, limit: int, max_bytes: int = DEFAULT_TAIL_BYTES) -> list[dict[str, Any]]:
    """Return trailing JSON object records, skipping malformed lines."""

    records: list[dict[str, Any]] = []
    bounded_limit = max(1, int(limit))
    raw_limit = min(max(bounded_limit * 4, bounded_limit + 20), bounded_limit + 500)
    for line in tail_lines(path, limit=raw_limit, max_bytes=max_bytes):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records[-bounded_limit:]
