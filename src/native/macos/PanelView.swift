import AppKit
import Foundation

final class PanelView: NSView {
    let model: StatusModel
    var onCalibrationAction: (() -> Void)?

    init(model: StatusModel) {
        self.model = model
        super.init(frame: .zero)
        wantsLayer = true
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.clear.setFill()
        dirtyRect.fill()
        drawPanel()
    }

    override func mouseDown(with event: NSEvent) {
        let point = convert(event.locationInWindow, from: nil)
        if calibrationActionFrame().contains(point) || calibrationBadgeFrame().contains(point) {
            onCalibrationAction?()
            return
        }
        super.mouseDown(with: event)
    }

    override func resetCursorRects() {
        addCursorRect(calibrationActionFrame(), cursor: .pointingHand)
        addCursorRect(calibrationBadgeFrame(), cursor: .pointingHand)
    }

    private func drawPanel() {
        let panel = bounds.insetBy(dx: 10, dy: 10)
        NSColor(calibratedRed: 0.10, green: 0.11, blue: 0.14, alpha: 0.97).setFill()
        NSBezierPath(roundedRect: panel, xRadius: 8, yRadius: 8).fill()

        var y = panel.maxY - 32
        drawText("Agent \(model.status.status)", x: panel.minX + 16, y: y, size: 18, weight: .semibold)
        let badgeText = model.eye.calibrationBannerText
        drawPill(
            text: badgeText,
            frame: calibrationBadgeFrame(in: panel, y: y),
            fill: badgeText == "Tracking" ? NSColor.systemGreen : (badgeText == "Projection hold" ? NSColor.systemOrange : NSColor.systemRed)
        )
        y -= 28
        drawText("ETA \(model.status.eta)", x: panel.minX + 16, y: y, size: 11, color: NSColor(calibratedWhite: 0.82, alpha: 1))
        drawText("Confidence \(fmt(model.status.confidence))", x: panel.maxX - 162, y: y, size: 11, color: NSColor(calibratedWhite: 0.82, alpha: 1))

        let sessionTop = panel.maxY - 74
        let sessionBottom = sessionTop - 106
        drawSection(
            title: "Agent Sessions",
            frame: CGRect(x: panel.minX + 10, y: sessionBottom, width: panel.width - 20, height: 106),
            accent: model.sessionSnapshot.activeCount > 0 ? NSColor.systemGreen : NSColor.systemGray
        ) { section in
            drawSessionSummary(in: section)
        }

        let calibrationTop = sessionBottom - 102
        drawSection(
            title: "Calibration",
            frame: CGRect(x: panel.minX + 10, y: calibrationTop, width: panel.width - 20, height: 98),
            accent: model.eye.calibrationRecommendedAction == "recalibrate" || model.eye.calibrationQualityLabel == "poor"
                ? NSColor.systemRed
                : (model.eye.projectionHoldActive ? NSColor.systemOrange : NSColor.systemGreen)
        ) { section in
            let action = model.eye.calibrationActionText
            drawMetricGrid(
                in: section,
                left: [
                    ("QUALITY", model.eye.calibrationQualityLabel),
                    ("MEAN", model.eye.calibrationMeanErrorPx.map { "\(Int($0)) px" } ?? "n/a"),
                    ("P95", model.eye.calibrationP95ErrorPx.map { "\(Int($0)) px" } ?? "n/a"),
                    ("SAMPLES", model.eye.calibrationSampleCount.map { "\($0)" } ?? "n/a")
                ],
                right: [
                    ("ACTION", action),
                    ("HOLD", model.eye.projectionHoldActive ? "projection hold" : "tracking"),
                    ("REASON", model.eye.projectionHoldReason.replacingOccurrences(of: "_", with: " ")),
                    ("DETAIL", model.eye.calibrationDetailText)
                ]
            )
            drawActionButton(model.eye.calibrationPrimaryActionTitle, frame: calibrationActionFrame(in: section))
        }

        drawSection(
            title: "Stability",
            frame: CGRect(x: panel.minX + 10, y: calibrationTop - 102, width: panel.width - 20, height: 98),
            accent: model.eye.targetingReliable ? NSColor.systemBlue : NSColor.systemOrange
        ) { section in
            drawMetricGrid(
                in: section,
                left: [
                    ("JUMP", "\(Int(model.eye.jumpPx)) px"),
                    ("JITTER", "\(Int(model.eye.jitterPx)) px"),
                    ("VELOCITY", "\(Int(model.eye.velocityPxS)) px/s")
                ],
                right: [
                    ("TARGET", model.eye.targetingReliable ? "reliable" : "held"),
                    ("COORD", coord(model.eyePoint())),
                    ("SCORE", fmt(model.eye.stabilityScore))
                ]
            )
        }

        drawSection(
            title: "Target",
            frame: CGRect(x: panel.minX + 10, y: calibrationTop - 204, width: panel.width - 20, height: 98),
            accent: NSColor(calibratedWhite: 0.58, alpha: 1)
        ) { section in
            let targetTitle = model.target.title.isEmpty ? "(no title)" : model.target.title
            let targetOwner = "\(model.target.owner) [\(model.target.pid)]"
            drawMetricGrid(
                in: section,
                left: [
                    ("PROCESS", targetOwner),
                    ("WINDOW", targetTitle),
                    ("AGENT", model.target.agentSurface)
                ],
                right: [
                    ("RESOLUTION", model.target.resolution),
                    ("HOOK", model.target.hookStatus),
                    ("TOOLS", model.commandStatus)
                ]
            )
        }
    }

