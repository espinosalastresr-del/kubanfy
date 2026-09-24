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

    static func decryptKBY(_ container: Data, base64Key: String, expectedHash: String?) throws -> (data: Data, contentType: String) {
        guard container.count >= 37 else { throw CryptoError.invalidCiphertext }
        guard container.prefix(4) == Data([0x4B, 0x42, 0x59, 0x31]) else { throw CryptoError.invalidCiphertext }
        guard container[4] == 1 else { throw CryptoError.unsupportedVersion }

        let headerLength = Int(UInt32(bigEndian: container.subdata(in: 5..<9).withUnsafeBytes { $0.load(as: UInt32.self) }))
        guard headerLength > 1, headerLength <= 16 * 1024 else { throw CryptoError.invalidCiphertext }
        let headerStart = 21
        let headerEnd = headerStart + headerLength
        guard container.count > headerEnd else { throw CryptoError.invalidCiphertext }

        struct Header: Decodable {
            let version: Int
            let content_hash: String
            let plaintext_size: Int
            let content_type: String
        }
        let header = try JSONDecoder().decode(Header.self, from: container.subdata(in: headerStart..<headerEnd))
        guard header.version == 1 else { throw CryptoError.unsupportedVersion }
        if let expectedHash, header.content_hash.lowercased() != expectedHash.lowercased() {
            throw CryptoError.integrityFailure
        }

        guard let keyData = Data(base64Encoded: base64Key), keyData.count == 32 else {
            throw CryptoError.invalidKey
        }
        let nonceData = container.subdata(in: 9..<21)
        let ciphertext = container.subdata(in: headerEnd..<container.count)
        let aad = container.subdata(in: 0..<headerEnd)
        let sealed = try AES.GCM.SealedBox(
            nonce: try AES.GCM.Nonce(data: nonceData),
            ciphertext: ciphertext.dropLast(16),
            tag: ciphertext.suffix(16)
        )
        let plaintext = try AES.GCM.open(sealed, using: SymmetricKey(data: keyData), authenticating: aad)

        guard plaintext.count == header.plaintext_size else { throw CryptoError.integrityFailure }
        let digest = SHA256.hash(data: plaintext)
        let digestHex = digest.map { String(format: "%02x", $0) }.joined()
        guard digestHex == header.content_hash.lowercased() else { throw CryptoError.integrityFailure }
        return (plaintext, header.content_type)
    }

    enum CryptoError: Error {
        case invalidCiphertext
        case invalidKey
        case unsupportedVersion
        case integrityFailure
    }
}
