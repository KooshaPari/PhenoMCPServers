import AppKit
import Foundation

private let statusdLabel = "com.phenotype.agent-user-statusd"
private let trayLabel = "com.phenotype.agent-user-status-tray"
private let cursorLabel = "com.phenotype.agent-user-status-cursor-tracker"
private let eyeTrackerLabel = "com.phenotype.agent-user-status-webcam-eye-tracker"
private let eyePython = "\(NSHomeDirectory())/.local/share/agent-imessage/eye-tracker-venv/bin/python"
private let eyeTracker = "\(NSHomeDirectory())/.local/bin/agent-user-status-webcam-eye-tracker"
private let userLaunchAgentsDir = "\(NSHomeDirectory())/Library/LaunchAgents"

private enum ServiceAction: String {
    case start
    case stop
    case kill
    case restart
}

private struct ManagedService {
    let label: String
    let plistPath: String

    init(_ label: String) {
        self.label = label
        self.plistPath = "\(userLaunchAgentsDir)/\(label).plist"
    }

    func arguments(for action: ServiceAction) -> [String] {
        let guiScope = "gui/\(String(getuid()))"
        switch action {
        case .start:
            return ["bootstrap", guiScope, plistPath]
        case .stop:
            return ["bootout", guiScope, plistPath]
        case .kill:
            return ["kill", "TERM", "\(guiScope)/\(label)"]
        case .restart:
            return ["bootstrap", guiScope, plistPath]
        }
    }

    func restartArguments() -> [String] {
        let guiScope = "gui/\(String(getuid()))"
        return ["kickstart", "-k", "\(guiScope)/\(label)"]
    }
}

private let managedServices: [String: ManagedService] = [
    statusdLabel: ManagedService(statusdLabel),
    trayLabel: ManagedService(trayLabel),
    cursorLabel: ManagedService(cursorLabel),
    eyeTrackerLabel: ManagedService(eyeTrackerLabel),
]

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
    private var discardedSamples = 0
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
        discardedSamples = 0
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
                self.samples.append((self.points[self.index], model.rawEyePoint()))
            } else {
                self.discardedSamples += 1
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
                detail: "No fresh reliable gaze samples were available.\nDiscarded samples: \(discardedSamples)\nStart or recalibrate the eye tracker, then retry."
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
            detail: "Mean error: \(Int(mean)) px\nP95 error: \(Int(p95)) px\nSamples: \(errors.count) (\(quality))\nDiscarded stale/unreliable samples: \(discardedSamples)"
        )
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
        let attrs: [NSAttributedString.Key: Any] = [.font: NSFont.systemFont(ofSize: 22, weight: .medium), .foregroundColor: NSColor.white]
        caption.draw(at: CGPoint(x: 40, y: bounds.height - 70), withAttributes: attrs)
    }
}

private extension CGRect {
    var center: CGPoint { CGPoint(x: midX, y: midY) }
}

extension AppDelegate {
    @objc func startEyeTracker() {
        setCommandStatus("Starting eye tracker")
        executeServiceAction(.start, for: eyeTrackerLabel, statusMessage: "Starting eye tracker")
    }

    @objc func stopEyeTracker() {
        setCommandStatus("Stopping eye tracker")
        executeServiceAction(.stop, for: eyeTrackerLabel, statusMessage: "Stopping eye tracker")
    }

    @objc func killEyeTracker() {
        setCommandStatus("Killing eye tracker")
        executeServiceAction(.kill, for: eyeTrackerLabel, statusMessage: "Killing eye tracker")
    }

    @objc func restartEyeTracker() {
        setCommandStatus("Restarting eye tracker")
        executeServiceAction(.restart, for: eyeTrackerLabel, statusMessage: "Restarting eye tracker")
    }

