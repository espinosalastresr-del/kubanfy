package com.kubanfy.android

import android.content.Context
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

data class AuthContext(
    val roles: List<String>,
    val artistIds: List<String>,
    val isArtist: Boolean,
    val isAdmin: Boolean,
)

data class DiscoveryTrack(val id: String, val title: String, val duration: Double?)

data class DiscoveryRanking(val trackId: String, val title: String?, val rank: Int)

data class DiscoveryHome(
    val country: String,
    val localArtists: List<String>,
    val topCountry: List<DiscoveryRanking>,
    val topGlobal: List<DiscoveryRanking>,
    val newReleases: List<DiscoveryTrack>,
)

data class TrackSearchResult(
    val provider: String,
    val providerTrackId: String,
    val title: String,
    val artists: List<String>,
    val album: String?,
    val duration: Double?,
    val artwork: String?,
    val isrc: String?,
)

data class AuthSession(
    val accessToken: String,
    val refreshToken: String,
    val expiresIn: Long,
    val userId: String,
    val displayName: String,
)

data class PlaybackSession(
    val url: String,
    val expiresInSeconds: Long,
    val quality: String,
    val trackId: String,
    val contentHash: String?,
)

class APIException(val statusCode: Int, message: String) : Exception(message)

class APIClient(context: Context) {
    private val appContext = context.applicationContext
    private val store = SecureStore(appContext)
    private val device = DeviceIdentity(appContext)
    private val baseUrl = BuildConfig.KUBANFY_API_URL.trimEnd('/')

    fun login(email: String, password: String): AuthSession {
        val body = JSONObject()
            .put("email", email.trim())
            .put("password", password)
            .put("device_id", device.id)
            .put("device_name", android.os.Build.MODEL)
            .put("platform", "android")
        val json = request("/auth/login", "POST", body.toString(), allowRefresh = false)
        return saveSession(json)
    }

    fun refresh(): Boolean {
        val refreshToken = store.get("refresh_token") ?: return false
        return try {
            val body = JSONObject()
                .put("refresh_token", refreshToken)
                .put("device_id", device.id)
            val json = request("/auth/refresh", "POST", body.toString(), allowRefresh = false)
            store.put("access_token", json.getString("access_token"))
            store.put("refresh_token", json.getString("refresh_token"))
            true
        } catch (_: Exception) {
            clearSession()
            false
        }
    }

    fun context(): AuthContext {
        val token = requireAccessToken()
        val json = request("/auth/context", "GET", null, token)
        return AuthContext(
            roles = json.getJSONArray("roles").toStringList(),
            artistIds = json.getJSONArray("artist_ids").toStringList(),
            isArtist = json.getBoolean("is_artist"),
            isAdmin = json.getBoolean("is_admin"),
        )
    }

    fun discoveryHome(): DiscoveryHome {
        val json = request("/discovery/home", "GET", null, requireAccessToken())
        return DiscoveryHome(
            country = json.getString("country"),
            localArtists = json.getJSONArray("local_artists").getJSONObjectStrings("name"),
            topCountry = json.getJSONArray("top_50_country").getDiscoveryRankings(),
            topGlobal = json.getJSONArray("top_50_global").getDiscoveryRankings(),
            newReleases = json.getJSONArray("new_releases").getDiscoveryTracks(),
        )
    }

    fun playback(trackId: String, quality: String = "low"): PlaybackSession {
        val token = requireAccessToken()
        val safeQuality = quality.lowercase().let { if (it in setOf("low", "medium", "lossless")) it else "low" }
        val json = request("/music/play/$trackId?quality=$safeQuality", "GET", null, token)
        return PlaybackSession(
            url = json.getString("url"),
            expiresInSeconds = json.getLong("expires_in_seconds"),
            quality = json.getString("quality"),
            trackId = json.getString("track_id"),
            contentHash = json.optString("content_hash").takeIf { it.isNotBlank() },
        )
    }

