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


def run_docs_fr(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/validate-docs.sh", "fr"],
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


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_validate_docs_rejects_fr_trace_marker_mismatch(tmp_path) -> None:
    repo = write_minimal_docs_repo(tmp_path)
    docs = repo / "docs"
    tests = repo / "tests" / "unit"
    fr_id = "FR-" + "AGENT_USER_STATUS-001"
    docs.mkdir()
    tests.mkdir(parents=True)
    (docs / "FUNCTIONAL_REQUIREMENTS.md").write_text(
        "\n".join(
            [
                "# Functional Requirements",
                f"### {fr_id}",
                "**Description:** CLI interface",
                "**Status:** IMPLEMENTED",
                "**Test Traces:** `tests/unit/test_expected.py`",
            ]
        ),
        encoding="utf-8",
    )
    (tests / "test_actual.py").write_text(
        f'import pytest\n\n@pytest.mark.requirement("{fr_id}")\ndef test_actual():\n    assert True\n',
        encoding="utf-8",
    )

    result = run_docs_fr(repo)

    assert result.returncode == 1
    assert f"{fr_id} trace files do not match pytest markers" in result.stderr


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_validate_docs_rejects_implemented_requirement_with_pending_traces(tmp_path) -> None:
    repo = write_minimal_docs_repo(tmp_path)
    docs = repo / "docs"
    docs.mkdir()
    fr_id = "FR-" + "AGENT_USER_STATUS-002"
    (docs / "FUNCTIONAL_REQUIREMENTS.md").write_text(
        "\n".join(
            [
                "# Functional Requirements",
                f"### {fr_id}",
                "**Description:** HTTP endpoints",
                "**Status:** IMPLEMENTED",
                "**Test Traces:** (pending implementation)",
            ]
        ),
        encoding="utf-8",
    )

    result = run_docs_fr(repo)

    assert result.returncode == 1
    assert f"{fr_id} is IMPLEMENTED but has pending traces" in result.stderr
