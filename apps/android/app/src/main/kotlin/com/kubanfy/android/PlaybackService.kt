package com.kubanfy.android

import android.content.Intent
import android.os.Handler
import android.os.Looper
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import java.util.concurrent.Executors

class PlaybackService : MediaSessionService() {
    companion object {
        const val ACTION_PLAY = "com.kubanfy.android.action.PLAY"
        const val ACTION_STOP = "com.kubanfy.android.action.STOP"
        const val EXTRA_TRACK_ID = "track_id"
        const val EXTRA_TITLE = "title"
        const val EXTRA_QUALITY = "quality"
    }

    private val executor = Executors.newSingleThreadExecutor()
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var api: APIClient
    private lateinit var player: ExoPlayer
    private var mediaSession: MediaSession? = null
    private var trackId: String? = null
    private var title: String? = null
    private var quality = "low"
    private var renewalGeneration = 0L
    private var recoveryAttempts = 0
    private var recoveryInProgress = false

    override fun onCreate() {
        super.onCreate()
        api = APIClient(this)
        player = ExoPlayer.Builder(this).build()
        player.addListener(object : Player.Listener {
            override fun onPlayerError(error: PlaybackException) {
                if (!recoveryInProgress && recoveryAttempts < 3) recoverPlayback()
            }
        })
        mediaSession = MediaSession.Builder(this, player).build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = mediaSession

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_PLAY -> {
                val id = intent.getStringExtra(EXTRA_TRACK_ID)
                val name = intent.getStringExtra(EXTRA_TITLE)
                if (!id.isNullOrBlank() && !name.isNullOrBlank()) {
                    quality = intent.getStringExtra(EXTRA_QUALITY)?.lowercase()
                        ?.takeIf { it in setOf("low", "medium", "lossless") } ?: "low"
                    play(id, name)
                }
            }
            ACTION_STOP -> stopPlayback()
        }
        return START_STICKY
    }

    private fun play(id: String, name: String) {
        renewalGeneration += 1
        recoveryAttempts = 0
        recoveryInProgress = false
        trackId = id
        title = name
        executor.execute {
            try {
                val playback = api.playback(id, quality)
                handler.post {
                    if (trackId != id) return@post
                    replaceMediaItem(playback.url, id, name, 0L)
                    player.prepare()
                    player.play()
                    scheduleRenewal(playback.expiresInSeconds)
                }
            } catch (_: Exception) {
                recoveryInProgress = false
            }
        }
    }

    private fun replaceMediaItem(url: String, id: String, name: String, positionMs: Long) {
        val item = MediaItem.Builder()
            .setUri(url)
            .setMediaId(id)
            .setMediaMetadata(MediaMetadata.Builder().setTitle(name).build())
            .build()
        player.setMediaItem(item, positionMs)
    }

    private fun scheduleRenewal(expiresInSeconds: Long) {
        renewalGeneration += 1
        val generation = renewalGeneration
        val delay = ((expiresInSeconds - 30L).coerceAtLeast(15L)) * 1000L
        handler.postDelayed({
            if (generation != renewalGeneration) return@postDelayed
            renewPlayback(generation)
        }, delay)
    }

    private fun renewPlayback(generation: Long) {
        val id = trackId ?: return
        val name = title ?: return
        val position = player.currentPosition
        executor.execute {
            try {
                val renewed = api.playback(id, quality)
                handler.post {
                    if (generation != renewalGeneration || trackId != id) return@post
                    val wasPlaying = player.isPlaying
                    replaceMediaItem(renewed.url, id, name, position)
                    player.prepare()
                    if (wasPlaying) player.play()
                    scheduleRenewal(renewed.expiresInSeconds)
                }
            } catch (_: Exception) {
                handler.post {
                    if (generation == renewalGeneration) scheduleRenewal(30L)
                }
            }
        }
    }

    private fun recoverPlayback() {
        val id = trackId ?: return
        val name = title ?: return
        val position = player.currentPosition
        recoveryInProgress = true
        recoveryAttempts += 1
        val attempt = recoveryAttempts
        val delay = minOf(8_000L, 1_000L * (1L shl (attempt - 1)))
        executor.execute {
            try {
                Thread.sleep(delay)
                val renewed = api.playback(id, quality)
                handler.post {
                    recoveryInProgress = false
                    if (trackId != id) return@post
                    replaceMediaItem(renewed.url, id, name, position)
                    player.prepare()
                    player.play()
                    scheduleRenewal(renewed.expiresInSeconds)
                }
            } catch (_: Exception) {
                handler.post { recoveryInProgress = false }
            }
        }
    }

    private fun stopPlayback() {
        renewalGeneration += 1
        trackId = null
        title = null
        recoveryAttempts = 0
        recoveryInProgress = false
        player.stop()
        player.clearMediaItems()
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        if (!player.isPlaying) stopSelf()
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        renewalGeneration += 1
        handler.removeCallbacksAndMessages(null)
        executor.shutdownNow()
        mediaSession?.release()
        mediaSession = null
        player.release()
        super.onDestroy()
    }
}
