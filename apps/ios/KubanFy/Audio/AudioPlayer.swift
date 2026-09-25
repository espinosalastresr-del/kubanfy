import SwiftUI
import AVFoundation
import MediaPlayer

enum RepeatMode { case off, all, one }

@MainActor
final class AudioPlayer: ObservableObject {
    @Published private(set) var currentTrackID: UUID?
    @Published private(set) var errorMessage: String?
    @Published private(set) var isPlaying = false
    @Published private(set) var position: Double = 0
    @Published private(set) var duration: Double = 0
    @Published private(set) var currentTitle: String?
    @Published private(set) var isLoading = false
    @Published private(set) var isShuffled = false
    @Published private(set) var repeatMode: RepeatMode = .off

    private var player: AVPlayer?
    private var timeObserver: Any?
    private var currentTrack: DiscoveryHome.Track?
    private var currentPlayback: PlaybackResponse?
    private var currentLocalAudioURL: URL?
    private var playbackToken: String?
    private var playbackSessionID: UUID?
    private var heartbeatTask: Task<Void, Never>?
    private var notificationTokens: [NSObjectProtocol] = []
    private var recoveryTask: Task<Void, Never>?
    private var recoveryAttempts = 0
    private var playbackGeneration = UUID()

    init() {
        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playback, mode: .default, options: [])
        try? session.setActive(true)

        let interruption = NotificationCenter.default.addObserver(
            forName: AVAudioSession.interruptionNotification,
            object: session,
            queue: .main
        ) { [weak self] notification in
            Task { @MainActor in
                self?.handleInterruption(notification)
            }
        }
        notificationTokens.append(interruption)

