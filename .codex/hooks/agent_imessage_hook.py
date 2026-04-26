#!/usr/bin/env python3
"""Repo-local Codex hook entrypoint for agent-imessage."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from agent_user_status.codex_hooks import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
