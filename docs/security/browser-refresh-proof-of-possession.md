# Browser proof-of-possession for KubanFy sessions

## Security objective

A device-bound refresh token must not be sufficient by itself to rotate a session. The browser must demonstrate possession of the Ed25519 private key registered to that device. The private key remains non-extractable in IndexedDB; only the raw public key is sent to the API.

## Protocol

### Password login and initial binding

1. The PWA creates or loads a non-extractable Ed25519 key pair in IndexedDB.
2. It requests `POST /v1/auth/devices/login-challenge` with the stable device ID and public key.
3. The API returns a 180-second, one-time, random challenge. Its signed message is domain-separated and includes the challenge ID, nonce, device ID and public key.
4. The browser signs the exact message and submits the proof with the password to `POST /v1/auth/login`.
5. The API consumes the challenge atomically in Redis, verifies Ed25519 after password authentication, then binds the public key to the device before issuing a device-bound session.

A password-authenticated login may replace a lost key. When a key changes, all previous sessions and offline licenses for that device are revoked before the new key is bound.

### Refresh-token rotation

1. The PWA sends its refresh token and device ID to `POST /v1/auth/refresh/challenge`.
2. The API validates the token, persisted session, active device and idle/absolute expiry without extending activity. It returns a 90-second challenge bound to the user, database session ID, refresh-token JTI, device row, device ID and current public key.
3. The browser signs the exact challenge with its non-extractable private key.
4. The PWA submits the challenge ID and signature with the refresh token to `POST /v1/auth/refresh`.
5. The API locks and validates the session, atomically consumes the challenge, checks every binding, verifies Ed25519, and only then revokes the old session and issues the rotated token pair.

## Security properties

- A copied refresh token cannot be rotated without the device private key.
- Challenges are random, short-lived, namespaced by protocol and single-use through Redis atomic GET+DEL.
- A challenge for one session, device, public key or refresh JTI cannot be reused for another.
- Device-bound sessions with no enrolled public key fail closed; the user must complete a fresh password login to bind a key.
- A password login with a new signed key rotates the device key and invalidates older sessions/licenses.
- Device-less sessions (legacy/non-device API clients) retain bearer refresh behavior; the PWA always supplies a device ID and must complete the proof protocol.

## Operational behavior and recovery

- If IndexedDB is unavailable or Ed25519 is unsupported, the PWA refuses to create a device-bound login rather than silently falling back to bearer-only refresh.
- If the browser key is lost, refresh fails closed. A fresh password login generates a replacement key; the server revokes prior sessions and licenses for that device before rebinding.
- Redis is required for challenge issuance/consumption. Failure to issue or consume a challenge blocks refresh; no fallback to bearer-only rotation is permitted.
- No schema migration or production database write is required for this change.

## Residual limits

Proof-of-possession prevents reuse of a stolen refresh token on another device; it does not protect against active XSS, malware controlling the browser context, theft of the user's password, or compromise of the API/Redis/database. HTTPS, CSP, dependency hygiene, session revocation and rate limiting remain required.
