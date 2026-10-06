# KubanFy Web Backend Contract

This document is the backend gate for the web/PWA client. The PWA must consume
this contract instead of reaching into database/storage implementation details.

## 1. Protected media pipeline

The browser never receives plaintext MP4 from KubanFy storage.

```
R2 .kby2
  -> short-lived signed GET
  -> encrypted KBY2 bytes
  -> browser decrypts chunks in memory
  -> fragmented MP4/AAC bytes in memory
  -> MediaSource/SourceBuffer
  -> <audio>
```

KBY2 remains the protected transport/storage representation. Plaintext media
exists only transiently after authorized client-side decryption.

## 2. Web playback

Request:

`GET /v1/music/play/{track_id}?quality=low|medium&kby_version=2`

The authenticated response contains:

- `url`: short-lived presigned GET URL for the KBY2 object.
- `expires_in_seconds`: current default is 900 seconds.
- `quality`: LOW or MEDIUM.
- `track_id`.
- `content_hash`.
- `kby_key`: per-asset decryption key material required by the current KBY protocol.
- `kby_version=2`.
- `content_type=audio/mp4`.
- `streaming_format=fmp4`.

KBY2 web playback rejects LOSSLESS and non-AAC catalog assets.

## 3. Media encoding contract

LOW and MEDIUM derivatives are AAC in fragmented MP4.

FFmpeg generation uses:

`-movflags +frag_keyframe+empty_moov+default_base_moof`

The resulting media must contain valid top-level ISO-BMFF `ftyp`, `moov`,
`moof`, and `mdat` boxes.

The KBY2 container chunks encrypted bytes; its 64 KiB chunk boundaries are not
media-segment boundaries. The web player therefore decrypts KBY2 chunks,
reassembles the plaintext byte stream, parses complete MP4 boxes, and appends
complete fMP4 initialization/media segments to MSE.

## 4. Range delivery

The signed R2 GET is the data plane. The web client uses HTTP Range requests
against the signed object so it can fetch only the KBY2 byte ranges required
for the current playback window.

The API authorization endpoint remains the control plane; it does not proxy
audio bytes through Render.

## 5. Entitlements

Product rules:

- FREE: LOW only (128 kbps), advertising, automatic cache maximum 3 songs,
  no persistent downloads.
- PREMIUM: MEDIUM (320 kbps), no ads, unlimited encrypted persistent downloads,
  automatic cache at played quality.
- FAMILY/STUDENT inherit Premium media/download/cache capabilities.

Quality is represented as LOW/MEDIUM/LOSSLESS. Plans determine access; the API
must not introduce plan-specific quality identifiers.

## 6. Playback anti-fraud

The client starts a playback session through:

`POST /v1/analytics/playback/start`

It returns a short-lived playback token plus the exact asset version and
content hash.

The client sends heartbeats approximately every 10 seconds through:

`POST /v1/analytics/playback/heartbeat`

The server:

- binds the session to track, quality, asset version and content hash;
- limits position jumps against server wall-clock time;
- qualifies after 30 seconds of plausible listening;
- rejects a session if the active asset version/hash changes;
- rechecks entitlement for authenticated sessions;
- records the client platform (`web`, `ios`, `android`).

Client events never directly become authoritative qualified plays.

## 7. R2 browser CORS requirement

The PWA uses JavaScript `fetch()` with signed R2 URLs, including Range
requests. The permanent R2 bucket therefore needs a CORS policy allowing the
deployed PWA origin and GET/HEAD as appropriate.

Do not make the permanent bucket public merely to solve CORS. Presigned URLs
remain the authorization mechanism.

Required deployment task once the final PWA origin exists:

- AllowedOrigin: exact PWA origin(s)
- AllowedMethods: GET, HEAD
- AllowedHeaders: headers actually sent by the player
- ExposeHeaders: Content-Length, Content-Range, ETag
- reasonable MaxAgeSeconds

## 8. Catalog readiness gate

Before enabling PWA playback against real catalog data, run:

`python -m scripts.audit_web_assets`

The audit is read-only and fails if any active LOW/MEDIUM asset:

- lacks KBY2;
- has a KBY2 quality/hash mismatch;
- fails KBY2 authentication/integrity;
- is not fragmented MP4;
- is not AAC.

Existing catalog assets created before the fragmented-MP4 pipeline must be
migrated or replaced before they are considered web-ready.

## 9. Operational rules

- Never expose permanent R2 URLs.
- Never return plaintext audio from the API.
- Never bypass entitlement checks for playback/download.
- Never treat a provider/cache object as the first-party catalog source.
- Keep asset version and content hash immutable for an active generation.
- When replacing audio, activate the new generation atomically and leave the
  old generation available long enough for already-issued offline licenses to
  expire/resolve safely.
- Investigate API playback failures in Render logs before changing the client.
