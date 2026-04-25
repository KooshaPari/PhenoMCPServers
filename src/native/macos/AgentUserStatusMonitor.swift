import AppKit
import CoreGraphics
import Foundation

let baseURL = URL(string: "http://127.0.0.1:8765")!

struct EyeState {
    var score: Double = 0
    var confidence: Double = 0
    var state: String = "unknown"
    var screenZone: String = "center"
    var x: Double?
    var y: Double?
    var observedX: Double?
    var observedY: Double?
    var screenWidth: Double?
    var screenHeight: Double?
    var stabilityScore: Double = 0
    var jumpPx: Double = 0
    var jitterPx: Double = 0
    var velocityPxS: Double = 0
    var calibrationMeanErrorPx: Double?
    var calibrationP95ErrorPx: Double?
    var calibrationSampleCount: Int?
    var calibrationQualityLabel: String = "unknown"
    var calibrationRecommendedAction: String = "unknown"
    var correctionOffsetXPx: Double?
    var correctionOffsetYPx: Double?
    var correctionSampleCount: Int?
    var correctionReliabilityScore: Double?
    var correctionUpdatedAt: String?
    var headYawDeg: Double?
    var headPitchDeg: Double?
    var headRollDeg: Double?
    var framingQuality: Double?
    var framingState: String = "unknown"
    var projectionHoldActive: Bool = false
    var projectionHoldReason: String = "unknown"
    var projectionHoldHint: String?
    var targetingReliable: Bool = false
    var filterMode: String = "unknown"
    var fresh: Bool = false
    var observedAt: String = "-"
}

struct UserStatus {
    var status: String = "unknown"
    var confidence: Double = 0
    var eta: String = "unknown"
    var source: String = "unknown"
    var preview: String = ""
    var workspaceRole: String = "unknown"
    var workspaceReason: String = ""
}

struct WindowTarget {
    var owner: String = "unknown"
    var title: String = ""
    var pid: Int = 0
    var bounds: CGRect = .zero
    var agentSurface: String = "none"
    var hookStatus: String = "not_applicable"
    var resolution: String = "unknown"
}

