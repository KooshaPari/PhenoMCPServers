from __future__ import annotations

import json

import pytest

from agent_user_status.jsonl_tail import tail_jsonl, tail_lines


@pytest.mark.requirement("FR-AGENT_USER_STATUS-016")
def test_tail_lines_reads_trailing_window_without_prefix_fragment(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text("".join(f"line-{index}\n" for index in range(200)), encoding="utf-8")

    lines = tail_lines(path, limit=5, max_bytes=80)

    assert lines == ["line-195", "line-196", "line-197", "line-198", "line-199"]


@pytest.mark.requirement("FR-AGENT_USER_STATUS-016")
def test_tail_jsonl_skips_malformed_lines(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for index in range(20):
            handle.write(json.dumps({"index": index}) + "\n")
        handle.write("{not-json\n")

    records = tail_jsonl(path, limit=4)

    assert [record["index"] for record in records] == [16, 17, 18, 19]
