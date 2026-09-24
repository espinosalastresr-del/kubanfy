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
    struct Track: Codable { let id: UUID; let title: String; let duration: Double? }
    struct Ranking: Codable { let rank: Int; let trackId: UUID; let title: String?; let score: Double; let metrics: [String: Int]
        enum CodingKeys: String, CodingKey { case rank, title, score, metrics; case trackId = "track_id" } }
    let country: String; let localArtists: [Artist]; let topCountry: [Ranking]; let topGlobal: [Ranking]; let newReleases: [Track]; let trending: [Ranking]; let viralByCountry: [Ranking]
    enum CodingKeys: String, CodingKey { case country, trending; case localArtists = "local_artists"; case topCountry = "top_50_country"; case topGlobal = "top_50_global"; case newReleases = "new_releases"; case viralByCountry = "viral_by_country" }
}
struct TrackSearchResult: Codable, Identifiable {
    let id = UUID(); let provider: String; let providerTrackId: String; let title: String; let artists: [String]; let album: String?; let duration: Double?; let artwork: String?; let isrc: String?
    enum CodingKeys: String, CodingKey { case provider, title, artists, album, duration, artwork, isrc; case providerTrackId = "provider_track_id" }
}
struct PlaybackResponse: Codable {
    let url: URL; let expiresInSeconds: Int; let quality: String; let trackId: UUID; let contentHash: String?
    enum CodingKeys: String, CodingKey { case url, quality; case expiresInSeconds = "expires_in_seconds"; case trackId = "track_id"; case contentHash = "content_hash" }
}
struct PlaybackStartResponse: Codable {
    let playbackToken: String
    let playbackSessionId: UUID
    let heartbeatIntervalSeconds: Int
    let qualifyingListenSeconds: Int
    let assetVersion: Int
    let contentHash: String
    enum CodingKeys: String, CodingKey {
        case playbackToken = "playback_token"; case playbackSessionId = "playback_session_id"; case heartbeatIntervalSeconds = "heartbeat_interval_seconds"; case qualifyingListenSeconds = "qualifying_listen_seconds"; case assetVersion = "asset_version"; case contentHash = "content_hash"
    }
}
struct PlaybackHeartbeatResponse: Codable {
    let qualified: Bool
    let listenedMs: Int
    let suspiciousScore: Double
    enum CodingKeys: String, CodingKey { case qualified; case listenedMs = "listened_ms"; case suspiciousScore = "suspicious_score" }
}
struct LoginResponse: Codable { let user: UserResponse; let tokens: TokenResponse }

enum APIError: LocalizedError {
    case invalidURL; case http(Int, String); case decoding; case missingSession
    var errorDescription: String? {
        switch self { case .invalidURL: return "URL de API inválida"; case let .http(code, message): return "(message) (HTTP (code))"; case .decoding: return "Respuesta inválida del servidor"; case .missingSession: return "No hay una sesión activa" }
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
    func load(_ account: String) -> String? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String, kSecAttrAccount as String, kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    func remove(_ account: String) { SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrService as String, kSecAttrAccount as String] as CFDictionary) }
}

