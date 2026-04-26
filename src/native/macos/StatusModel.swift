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
