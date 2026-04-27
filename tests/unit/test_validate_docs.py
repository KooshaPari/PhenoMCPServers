from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def write_minimal_docs_repo(tmp_path: Path, root_doc_name: str | None = None) -> Path:
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(Path("scripts/validate-docs.sh"), scripts / "validate-docs.sh")
    (repo / ".codex").mkdir()
    (repo / ".codex" / "hooks.json").write_text("{}", encoding="utf-8")
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    if root_doc_name:
        (repo / root_doc_name).write_text("# Temporary Report\n", encoding="utf-8")
    return repo


def run_docs_links(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/validate-docs.sh", "links"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_validate_docs_rejects_temporal_root_reports(tmp_path) -> None:
    result = run_docs_links(write_minimal_docs_repo(tmp_path, "SUMMARY.md"))

    assert result.returncode == 1
    assert "SUMMARY.md: merge durable content into docs/worklogs/ or docs/sessions/" in result.stderr


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_validate_docs_rejects_patterned_temporal_root_reports(tmp_path) -> None:
    result = run_docs_links(write_minimal_docs_repo(tmp_path, "release-status-report.md"))

    assert result.returncode == 1
    assert "release-status-report.md: merge durable content into docs/worklogs/ or docs/sessions/" in result.stderr


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_validate_docs_rejects_stale_pytest_command(tmp_path) -> None:
    repo = write_minimal_docs_repo(tmp_path)
    (repo / "CONTRIBUTING.md").write_text(
        "Run `PYTHONPATH=src python -m pytest tests/unit -q` before review.\n",
        encoding="utf-8",
    )

    result = run_docs_links(repo)

    assert result.returncode == 1
    assert "CONTRIBUTING.md: stale validation phrase remains" in result.stderr


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_validate_docs_rejects_missing_local_links(tmp_path) -> None:
    repo = write_minimal_docs_repo(tmp_path)
    (repo / "README.md").write_text("[missing](docs/missing.md)\n", encoding="utf-8")

    result = run_docs_links(repo)

    assert result.returncode == 1
    assert "README.md: missing local link target: docs/missing.md" in result.stderr