        let failed = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemFailedToPlayToEndTime,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            Task { @MainActor in
                await self?.handlePlaybackFailure(notification)
            }
        }
        notificationTokens.append(failed)

        let ended = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            Task { @MainActor in
                await self?.handlePlaybackEnded(notification)
            }
        }
        notificationTokens.append(ended)

        let commands = MPRemoteCommandCenter.shared()
        commands.playCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            Task { @MainActor in
                await self.resume()
            }
            return .success
        }
        commands.pauseCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            Task { @MainActor in
                await self.pause()
            }
            return .success
        }
        commands.changePlaybackPositionCommand.addTarget { [weak self] event in
            guard let self, let event = event as? MPChangePlaybackPositionCommandEvent else {
                return .commandFailed
            }
            Task { @MainActor in
                self.seek(to: event.positionTime)
            }
            return .success
        }
    }

    func toggleShuffle() {
        isShuffled.toggle()
    }

    func cycleRepeat() {
        switch repeatMode {
        case .off: repeatMode = .all
        case .all: repeatMode = .one
        case .one: repeatMode = .off
        }
    }

    func toggle(track: DiscoveryHome.Track) async {
        errorMessage = nil

        if currentTrackID == track.id {
            if isPlaying {
                await pause()
            } else if shouldRestartCurrentItem {
                await start(track: track)
            } else {
                await resume()
            }
            return
        }

        await start(track: track)
    }

    func toggleCurrent() async {
        guard let track = currentTrack else { return }
        await toggle(track: track)
    }

    private var shouldRestartCurrentItem: Bool {
        guard let item = player?.currentItem else { return true }
        if item.status == .failed { return true }
        if item.status != .readyToPlay { return true }
        if duration > 0, position >= max(0, duration - 0.5) { return true }
        return false
    }

    private func start(track: DiscoveryHome.Track) async {
        isLoading = true
        isPlaying = false
        errorMessage = nil
        currentTrack = track
        currentTrackID = track.id
        currentTitle = track.title

        heartbeatTask?.cancel()
        heartbeatTask = nil
        recoveryTask?.cancel()
        recoveryTask = nil
        recoveryAttempts = 0
        playbackGeneration = UUID()
        let generation = playbackGeneration

        defer {
            if generation == playbackGeneration {
                isLoading = false
            }
        }

        // Offline-first: a valid device-bound bootstrap asset is playable with
        // no network and remains encrypted on disk.
        if let localURL = try? APIClient.shared.cachedOfflinePlaybackURL(
            trackId: track.id,
            quality: "low"
        ) {
            do {
                try await activateLocalItem(
                    localURL,
                    track: track,
                    generation: generation,
                    position: 0
                )
                attachAnalyticsSessionIfPossible(track: track, generation: generation)
                return
            } catch {
                // Corrupt/unsupported local data falls through to the normal
                // authorized online path. The cache layer already removes bad data.
            }
        }

        do {
            let session = try await APIClient.shared.startPlayback(
                trackId: track.id,
                quality: "low"
            )
            let playback = try await APIClient.shared.playback(
                trackId: track.id,
                quality: "low"
            )
            guard generation == playbackGeneration else { return }

            playbackToken = session.playbackToken
            playbackSessionID = session.playbackSessionId
            currentPlayback = playback
            duration = track.duration ?? 0
            position = 0

            let localURL = try await APIClient.shared.cacheAuthorizedPlaybackKBY(playback)
            guard generation == playbackGeneration else {
                try? FileManager.default.removeItem(at: localURL)
                return
            }

            try await activateLocalItem(
                localURL,
                track: track,
                generation: generation,
                position: 0
            )
            startHeartbeatLoop(interval: session.heartbeatIntervalSeconds)
        } catch {
            guard generation == playbackGeneration else { return }
            stopPlaybackResources()
            isPlaying = false
            errorMessage = error.localizedDescription
            updateNowPlaying()
        }
    }

    private func activateLocalItem(
        _ url: URL,
        track: DiscoveryHome.Track,
        generation: UUID,
        position: Double
    ) async throws {
        guard generation == playbackGeneration else { return }
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw APIError.offlineUnavailable
        }

        let item = AVPlayerItem(url: url)
        item.preferredForwardBufferDuration = 0
        try await waitUntilReady(item)

        guard generation == playbackGeneration else { return }

        let oldURL = currentLocalAudioURL
        if let player {
            player.replaceCurrentItem(with: item)
        } else {
            let newPlayer = AVPlayer(playerItem: item)
            player = newPlayer
            timeObserver = newPlayer.addPeriodicTimeObserver(
                forInterval: CMTime(seconds: 0.5, preferredTimescale: 600),
                queue: .main
            ) { [weak self] time in
                Task { @MainActor in
                    guard let self else { return }
                    let value = time.seconds
                    self.position = max(0, value.isFinite ? value : 0)
                    self.updateNowPlaying()
                }
            }
        }

        currentLocalAudioURL = url
        duration = max(
            duration,
            item.asset.duration.seconds.isFinite ? item.asset.duration.seconds : 0
        )

        if position > 0 {
            player?.seek(
                to: CMTime(seconds: position, preferredTimescale: 600),
                toleranceBefore: .zero,
                toleranceAfter: .zero
            )
        }

        if let oldURL, oldURL != url {
            try? FileManager.default.removeItem(at: oldURL)
        }

        currentTrack = track
        currentTrackID = track.id
        currentTitle = track.title
        isPlaying = true
        errorMessage = nil
        try? AVAudioSession.sharedInstance().setActive(true)
        player?.play()
        updateNowPlaying()
    }

    private func waitUntilReady(_ item: AVPlayerItem) async throws {
        for _ in 0..<100 {
            switch item.status {
            case .readyToPlay:
                return
            case .failed:
                throw item.error ?? APIError.audioDelivery
            case .unknown:
                try await Task.sleep(nanoseconds: 50_000_000)
            @unknown default:
                throw APIError.audioDelivery
            }
        }
        throw APIError.http(408, "El audio no estuvo listo a tiempo")
    }

    private func attachAnalyticsSessionIfPossible(
        track: DiscoveryHome.Track,
        generation: UUID
    ) {
        Task { [weak self] in
            do {
                let session = try await APIClient.shared.startPlayback(
                    trackId: track.id,
                    quality: "low"
                )
                guard let self, self.playbackGeneration == generation,
                      self.currentTrackID == track.id else { return }
                self.playbackToken = session.playbackToken
                self.playbackSessionID = session.playbackSessionId
                self.startHeartbeatLoop(interval: session.heartbeatIntervalSeconds)
            } catch {
                // Offline playback must not fail because analytics are unavailable.
            }
        }
    }

    private func startHeartbeatLoop(interval: Int) {
        heartbeatTask?.cancel()
        let seconds = max(5, interval)
        heartbeatTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: UInt64(seconds) * 1_000_000_000)
                guard !Task.isCancelled else { return }
                await self?.sendHeartbeat(completed: false)
            }
        }
    }

    private func sendHeartbeat(completed: Bool) async {
        guard let token = playbackToken else { return }
        do {
            _ = try await APIClient.shared.heartbeat(
                token: token,
                positionMs: Int(max(0, position) * 1000),
                paused: !isPlaying,
                completed: completed
            )
        } catch {
            // Connectivity loss must not interrupt local audio.
        }
    }

    private func pause() async {
        player?.pause()
        isPlaying = false
        updateNowPlaying()
        await sendHeartbeat(completed: false)
    }

    private func resume() async {
        if shouldRestartCurrentItem, let track = currentTrack {
            await start(track: track)
            return
        }
        try? AVAudioSession.sharedInstance().setActive(true)
        player?.play()
        isPlaying = true
        errorMessage = nil
        updateNowPlaying()
    }

    func seek(to seconds: Double) {
        guard seconds.isFinite, seconds >= 0 else { return }
        guard let player, let item = player.currentItem,
              item.status == .readyToPlay else { return }
        player.seek(
            to: CMTime(seconds: seconds, preferredTimescale: 600),
            toleranceBefore: .zero,
            toleranceAfter: .zero
        )
        position = seconds
        updateNowPlaying()
    }

    private func handlePlaybackFailure(_ notification: Notification) async {
        guard let failedItem = notification.object as? AVPlayerItem,
              failedItem === player?.currentItem,
              currentTrackID != nil,
              currentTrack != nil else {
            return
        }
        guard recoveryTask == nil else { return }

        let generation = playbackGeneration
        let savedPosition = min(position, max(0, duration))
        recoveryTask = Task { [weak self] in
            guard let self else { return }
            for attempt in 0..<2 {
                guard !Task.isCancelled, generation == self.playbackGeneration,
                      let track = self.currentTrack else { return }

                self.recoveryAttempts = attempt + 1
                try? await Task.sleep(nanoseconds: UInt64(500_000_000 * (attempt + 1)))
                guard !Task.isCancelled, generation == self.playbackGeneration else { return }

                do {
                    if let offlineURL = try? APIClient.shared.cachedOfflinePlaybackURL(
                        trackId: track.id,
                        quality: "low"
                    ) {
                        try await self.activateLocalItem(
                            offlineURL,
                            track: track,
                            generation: generation,
                            position: savedPosition
                        )
                        self.errorMessage = nil
                        return
                    }

                    guard let playback = self.currentPlayback else {
                        let fresh = try await APIClient.shared.playback(
                            trackId: track.id,
                            quality: "low"
                        )
                        guard generation == self.playbackGeneration else { return }
                        self.currentPlayback = fresh
                        let localURL = try await APIClient.shared.cacheAuthorizedPlaybackKBY(fresh)
                        try await self.activateLocalItem(
                            localURL,
                            track: track,
                            generation: generation,
                            position: savedPosition
                        )
                        self.errorMessage = nil
                        return
                    }

                    let localURL = try await APIClient.shared.cacheAuthorizedPlaybackKBY(playback)
                    guard generation == self.playbackGeneration else { return }
                    try await self.activateLocalItem(
                        localURL,
                        track: track,
                        generation: generation,
                        position: savedPosition
                    )
                    self.errorMessage = nil
                    return
                } catch {
                    continue
                }
            }

            guard generation == self.playbackGeneration else { return }
            self.isPlaying = false
            self.errorMessage = "No se pudo recuperar la reproducción. Inténtalo de nuevo."
            self.updateNowPlaying()
        }

        await recoveryTask?.value
        recoveryTask = nil
        recoveryAttempts = 0
    }

    private func handlePlaybackEnded(_ notification: Notification) async {
        guard let endedItem = notification.object as? AVPlayerItem,
              endedItem === player?.currentItem,
              currentTrackID != nil else {
            return
        }

        if repeatMode == .one {
            player?.seek(to: .zero)
            position = 0
            isPlaying = true
            player?.play()
            updateNowPlaying()
            return
        }

        isPlaying = false
        position = duration
        await sendHeartbeat(completed: true)
        updateNowPlaying()
    }

    private func updateNowPlaying() {
        guard let track = currentTrack else {
            MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
            return
        }

        var info: [String: Any] = [
            MPMediaItemPropertyTitle: track.title,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: position,
            MPNowPlayingInfoPropertyPlaybackRate: isPlaying ? 1.0 : 0.0
        ]
        if let duration = track.duration {
            info[MPMediaItemPropertyPlaybackDuration] = duration
        }
        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
    }

    private func handleInterruption(_ notification: Notification) {
        guard
            let raw = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
            let type = AVAudioSession.InterruptionType(rawValue: raw)
        else {
            return
        }

        if type == .ended {
            try? AVAudioSession.sharedInstance().setActive(true)
        } else {
            isPlaying = false
            Task { await sendHeartbeat(completed: false) }
        }
        updateNowPlaying()
    }

    private func stopPlaybackResources() {
        heartbeatTask?.cancel()
        recoveryTask?.cancel()
        heartbeatTask = nil
        recoveryTask = nil
        playbackToken = nil
        playbackSessionID = nil
        currentPlayback = nil
        player?.pause()
        player?.replaceCurrentItem(with: nil)

        if let url = currentLocalAudioURL {
            try? FileManager.default.removeItem(at: url)
        }
        currentLocalAudioURL = nil
        duration = 0
        position = 0
        isPlaying = false
        playbackGeneration = UUID()
    }

    deinit {
        heartbeatTask?.cancel()
        recoveryTask?.cancel()
        if let timeObserver, let player {
            player.removeTimeObserver(timeObserver)
        }
        for token in notificationTokens {
            NotificationCenter.default.removeObserver(token)
        }
        player?.pause()
    }
}
