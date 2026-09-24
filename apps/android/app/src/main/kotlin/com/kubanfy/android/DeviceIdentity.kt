package com.kubanfy.android

import android.content.Context
import java.util.UUID

class DeviceIdentity(context: Context) {
    private val prefs = context.getSharedPreferences("kubanfy_device", Context.MODE_PRIVATE)

    val id: String
        get() {
            prefs.getString("id", null)?.let { return it }
            val value = UUID.randomUUID().toString()
            prefs.edit().putString("id", value).apply()
            return value
        }
}