final class StatusModel {
    private static let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.urlCache = nil
        return URLSession(configuration: config)
    }()

    var eye = EyeState()
    var status = UserStatus()
    var target = WindowTarget()
    var sessionSnapshot = AgentSessionSnapshot()
    var commandStatus = "Tools ready"
    private let visualFilter = VisualGazeFilter()
    private var visualPoint: CGPoint?
    private var lastReliableTarget = WindowTarget()

    func refresh(completion: @escaping () -> Void) {
        let group = DispatchGroup()
        group.enter()
        fetchJSON(path: "/dev/state") { payload in
            self.eye = Self.parseEye(payload: payload)
            group.leave()
        }
        group.enter()
        fetchJSON(path: "/status") { payload in
            self.status = Self.parseStatus(payload: payload)
            group.leave()
        }
        group.enter()
        refreshSessions {
            group.leave()
        }
        group.notify(queue: .main) {
            self.updateVisualPoint()
            self.updateTarget()
            completion()
        }
    }

    func refreshEye(completion: @escaping () -> Void) {
        fetchJSON(path: "/dev/state") { payload in
            self.eye = Self.parseEye(payload: payload)
            DispatchQueue.main.async {
                self.updateVisualPoint()
                self.updateTarget()
                completion()
            }
        }
    }

    func refreshStatus(completion: @escaping () -> Void) {
        let group = DispatchGroup()
        group.enter()
        fetchJSON(path: "/status") { payload in
            self.status = Self.parseStatus(payload: payload)
            group.leave()
        }
        group.enter()
        refreshSessions {
            group.leave()
        }
        group.notify(queue: .main) {
            completion()
        }
    }

    func eyePoint() -> CGPoint {
        if let visualPoint {
            return visualPoint
        }
        return rawEyePoint()
    }

    func rawEyePoint() -> CGPoint {
        if let x = eye.x, let y = eye.y {
            return CGPoint(x: x, y: y)
        }
        let screen = NSScreen.main?.frame ?? CGRect(x: 0, y: 0, width: 1440, height: 900)
        let normalized = Self.zonePoint(eye.screenZone)
        return CGPoint(x: screen.minX + normalized.x * screen.width, y: screen.minY + normalized.y * screen.height)
    }

    func observedEyePoint() -> CGPoint? {
        guard let x = eye.observedX, let y = eye.observedY else {
            return nil
        }
        return CGPoint(x: x, y: y)
    }

    private func updateVisualPoint() {
        let screen = NSScreen.main?.frame ?? CGRect(x: 0, y: 0, width: 1440, height: 900)
        visualPoint = visualFilter.update(raw: rawEyePoint(), eye: eye, screen: screen)
    }

    private func updateTarget() {
        let resolved = eye.targetingReliable ? WindowResolver.window(at: eyePoint()) : WindowTarget()
        if eye.targetingReliable, resolved.owner != "unknown" {
            target = annotateWorkspace(resolved)
            lastReliableTarget = resolved
            return
        }

        let frontmost = WindowResolver.frontmostTarget()
        if !eye.targetingReliable, lastReliableTarget.owner != "unknown" {
            var held = lastReliableTarget
            held.resolution = workspaceHoldResolution()
            if held.title.isEmpty, held.owner == frontmost.owner, !frontmost.title.isEmpty {
                held.title = frontmost.title
            }
            target = annotateWorkspace(held)
            return
        }
        target = annotateWorkspace(frontmost)
    }

    func fetchJSON(path: String, completion: @escaping ([String: Any]) -> Void) {
        let cleanedPath = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let url = URL(string: cleanedPath, relativeTo: baseURL)?.absoluteURL ??
            baseURL.appendingPathComponent(cleanedPath)
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        Self.session.dataTask(with: request) { data, _, _ in
            guard let data,
                  let object = try? JSONSerialization.jsonObject(with: data),
                  let payload = object as? [String: Any] else {
                completion([:])
                return
            }
            completion(payload)
        }.resume()
    }

    private static func parseEye(payload: [String: Any]) -> EyeState {
        guard let eye = payload["eye"] as? [String: Any] else { return EyeState() }
        let screen = NSScreen.main?.frame ?? CGRect(x: 0, y: 0, width: 1440, height: 900)
        let x = localScreenCoordinate(eye["screen_x"], origin: screen.minX)
        let y = localScreenCoordinate(eye["screen_y"], origin: screen.minY)
        let observedX = localScreenCoordinate(eye["observed_screen_x"], origin: screen.minX)
        let observedY = localScreenCoordinate(eye["observed_screen_y"], origin: screen.minY)
        return EyeState(
            score: eye["score"] as? Double ?? 0,
            confidence: eye["confidence"] as? Double ?? (eye["score"] as? Double ?? 0),
            state: eye["state"] as? String ?? "unknown",
            screenZone: eye["screen_zone"] as? String ?? "center",
            x: x,
            y: y,
            observedX: observedX,
            observedY: observedY,
            screenWidth: eye["screen_width"] as? Double,
            screenHeight: eye["screen_height"] as? Double,
            stabilityScore: eye["stability_score"] as? Double ?? 0,
            jumpPx: eye["jump_px"] as? Double ?? 0,
            jitterPx: eye["jitter_px"] as? Double ?? 0,
            velocityPxS: eye["velocity_px_s"] as? Double ?? 0,
            calibrationMeanErrorPx: eye["calibration_mean_error_px"] as? Double,
            calibrationP95ErrorPx: eye["calibration_p95_error_px"] as? Double,
            calibrationSampleCount: eye["calibration_sample_count"] as? Int,
            calibrationQualityLabel: eye["calibration_quality_label"] as? String ?? "unknown",
            calibrationRecommendedAction: eye["calibration_recommended_action"] as? String ?? "unknown",
            correctionOffsetXPx: eye["correction_offset_x_px"] as? Double,
            correctionOffsetYPx: eye["correction_offset_y_px"] as? Double,
            correctionSampleCount: eye["correction_sample_count"] as? Int,
            correctionReliabilityScore: eye["correction_reliability_score"] as? Double,
            correctionUpdatedAt: eye["correction_updated_at"] as? String,
            headYawDeg: eye["head_yaw_deg"] as? Double,
            headPitchDeg: eye["head_pitch_deg"] as? Double,
            headRollDeg: eye["head_roll_deg"] as? Double,
            framingQuality: eye["framing_quality"] as? Double,
            framingState: eye["framing_state"] as? String ?? "unknown",
            projectionHoldActive: eye["projection_hold_active"] as? Bool ?? false,
            projectionHoldReason: eye["projection_hold_reason"] as? String ?? "unknown",
            projectionHoldHint: eye["projection_hold_hint"] as? String,
            targetingReliable: eye["targeting_reliable"] as? Bool ?? false,
            filterMode: eye["filter_mode"] as? String ?? "unknown",
            fresh: eye["fresh"] as? Bool ?? false,
            observedAt: eye["observed_at"] as? String ?? "-"
        )
    }

    private static func localScreenCoordinate(_ value: Any?, origin: CGFloat) -> Double? {
        guard let coordinate = value as? Double else {
            return nil
        }
        return Double(origin) + coordinate
    }

    private static func parseStatus(payload: [String: Any]) -> UserStatus {
        let data = payload["data"] as? [String: Any] ?? payload
        let workspace = StatusModel.deriveWorkspaceRole(data: data)
        return UserStatus(
            status: data["status"] as? String ?? "unknown",
            confidence: data["confidence"] as? Double ?? 0,
            eta: data["estimated_response"] as? String ?? "unknown",
            source: data["source"] as? String ?? "unknown",
            preview: data["latest_inbound_preview"] as? String ?? "",
            workspaceRole: workspace.0,
            workspaceReason: workspace.1
        )
    }

    private static func zonePoint(_ zone: String) -> CGPoint {
        let cleaned = zone.replacingOccurrences(of: "looking_at_screen:", with: "")
        switch cleaned {
        case "top_left": return CGPoint(x: 0.18, y: 0.18)
        case "top": return CGPoint(x: 0.5, y: 0.16)
        case "top_right": return CGPoint(x: 0.82, y: 0.18)
        case "left": return CGPoint(x: 0.18, y: 0.5)
        case "right": return CGPoint(x: 0.82, y: 0.5)
        case "bottom_left": return CGPoint(x: 0.18, y: 0.82)
        case "bottom": return CGPoint(x: 0.5, y: 0.84)
        case "bottom_right": return CGPoint(x: 0.82, y: 0.82)
        default: return CGPoint(x: 0.5, y: 0.5)
        }
    }
}

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

