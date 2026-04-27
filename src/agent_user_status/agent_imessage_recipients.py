"""Recipient role primitives for the local iMessage helper."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    role: str
    phone_e164: str
    phone_digits: str
    email: str
    name: str


RECIPIENT_ROLES = ("koosha", "sponsor")
RECIPIENT_ENV_PREFIXES = {
    "koosha": "AGENT_IMESSAGE",
    "sponsor": "AGENT_IMESSAGE_SPONSOR",
}


def require_recipient_role(role: str | None) -> str:
    normalized = (role or "koosha").strip().lower()
    if normalized not in RECIPIENT_ROLES:
        raise ValueError(f"Unsupported recipient role: {role}. Use one of: {', '.join(RECIPIENT_ROLES)}")
    return normalized