final class APIClient {
    static let shared = APIClient()
    private let baseURL: URL
    private let keychain = KeychainStore()
    private let decoder: JSONDecoder
    private let session: URLSession
    private init() {
        let raw = ProcessInfo.processInfo.environment["KUBANFY_API_URL"] ?? "https://api.kubanfy.com/v1"
        baseURL = URL(string: raw.trimmingCharacters(in: CharacterSet(charactersIn: "/")))!
        decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        let configuration = URLSessionConfiguration.default
        configuration.waitsForConnectivity = true
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 120
        configuration.httpMaximumConnectionsPerHost = 4
        session = URLSession(configuration: configuration)
    }
    var deviceID: String {
        if let existing = keychain.load("device_id") { return existing }
        let value = UUID().uuidString.lowercased(); try? keychain.save(value, account: "device_id"); return value
    }
    func login(email: String, password: String) async throws -> LoginResponse {
        let body: [String: Any] = ["email": email.trimmingCharacters(in: .whitespacesAndNewlines), "password": password, "device_id": deviceID, "device_name": "iPhone", "platform": "ios"]
        let data = try await performRequest(path: "/auth/login", method: "POST", body: JSONSerialization.data(withJSONObject: body))
        let response = try decoder.decode(LoginResponse.self, from: data)
        try keychain.save(response.tokens.accessToken, account: "access"); try keychain.save(response.tokens.refreshToken, account: "refresh"); return response
    }
    func refresh() async throws {
        guard let refreshToken = keychain.load("refresh") else { throw APIError.missingSession }
        let body: [String: Any] = ["refresh_token": refreshToken, "device_id": deviceID]
        let data = try await performRequest(path: "/auth/refresh", method: "POST", body: JSONSerialization.data(withJSONObject: body), allowRefresh: false)
        let tokens = try decoder.decode(TokenResponse.self, from: data)
        try keychain.save(tokens.accessToken, account: "access"); try keychain.save(tokens.refreshToken, account: "refresh")
    }
    func context() async throws -> AuthContext { let data = try await performRequest(path: "/auth/context"); return try decoder.decode(AuthContext.self, from: data) }
    func discoveryHome() async throws -> DiscoveryHome { let data = try await performRequest(path: "/discovery/home"); return try decoder.decode(DiscoveryHome.self, from: data) }
    func playback(trackId: UUID, quality: String = "low") async throws -> PlaybackResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("music/play/(trackId.uuidString)"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "quality", value: quality.lowercased() == "medium" || quality.lowercased() == "lossless" ? quality.lowercased() : "low")]
        guard let url = components?.url else { throw APIError.invalidURL }
        return try decoder.decode(PlaybackResponse.self, from: try await performRequest(url: url))
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
    func search(query: String, limit: Int = 20) async throws -> [TrackSearchResult] {
        var components = URLComponents(url: baseURL.appendingPathComponent("music/search"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "q", value: query.trimmingCharacters(in: .whitespacesAndNewlines)), URLQueryItem(name: "limit", value: String(min(max(limit, 1), 50)))]
        guard let url = components?.url else { throw APIError.invalidURL }
        return try decoder.decode([TrackSearchResult].self, from: try await performRequest(url: url))
    }
    func me() async throws -> UserResponse { guard keychain.load("access") != nil else { throw APIError.missingSession }; return try decoder.decode(UserResponse.self, from: try await performRequest(path: "/auth/me")) }
    func logout() { keychain.remove("access"); keychain.remove("refresh") }
    private func performRequest(path: String, method: String = "GET", body: Data? = nil, allowRefresh: Bool = true) async throws -> Data {
        let cleanPath = path.trimmingCharacters(in: CharacterSet(charactersIn: "/")); return try await performRequest(url: baseURL.appendingPathComponent(cleanPath), method: method, body: body, allowRefresh: allowRefresh)
    }
    private func performRequest(url: URL, method: String = "GET", body: Data? = nil, allowRefresh: Bool = true) async throws -> Data {
        var request = URLRequest(url: url); request.httpMethod = method; request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Accept"); request.setValue("application/json", forHTTPHeaderField: "Content-Type"); request.setValue(deviceID, forHTTPHeaderField: "X-Device-ID")
        if let token = keychain.load("access") { request.setValue("Bearer (token)", forHTTPHeaderField: "Authorization") }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidURL }
        guard (200..<300).contains(http.statusCode) else {
            if http.statusCode == 401, allowRefresh, keychain.load("access") != nil, keychain.load("refresh") != nil {
                do { try await refresh(); return try await performRequest(url: url, method: method, body: body, allowRefresh: false) } catch { logout() }
            }
            let message = (try? JSONDecoder().decode(APIErrorEnvelope.self, from: data))?.error.message ?? "Error HTTP (http.statusCode)"
            throw APIError.http(http.statusCode, message)
        }
        return data
    }
}
private struct APIErrorEnvelope: Decodable { let error: APIErrorBody }
private struct APIErrorBody: Decodable { let message: String }
