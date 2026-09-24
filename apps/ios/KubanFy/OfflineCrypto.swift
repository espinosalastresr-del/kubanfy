import Foundation
import CryptoKit

enum OfflineCrypto {
    static func encrypt(_ data: Data, key: SymmetricKey) throws -> Data {
        let sealed = try AES.GCM.seal(data, using: key)
        guard let combined = sealed.combined else { throw CryptoError.invalidCiphertext }
        return combined
    }

    static func decrypt(_ data: Data, key: SymmetricKey) throws -> Data {
        try AES.GCM.open(AES.GCM.SealedBox(combined: data), using: key)
    }

    static func newKey() -> SymmetricKey { SymmetricKey(size: .bits256) }
    enum CryptoError: Error { case invalidCiphertext }
}