final class AppDelegate: NSObject, NSApplicationDelegate {
    let model = StatusModel()
    private let uiStateStore = MonitorUIStateStore()
    var panelWindow: NSPanel!
    var overlayWindow: NSPanel!
    var panelView: PanelView!
    var overlayView: DotOverlayView!
    var statusItem: NSStatusItem!
    var popupMenuItem: NSMenuItem!
    private var popupVisible = true
    var eyeTimer: Timer?
    var statusTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        popupVisible = uiStateStore.loadPopupVisible(default: true)
        setupOverlay()
        setupPanel()
        setupTray()
        refresh()
        eyeTimer = Timer.scheduledTimer(withTimeInterval: 0.08, repeats: true) { _ in self.refreshEyeOnly() }
        statusTimer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { _ in self.refreshStatusOnly() }
    }

    private func setupOverlay() {
        let screen = NSScreen.main?.frame ?? CGRect(x: 0, y: 0, width: 1440, height: 900)
        overlayWindow = NSPanel(contentRect: screen, styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        overlayWindow.backgroundColor = .clear
        overlayWindow.isOpaque = false
        overlayWindow.ignoresMouseEvents = true
        overlayWindow.hidesOnDeactivate = false
        overlayWindow.level = .statusBar
        overlayWindow.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        overlayView = DotOverlayView(model: model)
        overlayWindow.contentView = overlayView
        overlayWindow.orderFrontRegardless()
    }

    private func setupPanel() {
        let screen = NSScreen.main?.visibleFrame ?? CGRect(x: 0, y: 0, width: 1440, height: 900)
        let frame = CGRect(x: screen.maxX - 430, y: screen.maxY - 540, width: 410, height: 520)
        panelWindow = NSPanel(contentRect: frame, styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        panelWindow.backgroundColor = .clear
        panelWindow.isOpaque = false
        panelWindow.hidesOnDeactivate = false
        panelWindow.hasShadow = true
        panelWindow.isMovableByWindowBackground = true
        panelWindow.level = .statusBar
        panelWindow.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        panelView = PanelView(model: model)
        panelView.onCalibrationAction = { [weak self] in
            self?.performCalibrationPanelAction()
        }
        panelWindow.contentView = panelView
        if popupVisible {
            panelWindow.orderFrontRegardless()
        } else {
            panelWindow.orderOut(nil)
        }
    }

    private func setupTray() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let image = NSImage(systemSymbolName: "eye", accessibilityDescription: "Agent User Status") {
            image.isTemplate = true
            statusItem.button?.image = image
        } else {
            statusItem.button?.title = "US"
        }
        statusItem.button?.toolTip = "Agent User Status"
        statusItem.isVisible = true
        let menu = NSMenu()
        popupMenuItem = NSMenuItem(title: "Toggle Popup View", action: #selector(togglePopupView), keyEquivalent: "")
        menu.addItem(popupMenuItem)
        menu.addItem(NSMenuItem(title: "Show Monitor", action: #selector(showMonitor), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Open Web Monitor", action: #selector(openWebMonitor), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Restart Tray UI", action: #selector(restartTrayUI), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Stop Tray UI", action: #selector(stopTrayUI), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Restart Status Backend", action: #selector(restartStatusBackend), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Stop Status Backend", action: #selector(stopStatusBackend), keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Start Eye Tracker", action: #selector(startEyeTracker), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Restart Eye Tracker", action: #selector(restartEyeTracker), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Stop Eye Tracker", action: #selector(stopEyeTracker), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Kill Eye Tracker", action: #selector(killEyeTracker), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Recalibrate Eye Tracker", action: #selector(recalibrateEyeTracker), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Evaluate Calibration", action: #selector(evaluateCalibration), keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Stop All Services", action: #selector(stopAllServices), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Quit", action: #selector(quit), keyEquivalent: "q"))
        for item in menu.items { item.target = self }
        statusItem.menu = menu
        updatePopupMenuState()
    }

    private func refresh() {
        model.refresh {
            self.statusItem.button?.toolTip = self.model.calibrationTooltipText()
            self.refreshVisibleSurfaces()
        }
    }

    private func refreshEyeOnly() {
        model.refreshEye {
            self.refreshVisibleSurfaces()
        }
    }

    private func refreshStatusOnly() {
        model.refreshStatus {
            self.statusItem.button?.toolTip = self.model.calibrationTooltipText()
            self.refreshVisibleSurfaces()
        }
    }

    @objc func showMonitor() {
        overlayWindow.orderFrontRegardless()
        setPopupVisible(true, shouldRefresh: true)
    }

    @objc func togglePopupView() {
        setPopupVisible(!popupVisible, shouldRefresh: true)
    }

    @objc private func performCalibrationPanelAction() {
        if model.eye.calibrationPrimaryActionTitle == "Recalibrate" {
            recalibrateEyeTracker()
        } else {
            evaluateCalibration()
        }
    }

    @objc private func openWebMonitor() {
        NSWorkspace.shared.open(baseURL.appendingPathComponent("monitor"))
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }

    private func setPopupVisible(_ visible: Bool, shouldRefresh: Bool) {
        popupVisible = visible
        uiStateStore.savePopupVisible(visible)
        updatePopupMenuState()

        if visible {
            NSApp.activate(ignoringOtherApps: true)
            panelWindow.orderFrontRegardless()
            panelWindow.makeKeyAndOrderFront(nil)
            if shouldRefresh {
                self.refresh()
            } else {
                panelView.needsDisplay = true
            }
        } else {
            panelWindow.orderOut(nil)
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        uiStateStore.savePopupVisible(popupVisible)
    }

    private func refreshVisibleSurfaces() {
        if popupVisible { panelView.needsDisplay = true }
        overlayView.needsDisplay = true
    }

    private func updatePopupMenuState() {
        popupMenuItem.title = popupVisible ? "Hide Popup View" : "Show Popup View"
        popupMenuItem.state = popupVisible ? .on : .off
    }
}
