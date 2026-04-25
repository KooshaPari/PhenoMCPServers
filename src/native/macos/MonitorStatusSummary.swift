import Foundation

extension EyeState {
    var isProjectionHoldActive: Bool {
        filterMode == "projection_hold" || projectionHoldReason == "offscreen_jump" || !targetingReliable
    }

    var calibrationActionText: String {
        if passiveCorrectionActive {
            return "Passive correction active"
        }
        if calibrationRecommendedAction == "recalibrate" {
            return "Recalibrate now"
        }
        if calibrationRecommendedAction == "recalibrate_when_convenient" {
            return "Recalibrate when convenient"
        }
        if isProjectionHoldActive {
            return "Keep waiting"
        }
        return "Tracking stable"
    }

    var passiveCorrectionActive: Bool {
        if calibrationRecommendedAction == "recalibrate" || calibrationQualityLabel == "poor" {
            return false
        }
        return (correctionReliabilityScore ?? 0) >= 0.7 && (correctionSampleCount ?? 0) >= 3
    }

    var calibrationPrimaryActionTitle: String {
        if calibrationRecommendedAction == "recalibrate" || calibrationQualityLabel == "poor" {
            return "Recalibrate"
        }
        return "Evaluate"
    }

    var calibrationSummaryText: String {
        let quality = calibrationQualityLabel.capitalized
        let mean = calibrationMeanErrorPx.map { "mean \((Int($0))) px" } ?? "mean n/a"
        let p95 = calibrationP95ErrorPx.map { "p95 \((Int($0))) px" } ?? "p95 n/a"
        let samples = calibrationSampleCount.map { "\($0) samples" } ?? "samples n/a"
        let drift: String
        if let x = correctionOffsetXPx, let y = correctionOffsetYPx {
            drift = "drift \(Int(x)),\(Int(y)) px"
        } else {
            drift = "drift n/a"
        }
        return "\(quality) · \(mean) · \(p95) · \(samples) · \(drift)"
    }

    var headPoseSummaryText: String {
        let yaw = headYawDeg.map { "yaw \(Int($0))" } ?? "yaw n/a"
        let pitch = headPitchDeg.map { "pitch \(Int($0))" } ?? "pitch n/a"
        let roll = headRollDeg.map { "roll \(Int($0))" } ?? "roll n/a"
        return "\(yaw) \(pitch) \(roll)"
    }

    var framingSummaryText: String {
        let quality = framingQuality.map { String(format: "%.2f", $0) } ?? "n/a"
        return "\(framingState.replacingOccurrences(of: "_", with: " ")) \(quality)"
    }

    var calibrationDetailText: String {
        let action = calibrationActionText
        if isProjectionHoldActive {
            let reason = projectionHoldReason.capitalized.replacingOccurrences(of: "_", with: " ")
            let hint = projectionHoldHint ?? "keep the point anchored until the projection returns in bounds"
            return "\(action): \(reason). \(hint)"
        }
        if !calibrationQualityLabel.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
            !calibrationRecommendedAction.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            let correctionText = correctionSampleCount.map { sampleCount in
                let score = correctionReliabilityScore.map { String(format: "%.2f", $0) } ?? "n/a"
                let updated = correctionUpdatedAt ?? "unknown"
                return " Correction \(sampleCount) samples, reliability \(score), updated \(updated)."
            } ?? ""
            let passiveText = passiveCorrectionActive ? " Passive correction is active." : ""
            return "\(action): \(calibrationSummaryText).\(correctionText)\(passiveText)"
        }
        return action
    }

    var calibrationBannerText: String {
        if calibrationRecommendedAction == "recalibrate" || calibrationQualityLabel == "poor" {
            return "Recalibrate"
        }
        if isProjectionHoldActive {
            return "Projection hold"
        }
        return "Tracking"
    }
}

extension StatusModel {
    func calibrationTooltipText() -> String {
        let eye = eye
        if eye.calibrationRecommendedAction == "recalibrate" || eye.calibrationQualityLabel == "poor" {
            return "Calibration poor. \(eye.calibrationSummaryText). \(eye.calibrationActionText)."
        }
        if eye.isProjectionHoldActive {
            return "Projection hold active. \(eye.calibrationSummaryText). \(eye.calibrationActionText)."
        }
        if eye.calibrationRecommendedAction == "recalibrate_when_convenient" {
            return "Calibration usable. \(eye.calibrationSummaryText). \(eye.calibrationActionText)."
        }
        return "Tracking stable. \(eye.calibrationSummaryText)."
    }
}
