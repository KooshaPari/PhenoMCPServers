#!/usr/bin/env python3
"""Privacy policy helpers for agent session records."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

MAX_TEXT_LENGTH = 240
MAX_METADATA_DEPTH = 4
MAX_METADATA_ITEMS = 40

RAW_SESSION_PATTERNS = re.compile(
    r"(^|[^a-z0-9])(raw|transcript|prompt|completion|message_text|typed_text|"
    r"keystroke|keycode|screenshot|screen_capture|capture|frame|image|photo|"
    r"camera|webcam|audio|waveform|face|facial|biometric|embedding|landmark|"
    r"pupil|retina|iris)($|[^a-z0-9])",
    re.IGNORECASE,
)


def assert_privacy_safe_session_value(value: Any, path: str = "payload", depth: int = 0) -> None:
    """Reject raw transcript, screenshot, biometric, or sensor-like session payloads."""
    if depth > MAX_METADATA_DEPTH:
        raise ValueError(f"{path} exceeds max metadata depth")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int | float):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{path} numeric value must be finite")
        return
    if isinstance(value, str):
        if RAW_SESSION_PATTERNS.search(value):
            raise ValueError("raw session payload rejected; store derived session state only")
        return
    if isinstance(value, Mapping):
        if len(value) > MAX_METADATA_ITEMS:
            raise ValueError(f"{path} has too many metadata items")
        for key, item in value.items():
            key_text = str(key)
            if RAW_SESSION_PATTERNS.search(key_text):
                raise ValueError("raw session payload rejected; store derived session state only")
            assert_privacy_safe_session_value(item, f"{path}.{key_text}", depth + 1)
        return
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        if len(value) > MAX_METADATA_ITEMS:
            raise ValueError(f"{path} has too many metadata items")
        for index, item in enumerate(value):
            assert_privacy_safe_session_value(item, f"{path}[{index}]", depth + 1)
        return
    raise ValueError(f"{path} contains unsupported metadata type {type(value).__name__}")


def safe_text(value: str | None, name: str, max_length: int = MAX_TEXT_LENGTH) -> str | None:
    """Validate and bound short derived text fields."""
    if value is None:
        return None
    text = str(value).strip()
    assert_privacy_safe_session_value(text, name)
    return text[:max_length]


def safe_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return deterministic, privacy-checked metadata for JSONL storage."""
    if not metadata:
        return {}
    assert_privacy_safe_session_value(metadata, "metadata")
    return {str(key): metadata[key] for key in sorted(metadata)}
