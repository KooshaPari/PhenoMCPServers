from __future__ import annotations

from agent_user_status.gaze_evaluation import EvaluationCounters


def test_evaluation_counters_report_rejection_reasons_per_target() -> None:
    counters = EvaluationCounters()
    first = counters.begin_target(1, 100, 100)
    first.reject("settling")
    first.reject("settling")
    first.reject("low_confidence")
    first.accept((103.0, 104.0))

    second = counters.begin_target(2, 500, 400)
    second.reject("no_face_sample")
    second.accept((700.0, 400.0))

    summary = counters.summary(hold_threshold_px=120.0)

    assert summary["accepted_total"] == 2
    assert summary["rejected_total"] == 4
    assert summary["rejected_by_reason"] == {
        "low_confidence": 1,
        "no_face_sample": 1,
        "settling": 2,
    }
    assert summary["projection_hold_candidate_count"] == 1
    assert summary["targets"][0]["accepted"] == 1
    assert summary["targets"][0]["rejected"]["settling"] == 2
