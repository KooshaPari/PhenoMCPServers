import Foundation

struct AgentSessionSnapshot {
    var sessions: [AgentSessionSummary] = []
    var recentEvents: [AgentSessionEvent] = []

    var activeCount: Int {
        sessions.filter { $0.fresh }.count
    }

    var staleHookCount: Int {
        recentEvents.filter { $0.isStaleHook }.count
    }

    var childAgentCount: Int {
        sessions.filter { $0.isChildAgent }.count + recentEvents.filter { $0.isChildAgent }.count
    }

    var attributionConfidenceText: String {
        let values = recentEvents.compactMap(\.attributionConfidence)
        guard let value = values.first else {
            return "n/a"
        }
        return String(format: "%.2f", value)
    }
}

extension StatusModel {
    func refreshSessions(completion: @escaping () -> Void) {
        fetchJSON(path: "/session/snapshot?session_limit=80&event_limit=80") { payload in
            if let snapshot = payload["snapshot"] as? [String: Any] {
                self.sessionSnapshot = StatusModel.parseSessionSnapshot(snapshot)
                completion()
                return
            }
            self.refreshSessionFallback(completion: completion)
        }
    }

    private func refreshSessionFallback(completion: @escaping () -> Void) {
        let group = DispatchGroup()
        var sessions: [AgentSessionSummary] = []
        var events: [AgentSessionEvent] = []

        group.enter()
        fetchJSON(path: "/sessions?limit=80") { payload in
            if let items = payload["sessions"] as? [[String: Any]] {
                sessions = items.compactMap(AgentSessionSummary.parse)
            }
            group.leave()
        }

        group.enter()
        fetchJSON(path: "/session/events?limit=80") { payload in
            if let items = payload["events"] as? [[String: Any]] {
                events = Array(items.compactMap(AgentSessionEvent.parse).reversed())
            }
            group.leave()
        }

        group.notify(queue: .global(qos: .utility)) {
            self.sessionSnapshot = AgentSessionSnapshot(sessions: sessions, recentEvents: events)
            completion()
        }
    }

    static func parseSessionSnapshot(_ snapshot: [String: Any]) -> AgentSessionSnapshot {
        let sessions = (snapshot["sessions"] as? [[String: Any]] ?? [])
            .compactMap(AgentSessionSummary.parse)
        let events = Array(
            (snapshot["events"] as? [[String: Any]] ?? [])
                .compactMap(AgentSessionEvent.parse)
                .reversed()
        )
        return AgentSessionSnapshot(sessions: sessions, recentEvents: events)
    }
}

struct AgentSessionSummary {
    let sessionID: String
    let agentID: String
    let status: String
    let state: String
    let fresh: Bool
    let observedAt: String
    let latestEventType: String
    let attributionConfidence: Double?
    let isChildAgent: Bool

    static func parse(_ item: [String: Any]) -> AgentSessionSummary? {
        guard let sessionID = item["session_id"] as? String, !sessionID.isEmpty else {
            return nil
        }
        let heartbeat = item["heartbeat"] as? [String: Any]
        let latest = item["latest"] as? [String: Any]
        let event = item["last_event"] as? [String: Any]
        let primary = heartbeat ?? latest ?? [:]
        let metadata = primary["metadata"] as? [String: Any] ?? [:]
        let eventMetadata = event?["metadata"] as? [String: Any] ?? [:]
        return AgentSessionSummary(
            sessionID: sessionID,
            agentID: string(primary["agent_id"], defaultValue: string(latest?["agent_id"], defaultValue: "agent")),
            status: string(primary["status"], defaultValue: "unknown"),
            state: string(primary["state"], defaultValue: string(event?["state"], defaultValue: "-")),
            fresh: item["fresh"] as? Bool ?? false,
            observedAt: string(primary["observed_at"], defaultValue: string(latest?["observed_at"], defaultValue: "-")),
            latestEventType: string(event?["event_type"], defaultValue: "-"),
            attributionConfidence: double(metadata["attribution_confidence"]) ??
                double(eventMetadata["attribution_confidence"]) ??
                double(eventMetadata["confidence"]),
            isChildAgent: bool(metadata["child_agent"]) ||
                bool(eventMetadata["child_agent"]) ||
                string(primary["agent_id"], defaultValue: "").lowercased().contains("child")
        )
    }
}

struct AgentSessionEvent {
    let sessionID: String
    let eventType: String
    let state: String
    let observedAt: String
    let hookStatus: String
    let attributionConfidence: Double?
    let isChildAgent: Bool

    var isStaleHook: Bool {
        eventType.contains("waiting") ||
            state.contains("waiting") ||
            hookStatus.contains("unreliable") ||
            hookStatus.contains("unverified") ||
            hookStatus.contains("stale")
    }

    static func parse(_ item: [String: Any]) -> AgentSessionEvent? {
        guard let sessionID = item["session_id"] as? String, !sessionID.isEmpty else {
            return nil
        }
        let metadata = item["metadata"] as? [String: Any] ?? [:]
        let attribution = metadata["attribution"] as? [String: Any] ?? [:]
        return AgentSessionEvent(
            sessionID: sessionID,
            eventType: string(item["event_type"], defaultValue: string(item["kind"], defaultValue: "-")),
            state: string(item["state"], defaultValue: "-"),
            observedAt: string(item["observed_at"], defaultValue: "-"),
            hookStatus: string(metadata["hook_status"], defaultValue: string(attribution["hook_status"], defaultValue: "-")),
            attributionConfidence: double(metadata["attribution_confidence"]) ??
                double(metadata["confidence"]) ??
                double(attribution["confidence"]),
            isChildAgent: string(item["event_type"], defaultValue: "").hasPrefix("child_") ||
                metadata["child_session_id"] != nil ||
                metadata["child_agent_id"] != nil
        )
    }
}

private func string(_ value: Any?, defaultValue: String) -> String {
    if let value = value as? String, !value.isEmpty {
        return value
    }
    return defaultValue
}

private func double(_ value: Any?) -> Double? {
    if let value = value as? Double {
        return value
    }
    if let value = value as? Int {
        return Double(value)
    }
    if let value = value as? String {
        return Double(value)
    }
    return nil
}

private func bool(_ value: Any?) -> Bool {
    if let value = value as? Bool {
        return value
    }
    if let value = value as? String {
        return ["1", "true", "yes", "child", "child_agent"].contains(value.lowercased())
    }
    return false
}