    @objc func recalibrateEyeTracker() {
        setCommandStatus("Calibration running in background")
        guard let eyeTrackerService = managedServices[eyeTrackerLabel] else {
            setCommandStatus("Unknown service: \(eyeTrackerLabel)")
            return
        }
        _ = runLaunchctl(eyeTrackerService.arguments(for: .kill))
        _ = runShell("sleep 1")
        let calibration = [
            shellQuote(eyePython),
            shellQuote(eyeTracker),
            "calibrate",
            "--camera",
            shellQuote(eyeCameraIndex()),
            "--width",
            "1280",
            "--height",
            "720",
            "--seconds-per-point",
            "3",
            "--settle-seconds",
            "0.7",
        ].joined(separator: " ")
        if runShell(calibration) {
            setCommandStatus("Calibration complete; restarting eye tracker")
        } else {
            setCommandStatus("Calibration failed; restarting eye tracker")
        }
        _ = runLaunchctl(eyeTrackerService.arguments(for: .start))
        _ = runLaunchctl(eyeTrackerService.restartArguments())
    }

    @objc func evaluateCalibration() {
        setCommandStatus("Evaluating calibration")
        showMonitor()
        CalibrationEvalController.shared.start(model: model)
    }

    @objc func restartStatusBackend() {
        setCommandStatus("Restarting status backend")
        executeServiceAction(.restart, for: statusdLabel, statusMessage: "Restarting status backend")
    }

    @objc func stopStatusBackend() {
        setCommandStatus("Stopping status backend")
        executeServiceAction(.stop, for: statusdLabel, statusMessage: "Stopping status backend")
    }

    @objc func stopTrayUI() {
        setCommandStatus("Stopping tray UI")
        executeServiceAction(.stop, for: trayLabel, statusMessage: "Stopping tray UI")
    }

    @objc func restartTrayUI() {
        setCommandStatus("Restarting tray UI")
        executeServiceAction(.restart, for: trayLabel, statusMessage: "Restarting tray UI")
    }

    @objc func stopAllServices() {
        setCommandStatus("Stopping all services")
        let labels = [statusdLabel, cursorLabel, eyeTrackerLabel, trayLabel]
        let results = labels.map { label in
            managedServices[label].map { runLaunchctl($0.arguments(for: .stop)) } ?? false
        }
        if results.contains(false) {
            setCommandStatus("Stopping all services failed")
        }
    }

    func setCommandStatus(_ text: String) {
        DispatchQueue.main.async {
            self.model.commandStatus = text
            self.panelView.needsDisplay = true
        }
    }

    private func runShell(_ command: String) -> Bool {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/zsh")
        task.arguments = ["-lc", command]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        do {
            try task.run()
            task.waitUntilExit()
            return task.terminationStatus == 0
        } catch {
            setCommandStatus("Command failed to start")
            return false
        }
    }

    private func executeServiceAction(_ action: ServiceAction, for label: String, statusMessage: String) {
        guard let service = managedServices[label] else {
            setCommandStatus("Unknown service: \(label)")
            return
        }
        setCommandStatus(statusMessage)
        var ok = true
        switch action {
        case .start:
            _ = runLaunchctl(service.arguments(for: .stop))
            _ = runLaunchctl(service.arguments(for: .start))
            ok = runLaunchctl(service.restartArguments())
        case .stop:
            ok = runLaunchctl(service.arguments(for: .stop))
        case .kill:
            ok = runLaunchctl(service.arguments(for: .kill))
        case .restart:
            _ = runLaunchctl(service.arguments(for: .stop))
            _ = runLaunchctl(service.arguments(for: .start))
            ok = runLaunchctl(service.restartArguments())
        }
        if !ok {
            setCommandStatus("\(statusMessage) failed")
        }
    }

    private func runLaunchctl(_ arguments: [String]) -> Bool {
        runProcess("/bin/launchctl", arguments: arguments)
    }

    private func runProcess(_ executable: String, arguments: [String]) -> Bool {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: executable)
        task.arguments = arguments
        task.standardOutput = Pipe()
        task.standardError = Pipe()
        do {
            try task.run()
            task.waitUntilExit()
            return task.terminationStatus == 0
        } catch {
            return false
        }
    }

    private func shellQuote(_ value: String) -> String {
        "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }

    private func eyeCameraIndex() -> String {
        let value = ProcessInfo.processInfo.environment["AGENT_USER_STATUS_EYE_CAMERA"] ?? "0"
        if let parsed = Int(value), parsed >= 0 {
            return String(parsed)
        }
        return "0"
    }
}
