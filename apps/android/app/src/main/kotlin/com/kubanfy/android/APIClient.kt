package com.kubanfy.android

import android.content.Context
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

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

    fun me(): JSONObject {
        val token = store.get("access_token") ?: throw APIException(401, "No hay sesión")
        return request("/auth/me", "GET", null, token)
    }

    fun logout() {
        store.remove("access_token")
        store.remove("refresh_token")
    }

    private fun request(path: String, method: String, body: String?, token: String? = null): JSONObject {
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
            if (text.isBlank()) JSONObject() else JSONObject(text)
        } finally {
            connection.disconnect()
        }
    }
}
