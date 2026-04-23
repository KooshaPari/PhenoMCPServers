import Foundation

extension StatusModel {
    func annotateWorkspace(_ target: WindowTarget) -> WindowTarget {
        let role = modelWorkspaceRole()
        guard role != "unknown" else {
            return target
        }
        var annotated = target
        let owner = annotated.owner.lowercased()
        let terminalLikeOwner = ["terminal", "ghostty", "iterm", "warp"].contains { owner.contains($0) }
        let genericSurface = annotated.agentSurface == "none" || annotated.agentSurface == "agent_workspace" ||
            annotated.agentSurface.contains("+")
        if terminalLikeOwner || genericSurface {
            annotated.agentSurface = role
        }
        if !eye.targetingReliable && annotated.resolution == "unstable_hold" {
            annotated.resolution = workspaceHoldResolution()
        }
        return annotated
    }

    func modelWorkspaceRole() -> String {
        let confidence = status.confidence
        guard confidence >= 0.35 else {
            return "unknown"
        }
        return status.workspaceRole
    }

    func workspaceHoldResolution() -> String {
        let role = modelWorkspaceRole()
        guard role != "unknown" else {
            return "unstable_hold"
        }
        return "unstable_hold:\(role)"
    }

    static func deriveWorkspaceRole(data: [String: Any]) -> (String, String) {
        guard let signals = data["signals"] as? [[String: Any]] else {
            return ("unknown", "no_signals")
        }

        var frontmostApp: String?
        var processGroups: [String: [String]] = [:]

        for signal in signals {
            let name = signal["name"] as? String ?? ""
            if name == "frontmost_app" {
                frontmostApp = signal["app"] as? String ?? frontmostApp
                continue
            }
            if name == "process_activity",
               let groups = signal["process_groups"] as? [String: Any] {
                var parsed: [String: [String]] = [:]
                for (groupName, value) in groups {
                    if let items = value as? [String] {
                        parsed[groupName] = items
                    }
                }
                processGroups = parsed
            }
        }

        let app = (frontmostApp ?? data["frontmost_app"] as? String ?? "").lowercased()
        let terminalLike = ["terminal", "ghostty", "iterm", "warp"].contains { app.contains($0) }
        let agentCount = processGroups["agent"]?.count ?? 0
        let codingCount = processGroups["coding"]?.count ?? 0

        if terminalLike {
            if agentCount > 0 && codingCount > 0 {
                return ("multi_agent_terminal", "\(app):agent+coding")
            }
            if agentCount > 0 {
                return ("agent_terminal", "\(app):agent")
            }
            if codingCount > 0 {
                return ("coding_terminal", "\(app):coding")
            }
            return ("plain_terminal", "\(app):terminal")
        }

        if app.contains("claude") || app.contains("codex") || app.contains("chatgpt") || app.contains("openai") {
            return ("gui_agent", "\(app):gui")
        }

        return ("unknown", "no_workspace_hint")
    }
}
