package com.kubanfy.android

import android.app.Activity
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
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
                    runOnUiThread { showHome(session.displayName) }
                } catch (e: Exception) {
                    runOnUiThread {
                        status.text = e.message ?: "No se pudo iniciar sesión"
                        login.isEnabled = true
                    }
                }
            }
        }
    }

    private fun showHome(displayName: String) {
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
            text = "Sesión segura · dispositivo identificado"
            textSize = 14f
            gravity = Gravity.CENTER
            setPadding(0, 12, 0, 32)
        })
        listOf("Inicio", "Buscar", "Biblioteca", "Playlists", "Artista", "Administración").forEach { label ->
            root.addView(Button(this).apply { text = label; isAllCaps = false })
        }
        root.addView(Button(this).apply {
            text = "Cerrar sesión"
            isAllCaps = false
            setOnClickListener { api.logout(); showLogin() }
        })
        setContentView(root)
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }
}
