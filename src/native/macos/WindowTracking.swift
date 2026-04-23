import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

final class HookInspector {
    private static let processProbeInterval: TimeInterval = 2.5
    private static let hookConfigInterval: TimeInterval = 4.0
    private static let inspectInterval: TimeInterval = 2.0

    private static var runningAgentProcessesCache: (agents: [String], expiresAt: Date)?
    private static var claudeHookConfiguredCache: (value: Bool, expiresAt: Date)?
    private static var codexGuidanceConfiguredCache: (value: Bool, expiresAt: Date)?
    private static var inspectCache: [String: (agent: String, hook: String, expires: Date)] = [:]

    static func inspect(owner: String, title: String, pid: Int) -> (String, String) {
        let now = Date()
        let key = "\(pid)|\(owner.lowercased())|\(title.lowercased())"
        if let cached = inspectCache[key], cached.expires > now {
            return (cached.agent, cached.hook)
        }

        let text = "\(owner) \(title) \(processSignature(pid: pid))".lowercased()
        if text.contains("messages") || text.contains("imessage") {
            return cached(key, ("messages", "gui_chat"), now)
        }
        if text.contains("claude") || text.contains("codex") || text.contains("chatgpt") || text.contains("openai") {
            if text.contains("terminal") || text.contains("ghostty") || text.contains("iterm") ||
                text.contains("warp") || text.contains("xcode") || text.contains("tmux") ||
                text.contains("screen") || text.contains("pane") || text.contains("shell") ||
                text.contains("cursor") {
                let agents = runningAgentProcessesCached()
                let hookOK = (agents.contains("claude_code") && claudeHookConfigured()) ||
                    (agents.contains("codex_cli") && codexGuidanceConfigured())
                return cached(key, ("agent_terminal_candidate", hookOK ? "candidate_configured" : "candidate_unverified"), now)
            }
            return cached(
                key,
                ("gui_agent_chat", claudeHookConfigured() || codexGuidanceConfigured() ? "gui_agent_configured" : "gui_agent_unverified"),
                now
            )
        }
        if text.contains("cursor") || text.contains("ghostty") || text.contains("terminal") ||
            text.contains("iterm") || text.contains("warp") || text.contains("xcode") ||
            text.contains("tmux") || text.contains("screen") || text.contains("pane") ||
            text.contains("shell") {
            let agents = runningAgentProcessesCached()
            if !agents.isEmpty {
                let hookOK = (agents.contains("claude_code") && claudeHookConfigured()) ||
                    (agents.contains("codex_cli") && codexGuidanceConfigured())
                let surface = agents.count > 1 ? "multi_agent_terminal_candidate" : "agent_terminal_candidate"
                let hook = hookOK ? "candidate_configured" : "candidate_unverified"
                return cached(key, (surface, hook), now)
            }
            if text.contains("cursor") || text.contains("xcode") {
                return cached(key, ("coding_terminal_candidate", "unreliable_terminal_identity"), now)
            }
            return cached(key, ("unresolved_terminal", "unreliable_terminal_identity"), now)
        }
        return cached(key, ("none", "not_applicable"), now)
    }

    private static func cached(_ key: String, _ result: (String, String), _ now: Date) -> (String, String) {
        inspectCache[key] = (result.0, result.1, now.addingTimeInterval(inspectInterval))
        return result
    }

    private static func runningAgentProcessesCached() -> [String] {
        let now = Date()
        if let cached = runningAgentProcessesCache, cached.expiresAt > now {
            return cached.agents
        }
        let agents = runningAgentProcesses() ?? runningAgentProcessesCache?.agents ?? []
        runningAgentProcessesCache = (agents: agents, expiresAt: now.addingTimeInterval(processProbeInterval))
        return agents
    }

    private static func runningAgentProcesses() -> [String]? {
        let output = runZsh("ps -axo comm,args | egrep '(^|/| )((claude)|(codex))([[:space:]]|$)' | head -20")
        var agents: [String] = []
        if output.contains("claude") { agents.append("claude_code") }
        if output.contains("codex") { agents.append("codex_cli") }
        return agents
    }

    private static func claudeHookConfigured() -> Bool {
        let now = Date()
        if let cache = claudeHookConfiguredCache, cache.1 > now {
            return cache.0
        }
        let path = NSString(string: "~/.claude/settings.json").expandingTildeInPath
        let text = (try? String(contentsOfFile: path, encoding: .utf8)) ?? ""
        let configured = text.contains("agent-user-status-stop-hook") && text.contains("\"Stop\"")
        claudeHookConfiguredCache = (configured, now.addingTimeInterval(hookConfigInterval))
        return configured
    }