    private func drawSection(title: String, frame: CGRect, accent: NSColor, body: (CGRect) -> Void) {
        let card = frame.insetBy(dx: 0, dy: 0)
        NSColor(calibratedRed: 0.16, green: 0.17, blue: 0.21, alpha: 0.96).setFill()
        NSBezierPath(roundedRect: card, xRadius: 7, yRadius: 7).fill()
        accent.withAlphaComponent(0.6).setStroke()
        let border = NSBezierPath(roundedRect: card, xRadius: 7, yRadius: 7)
        border.lineWidth = 1
        border.stroke()
        drawText(title.uppercased(), x: card.minX + 12, y: card.maxY - 14, size: 10, weight: .semibold, color: NSColor(calibratedWhite: 0.78, alpha: 1))
        body(card.insetBy(dx: 12, dy: 18))
    }

    private func drawMetricGrid(in section: CGRect, left: [(String, String)], right: [(String, String)]) {
        let leftX = section.minX
        let rightX = section.midX + 4
        let width = section.width / 2 - 8
        var y = section.maxY - 8
        for item in left {
            drawMetric(label: item.0, value: item.1, x: leftX, y: y, width: width)
            y -= 20
        }
        y = section.maxY - 8
        for item in right {
            drawMetric(label: item.0, value: item.1, x: rightX, y: y, width: width)
            y -= 20
        }
    }

    private func drawMetric(label: String, value: String, x: CGFloat, y: CGFloat, width: CGFloat) {
        drawText(label, x: x, y: y, size: 10, weight: .semibold, color: NSColor(calibratedWhite: 0.68, alpha: 1), maxWidth: width * 0.45)
        drawText(value, x: x + width * 0.45, y: y, size: 11, color: .white, maxWidth: width * 0.55)
    }

    private func drawSessionSummary(in section: CGRect) {
        let snapshot = model.sessionSnapshot
        drawMetricGrid(
            in: CGRect(x: section.minX, y: section.maxY - 44, width: section.width, height: 44),
            left: [
                ("ACTIVE", "\(snapshot.activeCount)"),
                ("CHILD", "\(snapshot.childAgentCount)")
            ],
            right: [
                ("STALE HOOKS", "\(snapshot.staleHookCount)"),
                ("ATTR CONF", snapshot.attributionConfidenceText)
            ]
        )

        let rows = Array(snapshot.sessions.prefix(2))
        var y = section.minY + 14
        if rows.isEmpty {
            drawText("No session heartbeats", x: section.minX, y: y, size: 11, color: NSColor(calibratedWhite: 0.78, alpha: 1), maxWidth: section.width)
            return
        }
        for session in rows.reversed() {
            let marker = session.fresh ? "live" : "stale"
            let event = session.latestEventType == "-" ? session.state : session.latestEventType
            let child = session.isChildAgent ? " child" : ""
            let text = "\(marker) \(session.agentID)\(child) \(short(session.sessionID)): \(event)"
            drawText(text, x: section.minX, y: y, size: 11, color: .white, maxWidth: section.width)
            y += 16
        }
    }

