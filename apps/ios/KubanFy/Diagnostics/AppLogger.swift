import Foundation
import OSLog

enum AppLogLevel: String {
    case debug = "DEBUG"
    case info = "INFO"
    case warning = "WARN"
    case error = "ERROR"
}

final class AppLogger {
    static let shared = AppLogger()

    private let logger = Logger(subsystem: "com.kubanfy.ios", category: "app")
    private let lock = NSLock()
    private let maxEntries = 500
    private var entries: [String] = []
    private let fileURL: URL

    private init() {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let directory = base.appendingPathComponent("KubanFyDiagnostics", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        fileURL = directory.appendingPathComponent("app.log")
        if let existing = try? String(contentsOf: fileURL, encoding: .utf8) {
            entries = Array(existing.split(separator: "\n", omittingEmptySubsequences: false).suffix(maxEntries)).map(String.init)
        }
    }

    func log(
        _ level: AppLogLevel,
        event: String,
        message: String,
        context: [String: String] = [:]
    ) {
        let timestamp = ISO8601DateFormatter().string(from: Date())
        let safeMessage = Self.redact(message)
        let safeContext = context
            .sorted { $0.key < $1.key }
            .map { "\($0.key)=\(Self.redact($0.value))" }
            .joined(separator: " ")
        let line = safeContext.isEmpty
            ? "\(timestamp) [\(level.rawValue)] \(event) — \(safeMessage)"
            : "\(timestamp) [\(level.rawValue)] \(event) — \(safeMessage) | \(safeContext)"

        lock.lock()
        entries.append(line)
        if entries.count > maxEntries {
            entries.removeFirst(entries.count - maxEntries)
        }
        if let existing = try? String(contentsOf: fileURL, encoding: .utf8) {
            let lines = Array(existing.split(separator: "\n", omittingEmptySubsequences: false).suffix(maxEntries - 1))
            let content = (lines + [Substring(line)]).joined(separator: "\n") + "\n"
            try? content.write(to: fileURL, atomically: true, encoding: .utf8)
        } else {
            try? (line + "\n").write(to: fileURL, atomically: true, encoding: .utf8)
        }
        lock.unlock()

        switch level {
        case .debug:
            logger.debug("\(line, privacy: .public)")
        case .info:
            logger.info("\(line, privacy: .public)")
        case .warning:
            logger.warning("\(line, privacy: .public)")
        case .error:
            logger.error("\(line, privacy: .public)")
        }
    }

    func exportText() -> String {
        lock.lock()
        defer { lock.unlock() }
        if let persisted = try? String(contentsOf: fileURL, encoding: .utf8), !persisted.isEmpty {
            return persisted
        }
        return entries.joined(separator: "\n")
    }

    func clear() {
        lock.lock()
        entries.removeAll()
        try? FileManager.default.removeItem(at: fileURL)
        lock.unlock()
    }

    private static func redact(_ value: String) -> String {
        var result = value
        let sensitiveKeys = [
            "access_token", "refresh_token", "authorization",
            "kby_key", "offline_license", "password"
        ]

        for key in sensitiveKeys {
            let pattern = "(?i)\\b\(NSRegularExpression.escapedPattern(for: key))\\b(?:[=:]\\s*|%3D)([^&\\s,]+)"
            if let regex = try? NSRegularExpression(pattern: pattern) {
                let range = NSRange(result.startIndex..., in: result)
                result = regex.stringByReplacingMatches(
                    in: result,
                    options: [],
                    range: range,
                    withTemplate: "\(key)=[REDACTED]"
                )
            }
        }

        if let urlRegex = try? NSRegularExpression(
            pattern: "(?i)(https?://[^\\s]+)(?:[?&](?:token|signature|sig|key|auth)=[^&\\s]+)"
        ) {
            let range = NSRange(result.startIndex..., in: result)
            result = urlRegex.stringByReplacingMatches(
                in: result,
                options: [],
                range: range,
                withTemplate: "$1[REDACTED_QUERY]"
            )
        }
        return result
    }
}
