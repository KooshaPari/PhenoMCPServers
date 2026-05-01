"""Configure pytest to use the local src directory for agent_user_status package."""
from __future__ import annotations

import sys
from pathlib import Path

print(f"[agent-user-status conftest] Loaded from: {__file__}", flush=True)

# Remove any cached agent_user_status imports to force re-import from correct location
_modules_to_remove = [key for key in sys.modules.keys() if key.startswith("agent_user_status")]
for mod in _modules_to_remove:
    del sys.modules[mod]

# Ensure the local src directory takes precedence over any installed packages
_SRC_PATH = str(Path(__file__).parent / "src")
print(f"[agent-user-status conftest] _SRC_PATH: {_SRC_PATH}", flush=True)

# Remove any existing src paths to avoid duplicates
sys.path = [_SRC_PATH] + [p for p in sys.path if p != _SRC_PATH and not p.endswith("agent_user_status")]
print(f"[agent-user-status conftest] sys.path[0]: {sys.path[0]}", flush=True)
