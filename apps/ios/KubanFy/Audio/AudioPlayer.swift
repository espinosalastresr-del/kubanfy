import SwiftUI
import AVFoundation
import MediaPlayer

private enum RepeatMode { case off, all, one }

@MainActor


private final class AudioPlayer: ObservableObject {
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
    private var renewalTask: Task<Void, Never>?
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
        ) { [weak self] _ in
            Task { @MainActor in
                await self?.handlePlaybackEnded()
            }
        }
        notificationTokens.append(ended)

        let commands = MPRemoteCommandCenter.shared()
        commands.playCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            Task { @MainActor in
                self.resume()
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

    func toggleShuffle() { isShuffled.toggle() }

    func cycleRepeat() {
        switch repeatMode { case .off: repeatMode = .all; case .all: repeatMode = .one; case .one: repeatMode = .off }
    }

    func toggle(track: DiscoveryHome.Track) async {
        errorMessage = nil
        if currentTrackID == track.id {
            if isPlaying {
                await pause()
            } else {
                resume()
            }
            return
        }
        await start(track: track)
    }

    func toggleCurrent() async {
        guard currentTrack != nil else { return }
        if isPlaying { await pause() } else { resume() }
    }

    private func start(track: DiscoveryHome.Track) async {
        isLoading = true
        errorMessage = nil
        currentTrack = track
        currentTrackID = track.id
        currentTitle = track.title
        defer { isLoading = false }
        do {
            heartbeatTask?.cancel()
            renewalTask?.cancel()
            recoveryTask?.cancel()
            recoveryAttempts = 0
            playbackGeneration = UUID()
            let generation = playbackGeneration
            let session = try await APIClient.shared.startPlayback(
                trackId: track.id,
                quality: "low"
            )
            playbackToken = session.playbackToken
            playbackSessionID = session.playbackSessionId
            let playback = try await APIClient.shared.playback(trackId: track.id, quality: "low")
            guard generation == playbackGeneration else { return }
            currentPlayback = playback
            let localURL = try await APIClient.shared.fetchAndDecryptKBY(playback)
            guard generation == playbackGeneration else { return }
            duration = track.duration ?? 0
            position = 0
            try? AVAudioSession.sharedInstance().setActive(true)
            replaceItem(with: localURL, position: 0)
            isPlaying = true
            updateNowPlaying()
            player?.play()
            startHeartbeatLoop(interval: session.heartbeatIntervalSeconds)
            startRenewalLoop(expiresIn: playback.expiresInSeconds)
        } catch {
            stopPlaybackResources()
            isPlaying = false
            errorMessage = error.localizedDescription
            updateNowPlaying()
        }
    }

    private func replaceItem(with url: URL, position: Double) {
        if let previous = currentLocalAudioURL, previous != url {
            try? FileManager.default.removeItem(at: previous)
        }
        currentLocalAudioURL = url
        let item = AVPlayerItem(url: url)
        if let itemDuration = item.asset.duration.seconds.isFinite ? item.asset.duration.seconds : nil, itemDuration > 0 { duration = itemDuration }
        if let player {
            player.replaceCurrentItem(with: item)
        } else {
            player = AVPlayer(playerItem: item)
            timeObserver = player?.addPeriodicTimeObserver(
                forInterval: CMTime(seconds: 1, preferredTimescale: 600),
                queue: .main
            ) { [weak self] time in
                Task { @MainActor in
                    self?.position = max(0, time.seconds.isFinite ? time.seconds : 0)
                    self?.updateNowPlaying()
                }
            }
        }
        let target = max(0, position)
        if target > 0 {
            player?.seek(to: CMTime(seconds: target, preferredTimescale: 600))
        }
        player?.playImmediately(atRate: 1)
    }

    private func startHeartbeatLoop(interval: Int) {
        heartbeatTask?.cancel()
        let seconds = max(5, interval)
        heartbeatTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(seconds))
                guard !Task.isCancelled else { return }
                await self?.sendHeartbeat(completed: false)
            }
        }
    }

    private func startRenewalLoop(expiresIn: Int) {
        renewalTask?.cancel()
        let delay = max(15, expiresIn - 30)
        renewalTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(delay))
            guard !Task.isCancelled else { return }
            await self?.renewSignedURL()
        }
    }

    private func renewSignedURL() async {
        guard let track = currentTrack else { return }
        let savedPosition = position
        do {
            let playback = try await APIClient.shared.playback(trackId: track.id, quality: "low")
            guard currentTrackID == track.id else { return }
            currentPlayback = playback
            let localURL = try await APIClient.shared.fetchAndDecryptKBY(playback)
            guard currentTrackID == track.id else { return }
            replaceItem(with: localURL, position: savedPosition)
            if !isPlaying { player?.pause() }
            startRenewalLoop(expiresIn: playback.expiresInSeconds)
        } catch {
            // Keep the current item alive; the next playback error will retry renewal.
            startRenewalLoop(expiresIn: max(15, currentPlayback?.expiresInSeconds ?? 30))
        }
    }

    private func handlePlaybackFailure(_ notification: Notification) async {
        guard currentTrackID != nil, currentTrack != nil else { return }
        guard recoveryTask == nil else { return }
        let generation = playbackGeneration
        let savedPosition = position
        recoveryTask = Task { [weak self] in
            guard let self else { return }
            for attempt in 0..<3 {
                guard !Task.isCancelled, generation == self.playbackGeneration else { return }
                self.recoveryAttempts = attempt + 1
                let delay = UInt64(1 << attempt)
                try? await Task.sleep(for: .seconds(delay))
                guard !Task.isCancelled, generation == self.playbackGeneration,
                      let track = self.currentTrack else { return }
                do {
                    let playback = try await APIClient.shared.playback(trackId: track.id, quality: "low")
                    guard generation == self.playbackGeneration, self.currentTrackID == track.id else { return }
                    self.currentPlayback = playback
                    let localURL = try await APIClient.shared.fetchAndDecryptKBY(playback)
                    guard generation == self.playbackGeneration, self.currentTrackID == track.id else { return }
                    self.replaceItem(with: localURL, position: savedPosition)
                    self.isPlaying = true
                    self.errorMessage = nil
                    self.startRenewalLoop(expiresIn: playback.expiresInSeconds)
                    return
                } catch {
                    continue
                }
            }
            guard generation == self.playbackGeneration else { return }
            self.isPlaying = false
            self.errorMessage = "No se pudo recuperar la reproducción. Comprueba la conexión e inténtalo de nuevo."
        }
        await recoveryTask?.value
        recoveryTask = nil
        recoveryAttempts = 0
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
            // Connectivity loss must not stop local playback.
        }
    }

    private func pause() async {
        player?.pause()
        isPlaying = false
        updateNowPlaying()
        await sendHeartbeat(completed: false)
    }

    private func resume() {
        try? AVAudioSession.sharedInstance().setActive(true)
        player?.play()
        isPlaying = true
        updateNowPlaying()
    }

    func seek(to seconds: Double) {
        guard seconds.isFinite, seconds >= 0 else { return }
        player?.seek(to: CMTime(seconds: seconds, preferredTimescale: 600))
        position = seconds
        updateNowPlaying()
    }

    private func handlePlaybackEnded() async {
        if repeatMode == .one, let track = currentTrack {
            await start(track: track)
            return
        }
        isPlaying = false
        position = duration
        await sendHeartbeat(completed: true)
        updateNowPlaying()
    }
    private func updateNowPlaying() {
        guard let track = currentTrack else { MPNowPlayingInfoCenter.default().nowPlayingInfo = nil; return }
        var info: [String: Any] = [MPMediaItemPropertyTitle: track.title, MPNowPlayingInfoPropertyElapsedPlaybackTime: position, MPNowPlayingInfoPropertyPlaybackRate: isPlaying ? 1.0 : 0.0]
        if let duration = track.duration { info[MPMediaItemPropertyPlaybackDuration] = duration }
        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
    }
    private func handleInterruption(_ notification: Notification) {
        guard let raw = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt, let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }
        if type == .ended { try? AVAudioSession.sharedInstance().setActive(true) } else { isPlaying = false; Task { await sendHeartbeat(completed: false) } }
        updateNowPlaying()
    }
    private func stopPlaybackResources() {
        heartbeatTask?.cancel(); renewalTask?.cancel(); recoveryTask?.cancel()
        heartbeatTask = nil; renewalTask = nil; recoveryTask = nil
        playbackToken = nil; playbackSessionID = nil; currentPlayback = nil; player?.pause()
        if let url = currentLocalAudioURL { try? FileManager.default.removeItem(at: url) }
        currentLocalAudioURL = nil; duration = 0; position = 0; isPlaying = false; playbackGeneration = UUID()
    }
    private func resetPlaybackState() { stopPlaybackResources(); currentTrack = nil; currentTrackID = nil; currentTitle = nil; errorMessage = nil }
    deinit {
        heartbeatTask?.cancel(); renewalTask?.cancel(); recoveryTask?.cancel()
        if let timeObserver, let player { player.removeTimeObserver(timeObserver) }
        for token in notificationTokens { NotificationCenter.default.removeObserver(token) }
        player?.pause()
    }
}