    fun search(query: String, limit: Int = 20): List<TrackSearchResult> {
        val encoded = URLEncoder.encode(query.trim(), Charsets.UTF_8.name())
        val cappedLimit = limit.coerceIn(1, 50)
        val jsonArray = org.json.JSONArray(
            requestRaw("/music/search?q=$encoded&limit=$cappedLimit", "GET", null, null),
        )
        return (0 until jsonArray.length()).mapNotNull { index ->
            jsonArray.optJSONObject(index)?.let { item ->
                TrackSearchResult(
                    provider = item.optString("provider"),
                    providerTrackId = item.optString("provider_track_id"),
                    title = item.optString("title"),
                    artists = item.optJSONArray("artists")?.toStringList() ?: emptyList(),
                    album = item.optString("album").takeIf { it.isNotBlank() },
                    duration = if (item.isNull("duration")) null else item.optDouble("duration"),
                    artwork = item.optString("artwork").takeIf { it.isNotBlank() },
                    isrc = item.optString("isrc").takeIf { it.isNotBlank() },
                )
            }
        }
    }

    fun me(): JSONObject = request("/auth/me", "GET", null, requireAccessToken())

    fun logout() = clearSession()

    private fun saveSession(json: JSONObject): AuthSession {
        val tokens = json.getJSONObject("tokens")
        val user = json.getJSONObject("user")
        val session = AuthSession(
            accessToken = tokens.getString("access_token"),
            refreshToken = tokens.getString("refresh_token"),
            expiresIn = tokens.getLong("expires_in"),
            userId = user.getString("id"),
            displayName = user.getString("display_name"),
        )
        store.put("access_token", session.accessToken)
        store.put("refresh_token", session.refreshToken)
        return session
    }

    private fun requireAccessToken(): String =
        store.get("access_token") ?: throw APIException(401, "No hay sesión")

    private fun clearSession() {
        store.remove("access_token")
        store.remove("refresh_token")
    }

    private fun request(path: String, method: String, body: String?, token: String? = null, allowRefresh: Boolean = true): JSONObject {
        val text = requestRaw(path, method, body, token, allowRefresh)
        return if (text.isBlank()) JSONObject() else JSONObject(text)
    }

    private fun requestRaw(
        path: String,
        method: String,
        body: String?,
        token: String? = null,
        allowRefresh: Boolean = true,
    ): String {
        val connection = (URL(baseUrl + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 15_000
            readTimeout = 30_000
            setRequestProperty("Accept", "application/json")
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("X-Device-ID", device.id)
            token?.let { setRequestProperty("Authorization", "Bearer $it") }
            if (body != null) {
                doOutput = true
                outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            }
        }
        return try {
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (code !in 200..299) {
                if (code == 401 && allowRefresh && token != null && refresh()) {
                    return requestRaw(path, method, body, store.get("access_token"), allowRefresh = false)
                }
                val message = runCatching {
                    JSONObject(text).getJSONObject("error").getString("message")
                }.getOrDefault("Error HTTP $code")
                throw APIException(code, message)
            }
            text
        } finally {
            connection.disconnect()
        }
    }
}

private fun org.json.JSONArray.toStringList(): List<String> =
    (0 until length()).map { getString(it) }

private fun org.json.JSONArray.getDiscoveryTracks(): List<DiscoveryTrack> =
    (0 until length()).mapNotNull { i ->
        optJSONObject(i)?.let { item ->
            val id = item.optString("id")
            if (id.isBlank()) null else DiscoveryTrack(
                id,
                item.optString("title"),
                if (item.isNull("duration")) null else item.optDouble("duration"),
            )
        }
    }

private fun org.json.JSONArray.getDiscoveryRankings(): List<DiscoveryRanking> =
    (0 until length()).mapNotNull { i ->
        optJSONObject(i)?.let { item ->
            val id = item.optString("track_id")
            if (id.isBlank()) null else DiscoveryRanking(
                id,
                item.optString("title").takeIf { it.isNotBlank() },
                item.optInt("rank"),
            )
        }
    }

private fun org.json.JSONArray.getJSONObjectStrings(key: String): List<String> =
    (0 until length()).mapNotNull { i -> optJSONObject(i)?.optString(key)?.takeIf { it.isNotBlank() } }
