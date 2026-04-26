"""Privacy policy and raw-payload gate for statusd HTTP routes."""

from __future__ import annotations

import json
import re
from typing import Any

MAX_BODY_BYTES = 16_384
RAW_SENSOR_PATTERNS = re.compile(
    r"(^|[^a-z0-9])(raw|frame|image|photo|screenshot|face|facial|biometric|"
    r"pupil|retina|iris|embedding|landmarks?|camera|webcam|audio|transcript|waveform|"
    r"typed_text|key_name|keystroke|keycode)($|[^a-z0-9])",
    re.IGNORECASE,
)

PRIVACY_POLICY = {
    "classification": "highly_confidential_derived_presence",
    "retention": "short_lived_signals_only; agent-imessage max_age_seconds gates freshness",
    "accepted": [
        "score",
        "state",
        "screen_zone",
        "bounded screen coordinates for explicit correction events",
        "confidence",
        "eta_minutes",
        "max_age_seconds",
        "short note without raw sensor content",
    ],
    "rejected": [
        "camera frames",
        "screenshots",
        "face or eye images",
        "facial landmarks",
        "biometric embeddings",
        "raw gaze streams",
        "medical inference labels",
        "keystroke contents or key names",
        "audio transcripts or waveforms",
    ],
}


def reject_raw_payload(payload: dict[str, Any]) -> str | None:
    text = json.dumps(payload, sort_keys=True)
    if len(text.encode("utf-8")) > MAX_BODY_BYTES:
        return "payload too large"
    if RAW_SENSOR_PATTERNS.search(text):
        return "raw sensor/biometric payload rejected; send derived state only"
    return None
