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

    enum CodingKeys: String, CodingKey {
        case id, email, avatar, country, language, status
        case displayName = "display_name"
        case emailVerified = "email_verified"
        case createdAt = "created_at"
        case lastLoginAt = "last_login_at"
    }
}

struct TokenResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresIn = "expires_in"
    }
}

struct AuthContext: Codable {
    let roles: [String]
    let artistIds: [UUID]
    let isArtist: Bool
    let isAdmin: Bool

    enum CodingKeys: String, CodingKey {
        case roles
        case artistIds = "artist_ids"
        case isArtist = "is_artist"
        case isAdmin = "is_admin"
    }
}

struct DiscoveryHome: Codable {
    struct Artist: Codable { let id: UUID; let name: String; let slug: String; let verified: Bool }
    struct Track: Codable { let id: UUID; let title: String; let duration: Double? }
    struct Ranking: Codable { let rank: Int; let trackId: UUID; let title: String?; let score: Double; let metrics: [String: Int]
        enum CodingKeys: String, CodingKey { case rank, title, score, metrics; case trackId = "track_id" }
    }
    let country: String
    let localArtists: [Artist]
    let topCountry: [Ranking]
    let topGlobal: [Ranking]
    let newReleases: [Track]
    let trending: [Ranking]
    let viralByCountry: [Ranking]
    enum CodingKeys: String, CodingKey {
        case country, trending
        case localArtists = "local_artists"
        case topCountry = "top_50_country"
        case topGlobal = "top_50_global"
        case newReleases = "new_releases"
        case viralByCountry = "viral_by_country"
    }
}

struct LoginResponse: Codable {
    let user: UserResponse
    let tokens: TokenResponse
}

enum APIError: LocalizedError {
    case invalidURL
    case http(Int, String)
    case decoding
    case missingSession

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "URL de API inválida"
        case let .http(code, message): return "\(message) (HTTP \(code))"
        case .decoding: return "Respuesta inválida del servidor"
        case .missingSession: return "No hay una sesión activa"
        }
    }
}

private final class KeychainStore {
    private let service = "com.kubanfy.auth"

    func save(_ value: String, account: String) throws {
        let data = Data(value.utf8)
        let base: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        SecItemDelete(base as CFDictionary)
        var query = base
        query[kSecValueData as String] = data
        guard SecItemAdd(query as CFDictionary, nil) == errSecSuccess else {
            throw APIError.http(0, "No se pudo guardar la credencial")
        }
    }

    func load(_ account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func remove(_ account: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        SecItemDelete(query as CFDictionary)
    }
}

final class APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private let keychain = KeychainStore()
    private let decoder: JSONDecoder

    private init() {
        let raw = ProcessInfo.processInfo.environment["KUBANFY_API_URL"] ?? "https://api.kubanfy.com/v1"
        baseURL = URL(string: raw.trimmingCharacters(in: CharacterSet(charactersIn: "/")))!
        decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
    }

    var deviceID: String {
        if let existing = keychain.load("device_id") { return existing }
        let value = UUID().uuidString.lowercased()
        try? keychain.save(value, account: "device_id")
        return value
    }

    func login(email: String, password: String) async throws -> LoginResponse {
        let body: [String: Any] = [
            "email": email.trimmingCharacters(in: .whitespacesAndNewlines),
            "password": password,
            "device_id": deviceID,
            "device_name": "iPhone",
            "platform": "ios"
        ]
        let data = try await request(path: "/auth/login", method: "POST", body: JSONSerialization.data(withJSONObject: body))
        let response = try decoder.decode(LoginResponse.self, from: data)
        try keychain.save(response.tokens.accessToken, account: "access")
        try keychain.save(response.tokens.refreshToken, account: "refresh")
        return response
    }

    func context() async throws -> AuthContext {
        let data = try await request(path: "/auth/context")
        return try decoder.decode(AuthContext.self, from: data)
    }

    func discoveryHome() async throws -> DiscoveryHome {
        let data = try await request(path: "/discovery/home")
        return try decoder.decode(DiscoveryHome.self, from: data)
    }

    func me() async throws -> UserResponse {
        guard keychain.load("access") != nil else { throw APIError.missingSession }
        let data = try await request(path: "/auth/me")
        return try decoder.decode(UserResponse.self, from: data)
    }

    func logout() {
        keychain.remove("access")
        keychain.remove("refresh")
    }

    func request(path: String, method: String = "GET", body: Data? = nil) async throws -> Data {
        let cleanPath = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let url = baseURL.appendingPathComponent(cleanPath)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(deviceID, forHTTPHeaderField: "X-Device-ID")
        if let token = keychain.load("access") {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidURL }
        guard (200..<300).contains(http.statusCode) else {
            let message = (try? JSONDecoder().decode(APIErrorEnvelope.self, from: data))?.error.message
                ?? "Error HTTP \(http.statusCode)"
            throw APIError.http(http.statusCode, message)
        }
        return data
    }
}

private struct APIErrorEnvelope: Decodable {
    let error: APIErrorBody
}

private struct APIErrorBody: Decodable {
    let message: String
}
