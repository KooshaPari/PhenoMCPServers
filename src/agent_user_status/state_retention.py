#!/usr/bin/env python3
"""Retention, export, and delete helpers for derived local JSON state."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DERIVED_SUFFIXES = {".json", ".jsonl"}


def derived_state_files(state_dir: Path) -> list[Path]:
    """Return derived JSON/JSONL state files directly under the state directory."""
    if not state_dir.exists():
        return []
    return sorted(
        path
        for path in state_dir.iterdir()
        if path.is_file() and path.suffix in DERIVED_SUFFIXES and not path.name.startswith(".")
    )


def export_state(state_dir: Path) -> dict[str, Any]:
    """Export derived local state without reading native assets or model files."""
    files: dict[str, Any] = {}
    for path in derived_state_files(state_dir):
        if path.suffix == ".jsonl":
            records = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    records.append({"malformed": True})
            files[path.name] = {"kind": "jsonl", "records": records}
        else:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {"malformed": True}
            files[path.name] = {"kind": "json", "payload": payload}
    return {"state_dir": str(state_dir), "files": files}


def delete_state(state_dir: Path, *, names: list[str] | None = None) -> dict[str, Any]:
    """Delete selected derived JSON/JSONL files, or all when names is omitted."""
    allowed = {path.name: path for path in derived_state_files(state_dir)}
    selected = sorted(names or allowed)
    deleted: list[str] = []
    missing: list[str] = []
    for name in selected:
        path = allowed.get(Path(name).name)
        if path is None:
            missing.append(name)
            continue
        path.unlink()
        deleted.append(path.name)
    return {"deleted": deleted, "missing": missing}


def retain_recent_state(state_dir: Path, *, max_age_seconds: int) -> dict[str, Any]:
    """Delete derived files older than max_age_seconds based on mtime."""
    cutoff = datetime.now(UTC) - timedelta(seconds=max(1, int(max_age_seconds)))
    deleted: list[str] = []
    kept: list[str] = []
    for path in derived_state_files(state_dir):
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if modified < cutoff:
            path.unlink()
            deleted.append(path.name)
        else:
            kept.append(path.name)
    return {"deleted": deleted, "kept": kept, "max_age_seconds": max_age_seconds}
