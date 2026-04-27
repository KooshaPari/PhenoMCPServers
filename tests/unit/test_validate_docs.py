from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_validate_docs_rejects_temporal_root_reports(tmp_path) -> None:
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(Path("scripts/validate-docs.sh"), scripts / "validate-docs.sh")
    (repo / ".codex").mkdir()
    (repo / ".codex" / "hooks.json").write_text("{}", encoding="utf-8")
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    (repo / "SUMMARY.md").write_text("# Temporary Summary\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", "scripts/validate-docs.sh", "links"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "SUMMARY.md: merge durable content into docs/worklogs/ or docs/sessions/" in result.stderr
