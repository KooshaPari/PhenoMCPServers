import AppKit
import Foundation

final class CalibrationEvalController: NSObject {
    static let shared = CalibrationEvalController()

    private var window: NSPanel?
    private var view: CalibrationEvalView?
    private var timer: Timer?
    private var model: StatusModel?
    private var samples: [(target: CGPoint, observed: CGPoint)] = []
    private var points: [CGPoint] = []
    private var index = 0
    private var started = Date()
    private var evalStats = CalibrationEvalStats(targetCount: 0)
    private var isRefreshing = false
    private let settleSeconds: TimeInterval = 0.7
    private let secondsPerPoint: TimeInterval = 2.0
    private let minSamplesPerPoint = 4

    func start(model: StatusModel) {
        self.model = model
        let screen = NSScreen.main?.frame ?? CGRect(x: 0, y: 0, width: 1440, height: 900)
        points = CalibrationEvalController.targets(in: screen)
        samples = []
        index = 0
        started = Date()
        evalStats = CalibrationEvalStats(targetCount: points.count)
        isRefreshing = false
        let panel = NSPanel(contentRect: screen, styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.backgroundColor = .black
        panel.level = .statusBar
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        let evalView = CalibrationEvalView(frame: screen)
        evalView.target = points.first ?? screen.center
        evalView.caption = "Look at the dot"
        panel.contentView = evalView
        panel.orderFrontRegardless()
        window = panel
        view = evalView
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 0.12, repeats: true) { _ in self.tick() }
    }

    private func tick() {
        guard let model, let view else { return }
        if isRefreshing {
            return
        }
        let elapsed = Date().timeIntervalSince(started)
        if elapsed < settleSeconds {
            return
        }
        isRefreshing = true
        model.refreshEye {
            self.isRefreshing = false
            guard self.index < self.points.count else { return }
            let eye = model.eye
            if eye.fresh, eye.targetingReliable, eye.confidence >= 0.35 {
                let point = model.rawEyePoint()
                if let reason = self.evalStats.inspectSample(index: self.index, point: point, observedAt: eye.observedAt) {
                    self.evalStats.reject(index: self.index, reason: reason)
                } else {
                    self.samples.append((self.points[self.index], point))
                    self.evalStats.accept(index: self.index)
                }
            } else {
                self.evalStats.reject(index: self.index, reason: self.rejectReason(for: eye))
            }

            if Date().timeIntervalSince(self.started) >= self.secondsPerPoint {
                self.advancePoint(view: view)
            }
        }
    }

    private func advancePoint(view: CalibrationEvalView) {
        index += 1
        if index >= points.count {
            finish()
            return
        }
        view.target = points[index]
        view.caption = "\(index + 1)/\(points.count)"
        view.needsDisplay = true
        started = Date()
    }

    private func finish() {
        timer?.invalidate()
        timer = nil
        window?.close()
        window = nil
        guard !samples.isEmpty else {
            showAlert(
                title: "Calibration Evaluation",
                detail: "No fresh reliable gaze samples were available.\nRejected samples: \(evalStats.rejected)\n\(evalStats.summary())\nStart or recalibrate the eye tracker, then retry."
            )
            return
        }
        let errors = samples.map { hypot($0.target.x - $0.observed.x, $0.target.y - $0.observed.y) }.sorted()
        let mean = errors.reduce(0, +) / CGFloat(errors.count)
        let p95 = errors[min(errors.count - 1, Int(Double(errors.count - 1) * 0.95))]
        let expectedSamples = points.count * minSamplesPerPoint
        let quality = errors.count >= expectedSamples ? "usable sample volume" : "low sample volume"
        showAlert(
            title: "Calibration Evaluation",
            detail: "Mean error: \(Int(mean)) px\nP95 error: \(Int(p95)) px\nSamples: \(errors.count) (\(quality))\nRejected samples: \(evalStats.rejected)\n\(evalStats.summary())"
        )
    }

    private func rejectReason(for eye: EyeState) -> String {
        if !eye.fresh {
            return "stale"
        }
        if !eye.targetingReliable {
            return "unreliable"
        }
        if eye.confidence < 0.35 {
            return "low_confidence"
        }
        return "unknown"
    }

    private func showAlert(title: String, detail: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = detail
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }

    private static func targets(in screen: CGRect) -> [CGPoint] {
        let xs = [screen.minX + screen.width * 0.12, screen.midX, screen.minX + screen.width * 0.88]
        let ys = [screen.minY + screen.height * 0.14, screen.midY, screen.minY + screen.height * 0.86]
        return ys.flatMap { y in xs.map { x in CGPoint(x: x, y: y) } }
    }
}

final class CalibrationEvalView: NSView {
    var target = CGPoint.zero
    var caption = ""

    override func draw(_ dirtyRect: NSRect) {
        NSColor.black.setFill()
        dirtyRect.fill()
        let local = CGPoint(x: target.x - frame.minX, y: bounds.height - (target.y - frame.minY))
        NSColor(calibratedRed: 0.1, green: 0.72, blue: 0.45, alpha: 1).setFill()
        NSBezierPath(ovalIn: CGRect(x: local.x - 18, y: local.y - 18, width: 36, height: 36)).fill()
        NSColor.white.setStroke()
        let ring = NSBezierPath(ovalIn: CGRect(x: local.x - 34, y: local.y - 34, width: 68, height: 68))
        ring.lineWidth = 2
        ring.stroke()
        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: 22, weight: .medium),
            .foregroundColor: NSColor.white,
        ]
        caption.draw(at: CGPoint(x: 40, y: bounds.height - 70), withAttributes: attrs)
    }
}

private extension CGRect {
    var center: CGPoint { CGPoint(x: midX, y: midY) }
}
