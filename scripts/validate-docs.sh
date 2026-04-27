#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-all}"

case "${MODE}" in
  all|links|fr|matrix|fr-write)
    ;;
  *)
    echo "usage: $0 [all|links|fr|matrix|fr-write]" >&2
    exit 2
    ;;
esac

cd "${ROOT_DIR}"

python3 - "${MODE}" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

MODE = sys.argv[1]
ROOT = Path.cwd()
DOC_ROOTS = [
    Path("README.md"),
    Path("FUNCTIONAL_REQUIREMENTS.md"),
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    Path("CONTRIBUTING.md"),
    Path("SECURITY.md"),
    Path("docs"),
    Path("packaging"),
    Path("skills"),
    Path(".github"),
]
FR_DOC = Path("docs/FUNCTIONAL_REQUIREMENTS.md")
HOOKS_JSON = Path(".codex/hooks.json")

LOCAL_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
FR_HEADING_RE = re.compile(r"^### (FR-AGENT_USER_STATUS-\d{3})$", re.MULTILINE)
STATUS_RE = re.compile(r"\*\*Status:\*\* (IMPLEMENTED|PARTIAL|SCAFFOLD)")
TRACE_RE = re.compile(r"\*\*Test Traces:\*\* (.+)")
CANONICAL_MARKER_RE = re.compile(r"FR-AGENT_USER_STATUS-\d{3}")
LEGACY_MARKER_RE = re.compile(r"FR-age-\d{3}")
VALID_STATUSES = {"IMPLEMENTED", "PARTIAL", "SCAFFOLD"}

errors: list[str] = []
warnings: list[str] = []


def iter_markdown_files() -> list[Path]:
    files: list[Path] = []
    for root in DOC_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*.md") if path.is_file())
    return sorted(set(files))


def iter_source_files() -> list[Path]:
    roots = [Path("tests"), Path("src")]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(path for path in root.rglob("*.py") if path.is_file())
    return sorted(files)


def validate_hooks_json() -> None:
    if not HOOKS_JSON.exists():
        errors.append(f"missing {HOOKS_JSON}")
        return
    try:
        json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{HOOKS_JSON}:{exc.lineno}: invalid JSON: {exc.msg}")


def validate_local_links() -> None:
    for path in iter_markdown_files():
        text = path.read_text(encoding="utf-8")
        for match in LOCAL_LINK_RE.finditer(text):
            raw_target = match.group(1).strip()
            if not raw_target or raw_target.startswith("#"):
                continue
            if re.match(r"^[a-z][a-z0-9+.-]*:", raw_target, re.IGNORECASE):
                continue
            target_without_anchor = raw_target.split("#", 1)[0]
            if not target_without_anchor:
                continue
            candidate = (path.parent / unquote(target_without_anchor)).resolve()
            try:
                candidate.relative_to(ROOT)
            except ValueError:
                errors.append(f"{path}: local link escapes repo: {raw_target}")
                continue
            if not candidate.exists():
                errors.append(f"{path}: missing local link target: {raw_target}")


def parse_fr_blocks() -> dict[str, str]:
    if not FR_DOC.exists():
        errors.append(f"missing {FR_DOC}")
        return {}
    text = FR_DOC.read_text(encoding="utf-8")
    headings = list(FR_HEADING_RE.finditer(text))
    if not headings:
        errors.append(f"{FR_DOC}: no canonical FR headings found")
        return {}

    ids: dict[str, str] = {}
    for index, heading in enumerate(headings):
        fr_id = heading.group(1)
        block_end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.end() : block_end]
        if fr_id in ids:
            errors.append(f"{FR_DOC}: duplicate FR id {fr_id}")
        ids[fr_id] = block

        status_match = STATUS_RE.search(block)
        if not status_match:
            errors.append(f"{FR_DOC}: {fr_id} missing status")
        elif status_match.group(1) not in VALID_STATUSES:
            errors.append(f"{FR_DOC}: {fr_id} has invalid status {status_match.group(1)}")

        trace_match = TRACE_RE.search(block)
        if not trace_match:
            errors.append(f"{FR_DOC}: {fr_id} missing test traces")
            continue

        traces = trace_match.group(1).strip()
        status = status_match.group(1) if status_match else ""
        if status in {"IMPLEMENTED", "PARTIAL"}:
            if traces == "(pending implementation)":
                errors.append(f"{FR_DOC}: {fr_id} is {status} but has pending traces")
                continue
            for trace in re.findall(r"`([^`]+)`", traces):
                trace_path = Path(trace)
                if not trace_path.exists():
                    errors.append(f"{FR_DOC}: {fr_id} trace does not exist: {trace}")
    return ids


