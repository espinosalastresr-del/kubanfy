package com.kubanfy.android

import android.app.Activity
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.ProgressBar
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var api: APIClient
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        api = APIClient(this)
        showLogin()
    }

    private fun showLogin() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(48, 72, 48, 48)
        }
        root.addView(TextView(this).apply {
            text = "KubanFy"
            textSize = 32f
            gravity = Gravity.CENTER
        })
        root.addView(TextView(this).apply {
            text = "Música cubana · offline-first · nativo"
            textSize = 16f
            gravity = Gravity.CENTER
            setPadding(0, 24, 0, 32)
        })
        val email = EditText(this).apply {
            hint = "Correo"
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
        }
        val password = EditText(this).apply {
            hint = "Contraseña"
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        val login = Button(this).apply { text = "Iniciar sesión"; isAllCaps = false }
        status = TextView(this).apply { setPadding(0, 24, 0, 0) }
        root.addView(email)
        root.addView(password)
        root.addView(login)
        root.addView(status)
        setContentView(root)

        login.setOnClickListener {
            login.isEnabled = false
            status.text = "Conectando…"
            executor.execute {
                try {
                    val session = api.login(email.text.toString(), password.text.toString())
                    val context = api.context()
                    val discovery = api.discoveryHome()
                    runOnUiThread { showHome(session.displayName, context, discovery) }
                } catch (e: Exception) {
                    runOnUiThread {
                        status.text = e.message ?: "No se pudo iniciar sesión"
                        login.isEnabled = true
                    }
                }
            }
        }
    }

    private fun showHome(displayName: String, context: AuthContext, discovery: DiscoveryHome) {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(48, 72, 48, 48)
        }
        root.addView(TextView(this).apply {
            text = "Hola, $displayName"
            textSize = 26f
            gravity = Gravity.CENTER
        })
        root.addView(TextView(this).apply {
            text = buildString {
                append("Sesión segura · dispositivo identificado")
                if (context.isAdmin) append("\nAcceso administrativo")
                if (context.isArtist) append("\nAcceso de artista")
            }
            textSize = 14f
            gravity = Gravity.CENTER
            setPadding(0, 12, 0, 32)
        })
        root.addView(TextView(this).apply {
            text = "Descubrimiento · ${discovery.country}"
            textSize = 20f
            setPadding(0, 12, 0, 8)
        })
        root.addView(TextView(this).apply {
            text = "Artistas locales: ${discovery.localArtists.take(5).joinToString(", ")}"
        })
        root.addView(TextView(this).apply {
            text = "Nuevos lanzamientos: ${discovery.newReleases.take(5).joinToString(", ")}"
            setPadding(0, 8, 0, 16)
        })
        root.addView(Button(this).apply {
            text = "Buscar"
            isAllCaps = false
            setOnClickListener { showSearch() }
        })
        listOf("Inicio", "Biblioteca", "Playlists").forEach { label ->
            root.addView(Button(this).apply { text = label; isAllCaps = false })
        }
        if (context.isArtist) root.addView(Button(this).apply { text = "Panel de artista"; isAllCaps = false })
        if (context.isAdmin) root.addView(Button(this).apply { text = "Administración"; isAllCaps = false })
        root.addView(Button(this).apply {
            text = "Cerrar sesión"
            isAllCaps = false
            setOnClickListener { api.logout(); showLogin() }
        })
        setContentView(root)
    }

    private fun showSearch() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 48, 32, 32)
        }
        val query = EditText(this).apply {
            hint = "Buscar canciones o artistas"
            singleLine = true
            inputType = android.text.InputType.TYPE_CLASS_TEXT
        }
        val search = Button(this).apply {
            text = "Buscar"
            isAllCaps = false
        }
        val progress = ProgressBar(this).apply { visibility = android.view.View.GONE }
        val results = TextView(this).apply { setPadding(0, 24, 0, 0) }
        val back = Button(this).apply { text = "Volver"; isAllCaps = false }
        root.addView(query)
        root.addView(search)
        root.addView(progress)
        root.addView(results)
        root.addView(back)
        setContentView(root)

        back.setOnClickListener {
            executor.execute {
                try {
                    val context = api.context()
                    val discovery = api.discoveryHome()
                    val displayName = api.me().optString("display_name", "Usuario")
                    runOnUiThread { showHome(displayName, context, discovery) }
                } catch (e: Exception) {
                    runOnUiThread { showLogin() }
                }
            }
        }

        search.setOnClickListener {
            val text = query.text.toString().trim()
            if (text.isEmpty()) {
                results.text = "Escribe algo para buscar."
                return@setOnClickListener
            }
            search.isEnabled = false
            progress.visibility = android.view.View.VISIBLE
            results.text = "Buscando…"
            executor.execute {
                try {
                    val found = api.search(text)
                    val rendered = if (found.isEmpty()) {
                        "No se encontraron resultados."
                    } else {
                        found.joinToString("\n\n") { track ->
                            val artists = track.artists.joinToString(", ")
                            buildString {
                                append(track.title)
                                if (artists.isNotBlank()) append("\n$artists")
                                track.album?.let { append("\n$it") }
                            }
                        }
                    }
                    runOnUiThread {
                        results.text = rendered
                        search.isEnabled = true
                        progress.visibility = android.view.View.GONE
                    }
                } catch (e: Exception) {
                    runOnUiThread {
                        results.text = e.message ?: "No se pudo buscar."
                        search.isEnabled = true
                        progress.visibility = android.view.View.GONE
                    }
                }
            }
        }
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }
}
