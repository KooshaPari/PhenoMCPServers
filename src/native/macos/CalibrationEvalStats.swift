import Foundation

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
        return targetLines.joined(separator: "\n")
    }
}
