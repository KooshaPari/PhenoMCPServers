"""Compatibility entrypoint for agent-user-status bootstrap CLI."""

from __future__ import annotations

from agent_user_status.bootstrap_cli import main as _cli_main


def main(argv: list[str] | None = None) -> int:
    """Delegate to the canonical bootstrap CLI implementation."""
    return int(_cli_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
