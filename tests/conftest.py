"""Configure pytest to use the local src directory for agent_user_status package."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the local src directory takes precedence over any installed packages
_SRC_PATH = Path(__file__).parent.parent / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))
