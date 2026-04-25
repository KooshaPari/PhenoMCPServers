import Foundation

struct NativeRuntimePaths {
    let runtimeMetadataURL: URL?
    let eyePython: String
    let eyeTracker: String
    let launchAgentsDir: String

    static func load(environment: [String: String] = ProcessInfo.processInfo.environment) -> NativeRuntimePaths {
        let metadataURL = metadataURL(environment: environment)
        let metadata = metadataURL.flatMap { loadJSON(url: $0) } ?? [:]
        let home = NSHomeDirectory()
        return NativeRuntimePaths(
            runtimeMetadataURL: metadataURL,
            eyePython: value(
                metadata,
                "eye_python_bin",
                environment,
                "AGENT_USER_STATUS_EYE_PYTHON_BIN",
                defaultValue: "python3"
            ),
            eyeTracker: value(
                metadata,
                "webcam_eye_tracker_bin",
                environment,
                "AGENT_USER_STATUS_WEBCAM_EYE_TRACKER",
                defaultValue: "agent-user-status-webcam-eye-tracker"
            ),
            launchAgentsDir: value(
                metadata,
                "launchd_dir",
                environment,
                "AGENT_USER_STATUS_LAUNCHD_DIR",
                defaultValue: "\(home)/Library/LaunchAgents"
            )
        )
    }

    private static func metadataURL(environment: [String: String]) -> URL? {
        if let path = environment["AGENT_USER_STATUS_RUNTIME_PATHS"], !path.isEmpty {
            return URL(fileURLWithPath: NSString(string: path).expandingTildeInPath)
        }
        guard let stateDir = environment["AGENT_IMESSAGE_STATE_DIR"], !stateDir.isEmpty else {
            return nil
        }
        return URL(fileURLWithPath: NSString(string: stateDir).expandingTildeInPath, isDirectory: true)
            .appendingPathComponent("runtime_paths.json")
    }

    private static func loadJSON(url: URL) -> [String: Any] {
        guard let data = try? Data(contentsOf: url),
              let object = try? JSONSerialization.jsonObject(with: data),
              let payload = object as? [String: Any] else {
            return [:]
        }
        return payload
    }

    private static func value(
        _ metadata: [String: Any],
        _ metadataKey: String,
        _ environment: [String: String],
        _ envKey: String,
        defaultValue: String
    ) -> String {
        if let value = metadata[metadataKey] as? String, !value.isEmpty {
            return value
        }
        if let value = environment[envKey], !value.isEmpty {
            return NSString(string: value).expandingTildeInPath
        }
        return defaultValue
    }
}
