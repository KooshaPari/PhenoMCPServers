import AppKit
import Foundation

private let statusdLabel = "com.phenotype.agent-user-statusd"
private let trayLabel = "com.phenotype.agent-user-status-tray"
private let cursorLabel = "com.phenotype.agent-user-status-cursor-tracker"
private let eyeTrackerLabel = "com.phenotype.agent-user-status-webcam-eye-tracker"
private let runtimePaths = NativeRuntimePaths.load()

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
        self.plistPath = "\(runtimePaths.launchAgentsDir)/\(label).plist"
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
        setCommandStatus("Calibration starting")
        guard let eyeTrackerService = managedServices[eyeTrackerLabel] else {
            setCommandStatus("Unknown service: \(eyeTrackerLabel)")
            return
        }
        _ = runLaunchctl(eyeTrackerService.arguments(for: .kill))
        let calibration = [
            shellQuote(runtimePaths.eyePython),
            shellQuote(runtimePaths.eyeTracker),
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
        DispatchQueue.global(qos: .userInitiated).async {
            Thread.sleep(forTimeInterval: 1)
            let ok = self.runShell(calibration)
            self.setCommandStatus(ok ? "Calibration complete; restarting eye tracker" : "Calibration failed; restarting eye tracker")
            _ = self.runLaunchctl(eyeTrackerService.arguments(for: .start))
            _ = self.runLaunchctl(eyeTrackerService.restartArguments())
            DispatchQueue.main.async {
                self.model.refresh {
                    self.panelView.needsDisplay = true
                    self.overlayView.needsDisplay = true
                }
            }
        }
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
