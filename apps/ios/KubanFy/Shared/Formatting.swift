import SwiftUI

import Foundation

func formatDuration(_ seconds: Double) -> String {
    guard seconds.isFinite, seconds >= 0 else { return "--:--" }
    let totalSeconds = Int(seconds.rounded())
    return String(format: "%d:%02d", totalSeconds / 60, totalSeconds % 60)
}
