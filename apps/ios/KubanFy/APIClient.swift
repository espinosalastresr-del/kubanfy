import Foundation
import Security

struct UserResponse: Codable {
    let id: UUID
    let email: String
    let displayName: String
    let avatar: String?
    let country: String
    let language: String
    let status: String
    let emailVerified: Bool
    let createdAt: Date
    let lastLoginAt: Date?
    enum CodingKeys: String, CodingKey { case id, email, avatar, country, language, status; case displayName = "display_name"; case emailVerified = "email_verified"; case createdAt = "created_at"; case lastLoginAt = "last_login_at" }
}
struct TokenResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int
    enum CodingKeys: String, CodingKey { case accessToken = "access_token"; case refreshToken = "refresh_token"; case expiresIn = "expires_in" }
}
struct AuthContext: Codable {
    let roles: [String]; let artistIds: [UUID]; let isArtist: Bool; let isAdmin: Bool
    enum CodingKeys: String, CodingKey { case roles; case artistIds = "artist_ids"; case isArtist = "is_artist"; case isAdmin = "is_admin" }
}
struct DiscoveryHome: Codable {
    struct Artist: Codable { let id: UUID; let name: String; let slug: String; let verified: Bool }
    struct Track: Codable, Identifiable, Hashable { let id: UUID; let title: String; let duration: Double? }
    struct Ranking: Codable { let rank: Int; let trackId: UUID; let title: String?; let score: Double; let metrics: [String: Int]
        enum CodingKeys: String, CodingKey { case rank, title, score, metrics; case trackId = "track_id" } }
    let country: String; let localArtists: [Artist]; let topCountry: [Ranking]; let topGlobal: [Ranking]; let newReleases: [Track]; let trending: [Ranking]; let viralByCountry: [Ranking]
    enum CodingKeys: String, CodingKey { case country, trending; case localArtists = "local_artists"; case topCountry = "top_50_country"; case topGlobal = "top_50_global"; case newReleases = "new_releases"; case viralByCountry = "viral_by_country" }
}
struct TrackDetail: Codable, Identifiable {
    struct Artist: Codable, Identifiable {
        let id: UUID
        let name: String
        let slug: String
        let verified: Bool
    }
    let id: UUID
    let title: String
    let duration: Double?
    let isrc: String?
    let explicit: Bool
    let language: String?
    let releaseDate: Date?
    let artworkURL: String?
    let artists: [Artist]

    enum CodingKeys: String, CodingKey {
        case id, title, duration, isrc, explicit, language, artists
        case releaseDate = "release_date"
        case artworkURL = "artwork_url"
    }
}

struct TrackSearchResult: Codable, Identifiable {
    let id = UUID(); let provider: String; let providerTrackId: String; let trackId: UUID?; let title: String; let artists: [String]; let album: String?; let duration: Double?; let artwork: String?; let isrc: String?
    enum CodingKeys: String, CodingKey { case provider, title, artists, album, duration, artwork, isrc, trackId; case providerTrackId = "provider_track_id" }
}
struct PlaybackResponse: Codable {
    let url: URL
    let expiresInSeconds: Int
    let quality: String
    let trackId: UUID
    let contentHash: String?
    let kbyKey: String
    enum CodingKeys: String, CodingKey {
        case url, quality
        case expiresInSeconds = "expires_in_seconds"
        case trackId = "track_id"
        case contentHash = "content_hash"
        case kbyKey = "kby_key"
    }
}
struct PlaybackStartResponse: Codable {
    let playbackToken: String; let playbackSessionId: UUID; let heartbeatIntervalSeconds: Int; let qualifyingListenSeconds: Int; let assetVersion: Int; let contentHash: String
    enum CodingKeys: String, CodingKey { case playbackToken = "playback_token"; case playbackSessionId = "playback_session_id"; case heartbeatIntervalSeconds = "heartbeat_interval_seconds"; case qualifyingListenSeconds = "qualifying_listen_seconds"; case assetVersion = "asset_version"; case contentHash = "content_hash" }
}
struct OfflineBootstrapResponse: Codable {
    let trackId: UUID
    let title: String
    let duration: Double?
    let url: URL
    let expiresInSeconds: Int
    let quality: String
    let contentHash: String
    let kbyKey: String
    let assetVersion: Int
    let offlineLicense: String
    let offlineLicenseExpiresAt: Date

