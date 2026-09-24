import Foundation
import Security

final class APIClient {
    static let shared = APIClient()
    private let baseURL = URL(string: ProcessInfo.processInfo.environment["KUBANFY_API_URL"] ?? "http://127.0.0.1:8000")!

    func request(path: String, method: String = "GET", body: Data? = nil) async throws -> Data {
        var request = URLRequest(url: baseURL.appendingPathComponent(path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))))
        request.httpMethod = method
        request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await URLSession.shared.data(for: request).0
    }

    func saveToken(_ token: String) throws {
        let data = Data(token.utf8)
        let query: [String: Any] = [kSecClass as String:kSecClassGenericPassword, kSecAttrService as String:"com.kubanfy.auth", kSecAttrAccount as String:"access", kSecValueData as String:data]
        SecItemDelete(query as CFDictionary)
        guard SecItemAdd(query as CFDictionary, nil) == errSecSuccess else { throw CocoaError(.fileWriteUnknown) }
    }

    func loadToken() -> String? {
        let query: [String: Any] = [kSecClass as String:kSecClassGenericPassword, kSecAttrService as String:"com.kubanfy.auth", kSecAttrAccount as String:"access", kSecReturnData as String:true, kSecMatchLimit as String:kSecMatchLimitOne]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
}