    private static func codexGuidanceConfigured() -> Bool {
        let now = Date()
        if let cache = codexGuidanceConfiguredCache, cache.1 > now {
            return cache.0
        }
        let path = NSString(string: "~/.codex/AGENTS.md").expandingTildeInPath
        let text = (try? String(contentsOfFile: path, encoding: .utf8)) ?? ""
        let configured = text.contains("User Response Status and iMessage") && text.contains("hook-decision")
        codexGuidanceConfiguredCache = (configured, now.addingTimeInterval(hookConfigInterval))
        return configured
    }

    private static func runZsh(_ command: String) -> String {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/zsh")
        task.arguments = ["-lc", command]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = Pipe()
        do {
            try task.run()
            task.waitUntilExit()
            return String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?.lowercased() ?? ""
        } catch {
            return ""
        }
    }

    private static func processSignature(pid: Int) -> String {
        let output = runZsh("ps -p \(pid) -o comm=,args=")
        return output
    }
}

final class WindowResolver {
    static func window(at point: CGPoint) -> WindowTarget {
        guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
            as? [[String: Any]] else {
            return WindowTarget()
        }
        var nearest: (target: WindowTarget, distance: CGFloat)?
        for info in windows {
            guard let layer = info[kCGWindowLayer as String] as? Int, layer == 0,
                  let boundsDict = info[kCGWindowBounds as String] as? [String: Any],
                  let bounds = CGRect(dictionaryRepresentation: boundsDict as CFDictionary) else {
                continue
            }
            let owner = info[kCGWindowOwnerName as String] as? String ?? "unknown"
            let title = info[kCGWindowName as String] as? String ?? ""
            let pid = info[kCGWindowOwnerPID as String] as? Int ?? 0
            let hook = HookInspector.inspect(owner: owner, title: title, pid: pid)
            let target = WindowTarget(
                owner: owner,
                title: title,
                pid: pid,
                bounds: bounds,
                agentSurface: hook.0,
                hookStatus: hook.1,
                resolution: resolutionFor(hook: hook, prefix: "gaze_window")
            )
            if bounds.contains(point) || bounds.insetBy(dx: -18, dy: -18).contains(point) {
                return target
            }
            let clamped = CGPoint(
                x: min(max(point.x, bounds.minX), bounds.maxX),
                y: min(max(point.y, bounds.minY), bounds.maxY)
            )
            let distance = hypot(point.x - clamped.x, point.y - clamped.y)
            if distance <= 32, (nearest == nil || distance < nearest!.distance) {
                nearest = (target, distance)
            }
        }
        return nearest?.target ?? WindowTarget()
    }

    static func frontmostTarget() -> WindowTarget {
        guard let app = NSWorkspace.shared.frontmostApplication else {
            return WindowTarget(resolution: "frontmost_unknown")
        }
        let owner = app.localizedName ?? "unknown"
        let pid = Int(app.processIdentifier)
        let title = focusedWindowTitle(pid: app.processIdentifier) ?? ""
        let hook = HookInspector.inspect(owner: owner, title: title, pid: pid)
        let resolution = resolutionFor(hook: hook, prefix: "frontmost")
        return WindowTarget(
            owner: owner,
            title: title,
            pid: pid,
            bounds: .zero,
            agentSurface: hook.0,
            hookStatus: hook.1,
            resolution: resolution
        )
    }

    private static func resolutionFor(hook: (String, String), prefix: String) -> String {
        if hook.0 == "messages" {
            return "\(prefix)_gui_chat"
        }
        if hook.0 == "gui_agent_chat" {
            return "\(prefix)_gui_agent_chat"
        }
        if hook.1.contains("candidate") || hook.1.contains("unreliable") {
            return "\(prefix)_unresolved"
        }
        return "\(prefix)_fallback"
    }

    private static func focusedWindowTitle(pid: pid_t) -> String? {
        let app = AXUIElementCreateApplication(pid)
        if let title = copyTitle(windowElement(app, attribute: kAXFocusedWindowAttribute as CFString)) {
            return title
        }
        return copyTitle(windowElement(app, attribute: kAXMainWindowAttribute as CFString))
    }

    private static func windowElement(_ app: AXUIElement, attribute: CFString) -> AXUIElement? {
        var value: CFTypeRef?
        let result = AXUIElementCopyAttributeValue(app, attribute, &value)
        guard result == .success, let value, CFGetTypeID(value) == AXUIElementGetTypeID() else {
            return nil
        }
        return (value as! AXUIElement)
    }

    private static func copyTitle(_ window: AXUIElement?) -> String? {
        guard let window else {
            return nil
        }
        var value: CFTypeRef?
        let result = AXUIElementCopyAttributeValue(window, kAXTitleAttribute as CFString, &value)
        guard result == .success, let title = value as? String else {
            return nil
        }
        let cleaned = title.trimmingCharacters(in: .whitespacesAndNewlines)
        return cleaned.isEmpty ? nil : cleaned
    }
}
