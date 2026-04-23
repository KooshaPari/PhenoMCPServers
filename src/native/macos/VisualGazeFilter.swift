import AppKit
import Foundation

final class VisualGazeFilter {
    private var point: CGPoint?
    private var lastObservedAt = ""

    func update(raw: CGPoint, eye: EyeState, screen: CGRect) -> CGPoint {
        if point == nil {
            point = CGPoint(x: screen.midX, y: screen.midY)
        }
        guard eye.fresh, eye.state != "no_face" else {
            return point ?? raw
        }
        if eye.observedAt == lastObservedAt {
            return point ?? raw
        }
        lastObservedAt = eye.observedAt

        let current = point ?? raw
        let confidence = max(0.0, min(1.0, eye.confidence > 0 ? eye.confidence : eye.score))
        let stability = max(0.0, min(1.0, eye.stabilityScore))
        let dx = raw.x - current.x
        let dy = raw.y - current.y
        let distance = hypot(dx, dy)
        if distance < 1 {
            return current
        }

        let diagonal = hypot(screen.width, screen.height)
        let unstable = !eye.targetingReliable || stability < 0.4
        let rawLooksLikeOutlier = distance > diagonal * 0.16 && (confidence < 0.55 || unstable)
        let maxStep = rawLooksLikeOutlier ? 6.0 : (10.0 + confidence * 18.0 + stability * 30.0)
        let alpha = rawLooksLikeOutlier ? 0.015 : (0.028 + confidence * 0.08 + stability * 0.08)
        let intendedStep = min(distance * alpha, maxStep)
        let next = CGPoint(x: current.x + dx / distance * intendedStep, y: current.y + dy / distance * intendedStep)
        point = CGPoint(
            x: max(screen.minX, min(screen.maxX, next.x)),
            y: max(screen.minY, min(screen.maxY, next.y))
        )
        return point ?? current
    }
}