def validate_fr_markers(fr_blocks: dict[str, str]) -> None:
    canonical_ids = set(fr_blocks)
    canonical_seen: set[str] = set()
    marker_files: dict[str, set[str]] = {}
    legacy_seen: set[str] = set()
    for path in iter_source_files():
        text = path.read_text(encoding="utf-8")
        for marker in CANONICAL_MARKER_RE.findall(text):
            canonical_seen.add(marker)
            marker_files.setdefault(marker, set()).add(str(path))
            if marker not in canonical_ids:
                errors.append(f"{path}: marker {marker} is not defined in {FR_DOC}")
        for marker in LEGACY_MARKER_RE.findall(text):
            legacy_seen.add(marker)
            errors.append(f"{path}: legacy marker {marker} must use canonical FR-AGENT_USER_STATUS-*")

    for fr_id, block in fr_blocks.items():
        status_match = STATUS_RE.search(block)
        status = status_match.group(1) if status_match else ""
        if status == "IMPLEMENTED" and fr_id not in canonical_seen:
            errors.append(f"{FR_DOC}: {fr_id} is IMPLEMENTED but no test marker references it")
        if status in {"IMPLEMENTED", "PARTIAL"}:
            trace_match = TRACE_RE.search(block)
            declared_files = set(re.findall(r"`([^`]+)`", trace_match.group(1))) if trace_match else set()
            marked_files = marker_files.get(fr_id, set())
            if declared_files != marked_files:
                errors.append(
                    f"{FR_DOC}: {fr_id} trace files do not match pytest markers "
                    f"(declared={sorted(declared_files)}, marked={sorted(marked_files)})"
                )

    if legacy_seen:
        warnings.append(
            "legacy FR-age markers still exist and should be reconciled: "
            + ", ".join(sorted(legacy_seen))
        )


def validate_stale_phrases() -> None:
    stale_patterns = [
        "doctor` gate fails until the live `~/.local` install is refreshed",
        "doc-link-check not available; skipping",
        "fr-coverage not available; skipping",
    ]
    for path in iter_markdown_files() + list(Path(".github/workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for phrase in stale_patterns:
            if phrase in text:
                errors.append(f"{path}: stale validation phrase remains: {phrase}")
        for marker in LEGACY_MARKER_RE.findall(text):
            errors.append(f"{path}: legacy marker {marker} must use canonical FR-AGENT_USER_STATUS-*")


if MODE in {"all", "links"}:
    validate_hooks_json()
    validate_local_links()
    validate_stale_phrases()

if MODE in {"all", "fr"}:
    validate_fr_markers(parse_fr_blocks())

for warning in warnings:
    print(f"warning: {warning}", file=sys.stderr)

if errors:
    print("docs validation failed:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    raise SystemExit(1)

print(f"docs validation passed ({MODE})")
PY

if [[ "${MODE}" == "fr-write" ]]; then
  python3 scripts/update-fr-matrix.py --write
elif [[ "${MODE}" == "all" || "${MODE}" == "fr" || "${MODE}" == "matrix" ]]; then
  python3 scripts/update-fr-matrix.py --check
fi