    private func drawPill(text: String, frame: CGRect, fill: NSColor) {
        fill.withAlphaComponent(0.22).setFill()
        NSBezierPath(roundedRect: frame, xRadius: 10, yRadius: 10).fill()
        fill.withAlphaComponent(0.9).setStroke()
        let path = NSBezierPath(roundedRect: frame, xRadius: 10, yRadius: 10)
        path.lineWidth = 1
        path.stroke()
        drawText(text, x: frame.minX, y: frame.minY + 4, size: 9, weight: .semibold, color: fill, maxWidth: frame.width, center: true)
    }

    private func drawActionButton(_ text: String, frame: CGRect) {
        let fill = model.eye.calibrationPrimaryActionTitle == "Recalibrate" ? NSColor.systemRed : NSColor.systemBlue
        fill.withAlphaComponent(0.28).setFill()
        NSBezierPath(roundedRect: frame, xRadius: 6, yRadius: 6).fill()
        fill.withAlphaComponent(0.95).setStroke()
        let outline = NSBezierPath(roundedRect: frame, xRadius: 6, yRadius: 6)
        outline.lineWidth = 1
        outline.stroke()
        drawText(text, x: frame.minX, y: frame.minY + 7, size: 10, weight: .semibold, color: .white, maxWidth: frame.width, center: true)
    }

    private func calibrationBadgeFrame() -> CGRect {
        let panel = bounds.insetBy(dx: 10, dy: 10)
        return calibrationBadgeFrame(in: panel, y: panel.maxY - 32)
    }

    private func calibrationBadgeFrame(in panel: CGRect, y: CGFloat) -> CGRect {
        CGRect(x: panel.maxX - 118, y: y - 2, width: 96, height: 20)
    }

    private func calibrationActionFrame() -> CGRect {
        let panel = bounds.insetBy(dx: 10, dy: 10)
        let sessionTop = panel.maxY - 74
        let sessionBottom = sessionTop - 106
        let calibrationTop = sessionBottom - 102
        let section = CGRect(x: panel.minX + 22, y: calibrationTop + 18, width: panel.width - 44, height: 62)
        return calibrationActionFrame(in: section)
    }

    private func calibrationActionFrame(in section: CGRect) -> CGRect {
        CGRect(x: section.maxX - 84, y: section.minY + 2, width: 78, height: 24)
    }

    private func coord(_ point: CGPoint) -> String {
        "\(Int(point.x)), \(Int(point.y))"
    }

    private func fmt(_ value: Double) -> String {
        String(format: "%.2f", value)
    }

    private func short(_ value: String) -> String {
        if value.count <= 14 {
            return value
        }
        return String(value.prefix(11)) + "..."
    }

    private func drawText(
        _ text: String,
        x: CGFloat,
        y: CGFloat,
        size: CGFloat,
        weight: NSFont.Weight = .regular,
        color: NSColor = .white,
        maxWidth: CGFloat = 310,
        center: Bool = false
    ) {
        let clipped = text.count > 72 ? String(text.prefix(69)) + "..." : text
        let paragraph = NSMutableParagraphStyle()
        paragraph.alignment = center ? .center : .left
        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: size, weight: weight),
            .foregroundColor: color,
            .paragraphStyle: paragraph
        ]
        clipped.draw(in: CGRect(x: x, y: y - size, width: maxWidth, height: size + 8), withAttributes: attrs)
    }
}
