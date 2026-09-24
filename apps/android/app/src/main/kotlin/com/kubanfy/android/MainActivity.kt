package com.kubanfy.android

import android.app.Activity
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
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
            setPadding(0, 24, 0, 40)
        })
        listOf("Inicio", "Buscar", "Biblioteca", "Playlists", "Artista", "Administración").forEach { label ->
            root.addView(Button(this).apply { text = label; isAllCaps = false })
        }
        setContentView(root)
    }
}
