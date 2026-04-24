import Foundation
import CoreGraphics

private let repeatedGazeSampleReason = "repeated_gaze_sample"
private let stuckGazeSampleReason = "stuck_gaze_sample"

struct CalibrationEvalSampleHealth {
    private var lastObservedAt: String?
    private var lastPointKey: String?
    private var repeatCount = 0
    private let repeatedThreshold = 2
    private let stuckThreshold = 4
    private(set) var repeated = 0
    private(set) var stuck = 0

    mutating func inspect(point: CGPoint, observedAt: String) -> String? {
        let key = "\(Int(point.x.rounded())):\(Int(point.y.rounded()))"
        let samePoint = key == lastPointKey
        let sameObservation = !observedAt.isEmpty && observedAt == lastObservedAt
        if samePoint || sameObservation {
            repeatCount += 1
        } else {
            repeatCount = 1
        }
        lastPointKey = key
        lastObservedAt = observedAt

        if repeatCount >= stuckThreshold {
            stuck += 1
            return stuckGazeSampleReason
        }
        if repeatCount >= repeatedThreshold {
            repeated += 1
            return repeatedGazeSampleReason
        }
        return nil
    }

    mutating func reset() {
        lastObservedAt = nil
        lastPointKey = nil
        repeatCount = 0
    }
}

struct CalibrationEvalTargetStats {
    var accepted = 0
    var rejected = 0
    var rejectReasons: [String: Int] = [:]

    mutating func accept() {
        accepted += 1
    }

    mutating func reject(_ reason: String) {
        rejected += 1
        rejectReasons[reason, default: 0] += 1
    }
}

struct CalibrationEvalStats {
    private(set) var targets: [CalibrationEvalTargetStats]
    private var sampleHealth = CalibrationEvalSampleHealth()

    init(targetCount: Int) {
        targets = Array(repeating: CalibrationEvalTargetStats(), count: targetCount)
    }

    var accepted: Int {
        targets.reduce(0) { $0 + $1.accepted }
    }

    var rejected: Int {
        targets.reduce(0) { $0 + $1.rejected }
    }

    mutating func accept(index: Int) {
        guard targets.indices.contains(index) else { return }
        targets[index].accept()
    }

    mutating func inspectSample(index: Int, point: CGPoint, observedAt: String) -> String? {
        guard targets.indices.contains(index) else { return nil }
        return sampleHealth.inspect(point: point, observedAt: observedAt)
    }

    mutating func reject(index: Int, reason: String) {
        guard targets.indices.contains(index) else { return }
        targets[index].reject(reason)
    }

    func summary() -> String {
        let targetLines = targets.enumerated().map { offset, target in
            let reasons = target.rejectReasons
                .sorted { $0.key < $1.key }
                .map { "\($0.key)=\($0.value)" }
                .joined(separator: ", ")
            let reasonText = reasons.isEmpty ? "none" : reasons
            return "P\(offset + 1): accepted \(target.accepted), rejected \(target.rejected) (\(reasonText))"
        }
        let sampleHealthLine = "Sample health: repeated \(sampleHealth.repeated), stuck \(sampleHealth.stuck)"
        return ([sampleHealthLine] + targetLines).joined(separator: "\n")
    }
}
