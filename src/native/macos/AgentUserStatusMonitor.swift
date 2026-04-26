import AppKit
import Foundation

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
