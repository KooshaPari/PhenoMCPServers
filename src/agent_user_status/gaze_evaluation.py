"""Privacy-safe gaze calibration evaluation counters."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TargetEvaluation:
    target_index: int
    target_x: int
    target_y: int
    accepted: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    errors: list[float] = field(default_factory=list)

    def accept(self, observed: tuple[float, float]) -> None:
        self.accepted += 1
        self.errors.append(math.hypot(observed[0] - self.target_x, observed[1] - self.target_y))

    def reject(self, reason: str) -> None:
        self.rejected[reason] = self.rejected.get(reason, 0) + 1

    def summary(self) -> dict[str, Any]:
        return {
            "target_index": self.target_index,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "accepted": self.accepted,
            "rejected": dict(sorted(self.rejected.items())),
            "mean_error_px": round(sum(self.errors) / len(self.errors), 2) if self.errors else None,
            "max_error_px": round(max(self.errors), 2) if self.errors else None,
        }


@dataclass
class EvaluationCounters:
    targets: list[TargetEvaluation] = field(default_factory=list)

    def begin_target(self, target_index: int, target_x: int, target_y: int) -> TargetEvaluation:
        target = TargetEvaluation(target_index=target_index, target_x=target_x, target_y=target_y)
        self.targets.append(target)
        return target

    @property
    def errors(self) -> list[float]:
        return [error for target in self.targets for error in target.errors]

    def rejected_totals(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for target in self.targets:
            for reason, count in target.rejected.items():
                totals[reason] = totals.get(reason, 0) + count
        return dict(sorted(totals.items()))

    def summary(self, hold_threshold_px: float) -> dict[str, Any]:
        errors = self.errors
        hold_count = sum(1 for error in errors if error > hold_threshold_px)
        return {
            "sample_count": len(errors),
            "accepted_total": len(errors),
            "rejected_total": sum(self.rejected_totals().values()),
            "rejected_by_reason": self.rejected_totals(),
            "projection_hold_candidate_count": hold_count,
            "projection_hold_rate": round(hold_count / len(errors), 4) if errors else 0.0,
            "targets": [target.summary() for target in self.targets],
        }