    enum CodingKeys: String, CodingKey {
        case trackId = "track_id"
        case title, duration, url, quality
        case expiresInSeconds = "expires_in_seconds"
        case contentHash = "content_hash"
        case kbyKey = "kby_key"
        case assetVersion = "asset_version"
        case offlineLicense = "offline_license"
        case offlineLicenseExpiresAt = "offline_license_expires_at"
    }
}

private struct OfflineCacheEntry: Codable {
    let trackId: UUID
    let quality: String
    let contentHash: String
    let assetVersion: Int?
    let kbyKey: String
    let contentType: String
    let fileName: String
    let offlineLicense: String?
    let offlineLicenseExpiresAt: Date?
}

struct PlaybackHeartbeatResponse: Codable {
    let qualified: Bool; let listenedMs: Int; let suspiciousScore: Double
    enum CodingKeys: String, CodingKey { case qualified; case listenedMs = "listened_ms"; case suspiciousScore = "suspicious_score" }
}
struct LoginResponse: Codable { let user: UserResponse; let tokens: TokenResponse }
struct FavoriteResponse: Codable { let id: UUID; let targetType: String; let targetId: UUID; let createdAt: Date
    enum CodingKeys: String, CodingKey { case id; case targetType = "target_type"; case targetId = "target_id"; case createdAt = "created_at" }
}
struct PlaylistResponse: Codable, Identifiable { let id: UUID; let name: String; let description: String?; let visibility: String; let createdAt: Date; let updatedAt: Date
    enum CodingKeys: String, CodingKey { case id, name, description, visibility; case createdAt = "created_at"; case updatedAt = "updated_at" }
}
struct DownloadTicketResponse: Codable { let downloadTicket: String; let expiresInSeconds: Int
    enum CodingKeys: String, CodingKey { case downloadTicket = "download_ticket"; case expiresInSeconds = "expires_in_seconds" }
}

enum APIError: LocalizedError {
    case invalidURL, decoding, missingSession, network, offlineUnavailable, audioDelivery
    case http(Int, String)
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "URL de API inválida"
        case .decoding: return "Respuesta inválida del servidor"
        case .missingSession: return "No hay una sesión activa"
        case .network: return "No se pudo conectar con el servidor"
        case .offlineUnavailable: return "Esta canción no está disponible sin conexión"
        case .audioDelivery: return "No se pudo descargar el audio"
        case let .http(code, message): return "\(message) (HTTP \(code))"
        }
    }
}

private final class KeychainStore {
    private let service = "com.kubanfy.auth"
    func save(_ value: String, account: String) throws {
        let data = Data(value.utf8)
        let base: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account]
        SecItemDelete(base as CFDictionary)
        var query = base; query[kSecValueData as String] = data
        guard SecItemAdd(query as CFDictionary, nil) == errSecSuccess else { throw APIError.http(0, "No se pudo guardar la credencial") }
    }
    func loadData(_ account: String) -> Data? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account, kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess else { return nil }
        return item as? Data
    }
    func saveData(_ data: Data, account: String) throws {
        let base: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account]
        SecItemDelete(base as CFDictionary)
        var query = base
        query[kSecValueData as String] = data
        guard SecItemAdd(query as CFDictionary, nil) == errSecSuccess else { throw APIError.http(0, "No se pudo guardar el estado local") }
    }

    func load(_ account: String) -> String? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account, kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    func remove(_ account: String) { SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account] as CFDictionary) }
}

final class APIClient {
    static let shared = APIClient()
    private let baseURL: URL
    private let keychain = KeychainStore()
    private let decoder: JSONDecoder
    private let session: URLSession

    private static let fallbackBaseURL: String = {
#if DEBUG
        return "https://kubanfy-api-staging.onrender.com/v1"
#else
        return "https://api.kubanfy.com/v1"
#endif
    }()

