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

data class DiscoveryHome(
    val country: String,
    val localArtists: List<String>,
    val topCountry: List<String>,
    val topGlobal: List<String>,
    val newReleases: List<String>,
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
        val json = request("/auth/login", "POST", body.toString())
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

    fun context(): AuthContext {
        val token = store.get("access_token") ?: throw APIException(401, "No hay sesión")
        val json = request("/auth/context", "GET", null, token)
        return AuthContext(
            roles = json.getJSONArray("roles").toStringList(),
            artistIds = json.getJSONArray("artist_ids").toStringList(),
            isArtist = json.getBoolean("is_artist"),
            isAdmin = json.getBoolean("is_admin"),
        )
    }

    fun discoveryHome(): DiscoveryHome {
        val json = request("/discovery/home", "GET", null, store.get("access_token"))
        return DiscoveryHome(
            country = json.getString("country"),
            localArtists = json.getJSONArray("local_artists").getJSONObjectStrings("name"),
            topCountry = json.getJSONArray("top_50_country").getJSONObjectStrings("title"),
            topGlobal = json.getJSONArray("top_50_global").getJSONObjectStrings("title"),
            newReleases = json.getJSONArray("new_releases").getJSONObjectStrings("title"),
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

    fun me(): JSONObject {
        val token = store.get("access_token") ?: throw APIException(401, "No hay sesión")
        return request("/auth/me", "GET", null, token)
    }

    fun logout() {
        store.remove("access_token")
        store.remove("refresh_token")
    }

    private fun request(path: String, method: String, body: String?, token: String? = null): JSONObject {
        val text = requestRaw(path, method, body, token)
        return if (text.isBlank()) JSONObject() else JSONObject(text)
    }

    private fun requestRaw(path: String, method: String, body: String?, token: String? = null): String {
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

private fun org.json.JSONArray.getJSONObjectStrings(key: String): List<String> =
    (0 until length()).mapNotNull { i -> optJSONObject(i)?.optString(key)?.takeIf { it.isNotBlank() } }
