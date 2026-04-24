#!/usr/bin/env python3
"""CLI commands for derived local state retention."""

from __future__ import annotations

import argparse
import json

from agent_user_status.agent_imessage_core import STATE_DIR
from agent_user_status.state_retention import delete_state, export_state, retain_recent_state


def command_state_export(_: argparse.Namespace) -> int:
    print(json.dumps({"ok": True, "export": export_state(STATE_DIR)}, indent=2))
    return 0


def command_state_delete(args: argparse.Namespace) -> int:
    names = args.name or None
    print(json.dumps({"ok": True, **delete_state(STATE_DIR, names=names)}, indent=2))
    return 0


def command_state_retain(args: argparse.Namespace) -> int:
    payload = retain_recent_state(STATE_DIR, max_age_seconds=args.max_age_seconds)
    print(json.dumps({"ok": True, **payload}, indent=2))
    return 0


def add_state_parsers(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    export = sub.add_parser("state-export", help="Export derived local JSON/JSONL state")
    export.set_defaults(func=command_state_export)

    delete = sub.add_parser("state-delete", help="Delete derived local JSON/JSONL state")
    delete.add_argument("--name", action="append", help="Specific state file name; repeatable")
    delete.set_defaults(func=command_state_delete)

    retain = sub.add_parser("state-retain", help="Delete derived state older than max age")
    retain.add_argument("--max-age-seconds", type=int, required=True)
    retain.set_defaults(func=command_state_retain)
