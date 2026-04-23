import Foundation

struct MonitorUIState: Codable {
    var popupVisible: Bool
}

final class MonitorUIStateStore {
    private let fileManager: FileManager
    private let stateURL: URL

    init(fileManager: FileManager = .default) {
        self.fileManager = fileManager
        let defaultPath = NSString(string: "~/.local/share/agent-imessage/state").expandingTildeInPath
        let statePath = ProcessInfo.processInfo.environment["AGENT_IMESSAGE_STATE_DIR"] ?? defaultPath
        self.stateURL = URL(fileURLWithPath: statePath, isDirectory: true)
            .appendingPathComponent("monitor_ui_state.json")
    }

    func loadPopupVisible(default defaultValue: Bool) -> Bool {
        guard let data = try? Data(contentsOf: stateURL),
              let state = try? JSONDecoder().decode(MonitorUIState.self, from: data) else {
            return defaultValue
        }
        return state.popupVisible
    }

    func savePopupVisible(_ visible: Bool) {
        let directory = stateURL.deletingLastPathComponent()
        do {
            try fileManager.createDirectory(at: directory, withIntermediateDirectories: true)
            let data = try JSONEncoder().encode(MonitorUIState(popupVisible: visible))
            try data.write(to: stateURL, options: .atomic)
        } catch {
            // Best-effort persistence only.
        }
    }
}