    private static func resolveBaseURL() -> URL {
        let candidates = [
            ProcessInfo.processInfo.environment["KUBANFY_API_URL"],
            Bundle.main.object(forInfoDictionaryKey: "KubanFyAPIBaseURL") as? String,
        ]
        for value in candidates.compactMap({ $0 }) {
            let normalized = value.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            if normalized.isEmpty || normalized.contains("$(") { continue }
            if let url = URL(string: normalized), url.scheme == "https", url.host != nil {
                return url
            }
        }
        guard let fallback = URL(string: fallbackBaseURL) else {
            preconditionFailure("Invalid KubanFy API fallback URL")
        }
        return fallback
    }

    private init() {
        baseURL = Self.resolveBaseURL()
        decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        let configuration = URLSessionConfiguration.default
        configuration.waitsForConnectivity = false
        configuration.timeoutIntervalForRequest = 15
        configuration.timeoutIntervalForResource = 30
        configuration.httpMaximumConnectionsPerHost = 4
        session = URLSession(configuration: configuration)
    }

    var hasStoredSession: Bool { keychain.load("access") != nil && keychain.load("refresh") != nil }
    var savedEmail: String? { keychain.load("saved_email") }
    var savedPassword: String? { keychain.load("saved_password") }

    var deviceID: String {
        if let existing = keychain.load("device_id") { return existing }
        let value = UUID().uuidString.lowercased()
        try? keychain.save(value, account: "device_id")
        return value
    }

    func login(email: String, password: String, saveCredentials: Bool = false) async throws -> LoginResponse {
        let body: [String: Any] = ["email": email.trimmingCharacters(in: .whitespacesAndNewlines), "password": password, "device_id": deviceID, "device_name": "iPhone", "platform": "ios"]
        do {
            let data = try await performRequest(path: "/auth/login", method: "POST", body: JSONSerialization.data(withJSONObject: body))
            let response = try decoder.decode(LoginResponse.self, from: data)
            try keychain.save(response.tokens.accessToken, account: "access")
            try keychain.save(response.tokens.refreshToken, account: "refresh")
            if saveCredentials {
                try keychain.save(email.trimmingCharacters(in: .whitespacesAndNewlines), account: "saved_email")
                try keychain.save(password, account: "saved_password")
            } else {
                keychain.remove("saved_email")
                keychain.remove("saved_password")
            }
            return response
        } catch { throw mapNetworkError(error) }
    }

    func register(email: String, password: String, displayName: String) async throws -> UserResponse {
        let body: [String: Any] = [
            "email": email.trimmingCharacters(in: .whitespacesAndNewlines),
            "password": password,
            "display_name": displayName.trimmingCharacters(in: .whitespacesAndNewlines)
        ]
        do {
            let data = try await performRequest(path: "/auth/register", method: "POST", body: JSONSerialization.data(withJSONObject: body), allowRefresh: false)
            return try decoder.decode(UserResponse.self, from: data)
        } catch { throw mapNetworkError(error) }
    }

    func refresh() async throws {
        guard let refreshToken = keychain.load("refresh") else { throw APIError.missingSession }
        let body: [String: Any] = ["refresh_token": refreshToken, "device_id": deviceID]
        let data = try await performRequest(path: "/auth/refresh", method: "POST", body: JSONSerialization.data(withJSONObject: body), allowRefresh: false)
        let tokens = try decoder.decode(TokenResponse.self, from: data)
        try keychain.save(tokens.accessToken, account: "access")
        try keychain.save(tokens.refreshToken, account: "refresh")
    }

    func context() async throws -> AuthContext { let data = try await performRequest(path: "/auth/context"); return try decoder.decode(AuthContext.self, from: data) }
    func discoveryHome() async throws -> DiscoveryHome { let data = try await performRequest(path: "/discovery/home"); return try decoder.decode(DiscoveryHome.self, from: data) }

    func trackDetail(trackId: UUID) async throws -> TrackDetail {
        let data = try await performRequest(path: "/music/tracks/\(trackId.uuidString)")
        return try decoder.decode(TrackDetail.self, from: data)
    }

