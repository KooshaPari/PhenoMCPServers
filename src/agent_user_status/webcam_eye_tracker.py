#!/usr/bin/env python3
"""Opt-in webcam gaze collector that publishes only derived screen coordinates."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

from agent_user_status.eye_publish import EyePublishConfig, PublishError, post_eye
from agent_user_status.eye_smoothing import AdaptiveGazeSmoother
from agent_user_status.gaze_calibration import (
    calibration_points,
    fit_calibration,
    load_calibration_quality,
    predict,
    projection_thresholds,
)
from agent_user_status.gaze_drift_correction import apply_drift_correction, load_drift_correction
from agent_user_status.gaze_evaluation import EvaluationCounters
from agent_user_status.gaze_projection import ProjectionHoldGate, StableSampleGate
from agent_user_status.webcam_support import (
    TrackerError,
    create_face_mesh,
    frame_sample,
    import_cv2,
    import_mediapipe,
    import_numpy,
    open_camera,
    screen_size,
)

STATE_DIR = Path(os.environ.get("AGENT_IMESSAGE_STATE_DIR", "~/.local/share/agent-imessage/state")).expanduser()
CALIBRATION_PATH = Path(
    os.environ.get("AGENT_USER_STATUS_EYE_CALIBRATION", str(STATE_DIR / "eye_calibration.json"))
).expanduser()
STATUSD_URL = os.environ.get("AGENT_USER_STATUSD_URL", "http://127.0.0.1:8765")


def default_camera() -> int:
    try:
        return int(os.environ.get("AGENT_USER_STATUS_EYE_CAMERA", "0"))
    except ValueError:
        return 0


def load_calibration(path: Path = CALIBRATION_PATH) -> dict[str, Any]:
    if not path.exists():
        raise TrackerError(f"calibration missing: run `agent-user-status-webcam-eye-tracker calibrate` first ({path})")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("kind") != "mediapipe_iris_regression":
        raise TrackerError(f"unsupported calibration kind in {path}")
    return payload


def summarize_errors(errors: list[float]) -> dict[str, float]:
    if not errors:
        return {"mean_error_px": 0.0, "p95_error_px": 0.0, "max_error_px": 0.0}
    np = import_numpy()
    ordered = np.asarray(errors, dtype=float)
    return {
        "mean_error_px": float(ordered.mean()),
        "p95_error_px": float(np.percentile(ordered, 95)),
        "max_error_px": float(ordered.max()),
    }


def command_calibrate(args: argparse.Namespace) -> int:
    cv2 = import_cv2()
    screen = screen_size()
    cap = open_camera(args.camera, args.width, args.height)
    face_mesh = create_face_mesh()
    samples: list[tuple[list[float], float, float]] = []
    sample_gate = StableSampleGate(args.min_sample_confidence, args.min_consecutive_frames)
    window_name = "Agent User Status Eye Calibration"

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    points = calibration_points(screen)
    try:
        for idx, (target_x, target_y) in enumerate(points, start=1):
            started = time.monotonic()
            kept = 0
            while time.monotonic() - started < args.seconds_per_point:
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                sample = frame_sample(face_mesh, frame)
                elapsed = time.monotonic() - started
                if sample is None or sample.confidence < args.min_sample_confidence:
                    sample_gate.reset()
                elif elapsed > args.settle_seconds and sample_gate.update(sample.confidence):
                    samples.append((sample.features, float(target_x), float(target_y)))
                    kept += 1

                canvas = cv2.UMat(screen.height, screen.width, cv2.CV_8UC3).get()
                canvas[:] = (18, 18, 18)
                cv2.circle(canvas, (target_x, target_y), 18, (87, 207, 136), -1)
                cv2.circle(canvas, (target_x, target_y), 34, (255, 255, 255), 2)
                cv2.putText(
                    canvas,
                    f"{idx}/{len(points)}  samples {kept}  look at the dot",
                    (40, 54),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (240, 240, 240),
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow(window_name, canvas)
                if cv2.waitKey(1) == 27:
                    raise TrackerError("calibration cancelled")
        calibration = fit_calibration(samples, screen)
        calibration.update(load_calibration_quality(calibration, screen))
        CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        CALIBRATION_PATH.write_text(json.dumps(calibration, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, "calibration": str(CALIBRATION_PATH), **calibration}, indent=2))
        return 0
    finally:
        cap.release()
        cv2.destroyAllWindows()
        face_mesh.close()


def command_run(args: argparse.Namespace) -> int:
    screen = screen_size()
    calibration = load_calibration()
    calibration_quality = load_calibration_quality(calibration, screen)
    hold_threshold_px, release_threshold_px = projection_thresholds(calibration, screen)
    cap = open_camera(args.camera, args.width, args.height)
    face_mesh = create_face_mesh()
    publisher = EyePublishConfig(statusd_url=STATUSD_URL)
    smoother = AdaptiveGazeSmoother(
        min_cutoff=args.min_cutoff,
        beta=args.beta,
        derivative_cutoff=args.derivative_cutoff,
        max_jump_px=args.max_jump_px,
    )
    hold_gate = ProjectionHoldGate(
        hold_threshold_px=hold_threshold_px,
        release_threshold_px=release_threshold_px,
        calibration_quality_score=float(calibration_quality.get("calibration_quality_score", 0.0) or 0.0),
        calibration_recommended_action=str(
            calibration_quality.get("calibration_recommended_action") or "monitor"
        ),
        min_confidence=args.min_sample_confidence,
    )
    frame_period = 1.0 / args.hz
    last_no_face_post = 0.0
    stopped = False

    def stop(_signum: int, _frame: Any) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while not stopped:
            started = time.monotonic()
            ok, frame = cap.read()
            if ok and frame is not None:
                sample = frame_sample(face_mesh, frame)
                if sample is not None:
                    raw_point = predict(calibration, sample.features)
                    correction = load_drift_correction()
                    corrected_point = apply_drift_correction(raw_point, screen, correction)
                    confidence = min(1.0, sample.confidence * args.confidence_scale)
                    stable_state = smoother.snapshot()
                    decision = hold_gate.update(
                        corrected_point,
                        screen,
                        confidence,
                        float(stable_state.get("stability_score", confidence) or confidence),
                        smoother.current(),
                    )
                    if decision.should_reset:
                        smoother.reset(
                            decision.smooth_point or decision.publish_point,
                            time.monotonic(),
                            confidence=confidence,
                        )
                    if decision.smooth_point is None:
                        smoothed = decision.publish_point
                        stability = {
                            **smoother.snapshot(),
                            "stability_score": 0.0,
                            "targeting_reliable": False,
                            "filter_mode": decision.mode,
                        }
                    else:
                        smoothed = smoother.update(
                            decision.smooth_point,
                            time.monotonic(),
                            confidence=confidence if decision.targeting_reliable else min(confidence, 0.4),
                        )
                        stability = smoother.snapshot()
                    try:
                        post_eye(
                            smoothed,
                            screen,
                            confidence,
                            max_age=max(2, int(args.max_age_seconds)),
                            config=publisher,
                            extra={
                                **stability,
                                **calibration_quality,
                                "observed_screen_x": round(raw_point[0], 2),
                                "observed_screen_y": round(raw_point[1], 2),
                                "correction_offset_x_px": correction.get("screen_x_offset_px") if correction else None,
                                "correction_offset_y_px": correction.get("screen_y_offset_px") if correction else None,
                                "correction_sample_count": correction.get("sample_count") if correction else None,
                                "correction_reliability_score": (
                                    correction.get("reliability_score") if correction else None
                                ),
                                "correction_updated_at": correction.get("created_at") if correction else None,
                                "projection_error_px": decision.projection_error_px,
                                "projection_offscreen_px": decision.projection_offscreen_px,
                                "projection_hold_active": decision.hold_active,
                                "projection_hold_reason": decision.hold_reason,
                                "projection_hold_hint": decision.hold_hint,
                                "projection_hold_samples": decision.stable_frames,
                                "projection_hold_threshold_px": decision.hold_threshold_px,
                                "projection_release_threshold_px": decision.release_threshold_px,
                                "projection_recovery_score": decision.recovery_score,
                                "projection_hold_budget_frames": decision.hold_budget_frames,
                                "projection_anchor_x": (
                                    round(decision.anchor_point[0], 2) if decision.anchor_point else None
                                ),
                                "projection_anchor_y": (
                                    round(decision.anchor_point[1], 2) if decision.anchor_point else None
                                ),
                                "projection_recommended_action": calibration_quality.get(
                                    "calibration_recommended_action"
                                ),
                                "filter_mode": decision.mode,
                                "targeting_reliable": bool(
                                    decision.targeting_reliable
                                    and bool(stability.get("targeting_reliable", True))
                                ),
                            },
                        )
                    except PublishError:
                        pass
                elif started - last_no_face_post >= 1.0:
                    try:
                        post_eye(
                            (screen.width / 2, screen.height / 2),
                            screen,
                            0.0,
                            max_age=2,
                            config=publisher,
                            state="presence_missing",
                        )
                    except PublishError:
                        pass
                    last_no_face_post = started
            sleep_for = frame_period - (time.monotonic() - started)
            if sleep_for > 0:
                time.sleep(sleep_for)
        return 0
    finally:
        cap.release()
        face_mesh.close()


def command_evaluate(args: argparse.Namespace) -> int:
    cv2 = import_cv2()
    screen = screen_size()
    calibration = load_calibration()
    hold_threshold_px, release_threshold_px = projection_thresholds(calibration, screen)
    cap = open_camera(args.camera, args.width, args.height)
    face_mesh = create_face_mesh()
    counters = EvaluationCounters()
    sample_gate = StableSampleGate(args.min_sample_confidence, args.min_consecutive_frames)
    window_name = "Agent User Status Eye Evaluation"
    points = calibration_points(screen)

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    try:
        for idx, (target_x, target_y) in enumerate(points, start=1):
            started = time.monotonic()
            target = counters.begin_target(idx, target_x, target_y)
            while time.monotonic() - started < args.seconds_per_point:
                ok, frame = cap.read()
                if not ok or frame is None:
                    target.reject("camera_frame_unavailable")
                    continue
                sample = frame_sample(face_mesh, frame)
                if sample is None:
                    target.reject("no_face_sample")
                    sample_gate.reset()
                    continue
                if sample.confidence < args.min_sample_confidence:
                    target.reject("low_confidence")
                    sample_gate.reset()
                    continue
                if time.monotonic() - started <= args.settle_seconds:
                    target.reject("settling")
                    continue
                if not sample_gate.update(sample.confidence):
                    target.reject("unstable_confidence")
                    continue

                observed = predict(calibration, sample.features)
                sample_health = counters.inspect_observed_sample(observed)
                if sample_health:
                    target.reject(sample_health)
                    continue
                target.accept(observed)

                canvas = cv2.UMat(screen.height, screen.width, cv2.CV_8UC3).get()
                canvas[:] = (18, 18, 18)
                cv2.circle(canvas, (target_x, target_y), 18, (87, 207, 136), -1)
                cv2.circle(canvas, (target_x, target_y), 34, (255, 255, 255), 2)
                cv2.putText(
                    canvas,
                    f"{idx}/{len(points)}  look at the dot",
                    (40, 54),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (240, 240, 240),
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow(window_name, canvas)
                if cv2.waitKey(1) == 27:
                    raise TrackerError("evaluation cancelled")

        summary = summarize_errors(counters.errors)
        summary.update(
            {
                "hold_threshold_px": round(hold_threshold_px, 2),
                "release_threshold_px": round(release_threshold_px, 2),
                **counters.summary(hold_threshold_px),
                **load_calibration_quality(calibration, screen),
            }
        )
        print(json.dumps({"ok": True, "evaluation": summary}, indent=2))
        return 0
    finally:
        cap.release()
        cv2.destroyAllWindows()
        face_mesh.close()


def command_check(args: argparse.Namespace) -> int:
    payload = {
        "python": sys.executable,
        "calibration": str(CALIBRATION_PATH),
        "calibrated": CALIBRATION_PATH.exists(),
        "statusd_url": STATUSD_URL,
    }
    for name, loader in (("cv2", import_cv2), ("numpy", import_numpy), ("mediapipe", import_mediapipe)):
        try:
            module = loader()
            payload[name] = getattr(module, "__version__", "ok")
        except Exception as exc:
            payload[name] = f"missing: {exc}"
    print(json.dumps(payload, indent=2))
    return 0


def command_probe(args: argparse.Namespace) -> int:
    cap = open_camera(args.camera, args.width, args.height)
    try:
        ok, frame = cap.read()
        if not ok or frame is None:
            raise TrackerError("camera opened but did not return a frame")
        result = {"ok": True, "camera": args.camera, "width": int(frame.shape[1]), "height": int(frame.shape[0])}
        print(json.dumps(result, indent=2))
        return 0
    finally:
        cap.release()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Opt-in webcam gaze tracker for agent-user-status")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Check optional eye-tracking dependencies")
    check.set_defaults(func=command_check)

    probe = sub.add_parser("probe-camera", help="Open the camera and read one frame without storing it")
    probe.add_argument("--camera", type=int, default=default_camera())
    probe.add_argument("--width", type=int, default=1280)
    probe.add_argument("--height", type=int, default=720)
    probe.set_defaults(func=command_probe)

    calibrate = sub.add_parser("calibrate", help="Collect 9-point calibration from the MacBook webcam")
    calibrate.add_argument("--camera", type=int, default=default_camera())
    calibrate.add_argument("--width", type=int, default=1280)
    calibrate.add_argument("--height", type=int, default=720)
    calibrate.add_argument("--seconds-per-point", type=float, default=2.0)
    calibrate.add_argument("--settle-seconds", type=float, default=0.55)
    calibrate.add_argument("--min-sample-confidence", type=float, default=0.35)
    calibrate.add_argument("--min-consecutive-frames", type=int, default=2)
    calibrate.set_defaults(func=command_calibrate)

    evaluate = sub.add_parser("evaluate", help="Evaluate a saved calibration against a 9-point screen target")
    evaluate.add_argument("--camera", type=int, default=default_camera())
    evaluate.add_argument("--width", type=int, default=1280)
    evaluate.add_argument("--height", type=int, default=720)
    evaluate.add_argument("--seconds-per-point", type=float, default=1.6)
    evaluate.add_argument("--settle-seconds", type=float, default=0.4)
    evaluate.add_argument("--min-sample-confidence", type=float, default=0.35)
    evaluate.add_argument("--min-consecutive-frames", type=int, default=2)
    evaluate.set_defaults(func=command_evaluate)

    run = sub.add_parser("run", help="Publish calibrated derived gaze coordinates to statusd")
    run.add_argument("--camera", type=int, default=default_camera())
    run.add_argument("--width", type=int, default=1280)
    run.add_argument("--height", type=int, default=720)
    run.add_argument("--hz", type=float, default=12.0)
    run.add_argument("--min-cutoff", type=float, default=1.15)
    run.add_argument("--beta", type=float, default=0.012)
    run.add_argument("--derivative-cutoff", type=float, default=1.0)
    run.add_argument("--max-jump-px", type=float, default=620.0)
    run.add_argument("--confidence-scale", type=float, default=1.0)
    run.add_argument("--min-sample-confidence", type=float, default=0.35)
    run.add_argument("--max-age-seconds", type=int, default=3)
    run.set_defaults(func=command_run)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        return int(args.func(args))
    except TrackerError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
