import AppKit
import CoreGraphics

final class DotOverlayView: NSView {
    let model: StatusModel

    init(model: StatusModel) {
        self.model = model
        super.init(frame: .zero)
        wantsLayer = true
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func draw(_ dirtyRect: NSRect) {
        drawEyeDot()
    }

    private func drawEyeDot() {
        let point = model.eyePoint()
        let screen = NSScreen.main?.frame ?? CGRect(x: 0, y: 0, width: 1440, height: 900)
        let localX = max(18, min(bounds.width - 18, point.x - screen.minX))
        let localY = max(18, min(bounds.height - 18, bounds.height - (point.y - screen.minY)))
        let radius = CGFloat(model.eye.targetingReliable ? 11 : 8)
        let rect = CGRect(x: localX - radius, y: localY - radius, width: radius * 2, height: radius * 2)
        let dotColor = model.eye.targetingReliable
            ? NSColor(calibratedRed: 0.1, green: 0.72, blue: 0.45, alpha: model.eye.fresh ? 0.88 : 0.2)
            : NSColor(calibratedRed: 0.93, green: 0.58, blue: 0.15, alpha: model.eye.fresh ? 0.78 : 0.2)
        dotColor.setFill()
        NSBezierPath(ovalIn: rect).fill()
        NSColor.white.withAlphaComponent(model.eye.targetingReliable ? 0.7 : 0.3).setStroke()
        let ring = NSBezierPath(ovalIn: rect.insetBy(dx: -5, dy: -5))
        ring.lineWidth = 1.5
        ring.stroke()
    }
}