    func playback(trackId: UUID, quality: String = "low") async throws -> PlaybackResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("music/play/\(trackId.uuidString)"), resolvingAgainstBaseURL: false)
        let normalized = ["low", "medium", "lossless"].contains(quality.lowercased()) ? quality.lowercased() : "low"
        components?.queryItems = [URLQueryItem(name: "quality", value: normalized)]
        guard let url = components?.url else { throw APIError.invalidURL }
        return try decoder.decode(PlaybackResponse.self, from: try await performRequest(url: url))
    }

    func fetchAndDecryptKBY(_ playback: PlaybackResponse) async throws -> URL {
        let (data, contentType) = try await downloadAndValidateKBY(
            url: playback.url,
            base64Key: playback.kbyKey,
            expectedHash: playback.contentHash
        )
        return try materializeDecryptedAudio(data, contentType: contentType)
    }

    func cacheAuthorizedPlaybackKBY(_ playback: PlaybackResponse) async throws -> URL {
        if let cached = try cachedAuthorizedPlaybackURL(
            trackId: playback.trackId,
            quality: playback.quality,
            expectedHash: playback.contentHash,
            kbyKey: playback.kbyKey
        ) {
            return cached
        }

        let (container, contentType) = try await downloadAndValidateKBY(
            url: playback.url,
            base64Key: playback.kbyKey,
            expectedHash: playback.contentHash
        )

        let existing = loadOfflineCacheIndex().first {
            $0.trackId == playback.trackId && $0.quality == playback.quality
        }
        let preserveOfflineAuthorization: (String?, Date?) = {
            guard let existing,
                  existing.contentHash.caseInsensitiveCompare(playback.contentHash ?? "") == .orderedSame,
                  existing.kbyKey == playback.kbyKey,
                  existing.offlineLicense != nil,
                  let expiry = existing.offlineLicenseExpiresAt,
                  expiry > Date()
            else {
                return (nil, nil)
            }
            return (existing.offlineLicense, existing.offlineLicenseExpiresAt)
        }()

        try saveOfflineKBY(
            container,
            trackId: playback.trackId,
            quality: playback.quality,
            contentHash: playback.contentHash ?? "",
            assetVersion: existing?.assetVersion,
            kbyKey: playback.kbyKey,
            contentType: contentType,
            offlineLicense: preserveOfflineAuthorization.0,
            offlineLicenseExpiresAt: preserveOfflineAuthorization.1
        )
        return try materializeDecryptedAudio(
            try OfflineCrypto.decryptKBY(
                container,
                base64Key: playback.kbyKey,
                expectedHash: playback.contentHash
            ).data,
            contentType: contentType
        )
    }

    func cachedAuthorizedPlaybackURL(
        trackId: UUID,
        quality: String,
        expectedHash: String?,
        kbyKey: String
    ) throws -> URL? {
        guard let entry = loadOfflineCacheIndex().first(where: {
            $0.trackId == trackId && $0.quality == quality
        }) else {
            return nil
        }
        if let expectedHash, !expectedHash.isEmpty,
           entry.contentHash.caseInsensitiveCompare(expectedHash) != .orderedSame {
            return nil
        }
        guard entry.kbyKey == kbyKey else { return nil }
        let fileURL = try offlineCacheURL(for: entry)
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            removeOfflineCacheEntry(entry)
            return nil
        }
        do {
            let container = try Data(contentsOf: fileURL)
            let decoded = try OfflineCrypto.decryptKBY(
                container,
                base64Key: entry.kbyKey,
                expectedHash: expectedHash ?? entry.contentHash
            )
            return try materializeDecryptedAudio(decoded.data, contentType: decoded.contentType)
        } catch {
            removeOfflineCacheEntry(entry)
            return nil
        }
    }

    func cachedOfflinePlaybackURL(trackId: UUID, quality: String = "low") throws -> URL {
        let now = Date()
        guard let entry = loadOfflineCacheIndex().first(where: {
            $0.trackId == trackId && $0.quality == quality && $0.offlineLicense != nil
        }) else {
            throw APIError.offlineUnavailable
        }
        guard let expiresAt = entry.offlineLicenseExpiresAt, expiresAt > now else {
            removeOfflineCacheEntry(entry)
            throw APIError.offlineUnavailable
        }
        let fileURL = try offlineCacheURL(for: entry)
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            removeOfflineCacheEntry(entry)
            throw APIError.offlineUnavailable
        }
        do {
            let container = try Data(contentsOf: fileURL)
            let decoded = try OfflineCrypto.decryptKBY(
                container,
                base64Key: entry.kbyKey,
                expectedHash: entry.contentHash
            )
            return try materializeDecryptedAudio(decoded.data, contentType: decoded.contentType)
        } catch {
            removeOfflineCacheEntry(entry)
            throw APIError.offlineUnavailable
        }
    }

    func preloadOfflineBootstrapIfNeeded() async {
        let now = Date()
        let validBootstrap = loadOfflineCacheIndex().filter {
            $0.offlineLicense != nil && ($0.offlineLicenseExpiresAt ?? .distantPast) > now
        }
        guard validBootstrap.count < 3 else { return }

        do {
            let data = try await performRequest(
                path: "/music/offline/bootstrap?limit=3",
                method: "GET"
            )
            let items = try decoder.decode([OfflineBootstrapResponse].self, from: data)
            for item in items.prefix(3) {
                let existing = loadOfflineCacheIndex().first {
                    $0.trackId == item.trackId &&
                    $0.quality == item.quality &&
                    $0.contentHash.caseInsensitiveCompare(item.contentHash) == .orderedSame &&
                    ($0.offlineLicenseExpiresAt ?? .distantPast) > now
                }
                if existing != nil {
                    continue
                }
                let (container, contentType) = try await downloadAndValidateKBY(
                    url: item.url,
                    base64Key: item.kbyKey,
                    expectedHash: item.contentHash
                )
                try saveOfflineKBY(
                    container,
                    trackId: item.trackId,
                    quality: item.quality,
                    contentHash: item.contentHash,
                    assetVersion: item.assetVersion,
                    kbyKey: item.kbyKey,
                    contentType: contentType,
                    offlineLicense: item.offlineLicense,
                    offlineLicenseExpiresAt: item.offlineLicenseExpiresAt
                )
            }
        } catch {
            // Bootstrap is best-effort. Normal online playback remains available.
        }
    }

    private func downloadAndValidateKBY(
        url: URL,
        base64Key: String,
        expectedHash: String?
    ) async throws -> (Data, String) {
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse else {
            throw APIError.audioDelivery
        }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError.http(http.statusCode, "Audio delivery failed")
        }
        let decoded = try OfflineCrypto.decryptKBY(
            data,
            base64Key: base64Key,
            expectedHash: expectedHash
        )
        return (data, decoded.contentType)
    }

    private func materializeDecryptedAudio(_ data: Data, contentType: String) throws -> URL {
        let ext: String
        switch contentType.lowercased() {
        case "audio/mp4", "audio/m4a": ext = "m4a"
        case "audio/flac": ext = "flac"
        case "audio/ogg", "audio/opus": ext = "ogg"
        default: ext = "wav"
        }
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("kubanfy-\(UUID().uuidString).\(ext)")
        try data.write(to: url, options: .atomic)
        return url
    }

    private func offlineCacheDirectory() throws -> URL {
        let base = try FileManager.default.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        let directory = base.appendingPathComponent("OfflineAudio", isDirectory: true)
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true,
            attributes: nil
        )
        return directory
    }

    private func loadOfflineCacheIndex() -> [OfflineCacheEntry] {
        guard let data = keychain.loadData("offline_cache_index") else { return [] }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return (try? decoder.decode([OfflineCacheEntry].self, from: data)) ?? []
    }

    private func saveOfflineKBY(
        _ container: Data,
        trackId: UUID,
        quality: String,
        contentHash: String,
        assetVersion: Int?,
        kbyKey: String,
        contentType: String,
        offlineLicense: String?,
        offlineLicenseExpiresAt: Date?
    ) throws {
        let directory = try offlineCacheDirectory()
        let filename = "\(trackId.uuidString)-\(quality)-\(UUID().uuidString).kby"
        let fileURL = directory.appendingPathComponent(filename)
        try container.write(to: fileURL, options: .atomic)

        var entries = loadOfflineCacheIndex()
        if let old = entries.first(where: { $0.trackId == trackId && $0.quality == quality }) {
            try? FileManager.default.removeItem(at: try offlineCacheURL(for: old))
            entries.removeAll { $0.trackId == trackId && $0.quality == quality }
        }

        entries.append(
            OfflineCacheEntry(
                trackId: trackId,
                quality: quality,
                contentHash: contentHash,
                assetVersion: assetVersion,
                kbyKey: kbyKey,
                contentType: contentType,
                fileName: filename,
                offlineLicense: offlineLicense,
                offlineLicenseExpiresAt: offlineLicenseExpiresAt
            )
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let encoded = try encoder.encode(entries)
        do {
            try keychain.saveData(encoded, account: "offline_cache_index")
        } catch {
            try? FileManager.default.removeItem(at: fileURL)
            throw error
        }
    }

    private func offlineCacheURL(for entry: OfflineCacheEntry) throws -> URL {
        try offlineCacheDirectory().appendingPathComponent(entry.fileName)
    }

    private func removeOfflineCacheEntry(_ entry: OfflineCacheEntry) {
        if let url = try? offlineCacheURL(for: entry) {
            try? FileManager.default.removeItem(at: url)
        }
        var entries = loadOfflineCacheIndex()
        entries.removeAll {
            $0.trackId == entry.trackId && $0.quality == entry.quality && $0.fileName == entry.fileName
        }
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        if let data = try? encoder.encode(entries) {
            try? keychain.saveData(data, account: "offline_cache_index")
        }
    }

    func startPlayback(trackId: UUID, quality: String = "low", sessionId: String? = nil) async throws -> PlaybackStartResponse {
        var body: [String: Any] = ["track_id": trackId.uuidString, "quality": quality, "device_id": deviceID]
        if let sessionId { body["session_id"] = sessionId }
        let data = try await performRequest(path: "/analytics/playback/start", method: "POST", body: JSONSerialization.data(withJSONObject: body))
        return try decoder.decode(PlaybackStartResponse.self, from: data)
    }

    func heartbeat(token: String, positionMs: Int, paused: Bool, completed: Bool) async throws -> PlaybackHeartbeatResponse {
        let body: [String: Any] = ["token": token, "position_ms": max(0, positionMs), "paused": paused, "completed": completed]
        let data = try await performRequest(path: "/analytics/playback/heartbeat", method: "POST", body: JSONSerialization.data(withJSONObject: body))
        return try decoder.decode(PlaybackHeartbeatResponse.self, from: data)
    }

    func addFavorite(trackId: UUID) async throws -> FavoriteResponse {
        let body = try JSONSerialization.data(withJSONObject: ["target_type": "track", "target_id": trackId.uuidString])
        return try decoder.decode(FavoriteResponse.self, from: try await performRequest(path: "/library/favorites", method: "POST", body: body))
    }

    func removeFavorite(trackId: UUID) async throws {
        _ = try await performRequest(path: "/library/favorites/track/\(trackId.uuidString)", method: "DELETE")
    }

    func listFavorites() async throws -> [FavoriteResponse] {
        try decoder.decode([FavoriteResponse].self, from: try await performRequest(path: "/library/favorites"))
    }

    func listPlaylists() async throws -> [PlaylistResponse] {
        try decoder.decode([PlaylistResponse].self, from: try await performRequest(path: "/library/playlists"))
    }

    func createPlaylist(name: String) async throws -> PlaylistResponse {
        let body = try JSONSerialization.data(withJSONObject: ["name": name, "visibility": "private"])
        return try decoder.decode(PlaylistResponse.self, from: try await performRequest(path: "/library/playlists", method: "POST", body: body))
    }

    func addToPlaylist(playlistId: UUID, trackId: UUID) async throws {
        _ = try await performRequest(path: "/library/playlists/\(playlistId.uuidString)/tracks/\(trackId.uuidString)", method: "POST")
    }

    func issueDownloadTicket(trackId: UUID, quality: String = "low") async throws -> DownloadTicketResponse {
        let body = try JSONSerialization.data(withJSONObject: ["track_id": trackId.uuidString, "quality": quality, "device_id": deviceID])
        return try decoder.decode(DownloadTicketResponse.self, from: try await performRequest(path: "/analytics/downloads/ticket", method: "POST", body: body))
    }

    func completeDownload(ticket: String, sizeBytes: Int) async throws {
        let body = try JSONSerialization.data(withJSONObject: ["ticket": ticket, "size_bytes": sizeBytes, "device_id": deviceID])
        _ = try await performRequest(path: "/analytics/downloads/complete", method: "POST", body: body)
    }

    func search(query: String, limit: Int = 20) async throws -> [TrackSearchResult] {
        var components = URLComponents(url: baseURL.appendingPathComponent("music/search"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "q", value: query.trimmingCharacters(in: .whitespacesAndNewlines)), URLQueryItem(name: "limit", value: String(min(max(limit, 1), 50)))]
        guard let url = components?.url else { throw APIError.invalidURL }
        return try decoder.decode([TrackSearchResult].self, from: try await performRequest(url: url))
    }

    func me() async throws -> UserResponse {
        guard keychain.load("access") != nil else { throw APIError.missingSession }
        return try decoder.decode(UserResponse.self, from: try await performRequest(path: "/auth/me"))
    }

    func logout() {
        keychain.remove("access")
        keychain.remove("refresh")
        keychain.remove("cached_user")
    }

    func cachedUser() -> UserResponse? {
        guard let data = keychain.loadData("cached_user") else { return nil }
        return try? decoder.decode(UserResponse.self, from: data)
    }

    func cacheUser(_ user: UserResponse) {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        guard let data = try? encoder.encode(user) else { return }
        try? keychain.saveData(data, account: "cached_user")
    }

    func refreshIfNeeded() async throws {
        guard let access = keychain.load("access") else { throw APIError.missingSession }
        let parts = access.split(separator: ".")
        guard parts.count == 3 else {
            try await refresh()
            return
        }
        var encoded = String(parts[1])
        encoded += String(repeating: "=", count: (4 - encoded.count % 4) % 4)
        guard let data = Data(base64Encoded: encoded),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let exp = json["exp"] as? TimeInterval else {
            try await refresh()
            return
        }
        if Date().timeIntervalSince1970 >= exp - 30 {
            try await refresh()
        }
    }

    private func performRequest(path: String, method: String = "GET", body: Data? = nil, allowRefresh: Bool = true) async throws -> Data {
        let cleanPath = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        return try await performRequest(url: baseURL.appendingPathComponent(cleanPath), method: method, body: body, allowRefresh: allowRefresh)
    }

    private func performRequest(url: URL, method: String = "GET", body: Data? = nil, allowRefresh: Bool = true) async throws -> Data {
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(deviceID, forHTTPHeaderField: "X-Device-ID")
        if let token = keychain.load("access") { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }

        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else { throw APIError.invalidURL }
            guard (200..<300).contains(http.statusCode) else {
                if http.statusCode == 401, allowRefresh, keychain.load("access") != nil, keychain.load("refresh") != nil {
                    do {
                        try await refresh()
                        return try await performRequest(url: url, method: method, body: body, allowRefresh: false)
                    } catch { logout() }
                }
                let message = (try? JSONDecoder().decode(APIErrorEnvelope.self, from: data))?.error.message ?? "Error HTTP \(http.statusCode)"
                throw APIError.http(http.statusCode, message)
            }
            return data
        } catch { throw mapNetworkError(error) }
    }

    private func mapNetworkError(_ error: Error) -> Error {
        if error is APIError { return error }
        guard let urlError = error as? URLError else { return error }
        switch urlError.code {
        case .timedOut, .cannotFindHost, .cannotConnectToHost, .networkConnectionLost, .notConnectedToInternet, .dnsLookupFailed, .resourceUnavailable:
            return APIError.network
        default:
            return error
        }
    }
}

private struct APIErrorEnvelope: Decodable { let error: APIErrorBody }
private struct APIErrorBody: Decodable { let message: String }
