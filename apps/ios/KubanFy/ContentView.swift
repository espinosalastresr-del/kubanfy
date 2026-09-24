import SwiftUI
import AVFoundation
import MediaPlayer

struct ContentView: View {
    @State private var email = ""
    @State private var password = ""
    @State private var user: UserResponse?
    @State private var authContext: AuthContext?
    @State private var discovery: DiscoveryHome?
    @State private var errorMessage: String?
    @State private var isLoading = false
    @StateObject private var audioPlayer = AudioPlayer()

    var body: some View {
        NavigationStack {
            Group {
                if let user {
                    home(user, context: authContext, discovery: discovery)
                } else {
                    login
                }
            }
            .navigationTitle("KubanFy")
        }
        .task {
            guard user == nil else { return }
            do {
                user = try await APIClient.shared.me()
                authContext = try await APIClient.shared.context()
                discovery = try await APIClient.shared.discoveryHome()
            } catch {
                user = nil
            }
        }
    }

    private var login: some View {
        Form {
            Section {
                Text("Música cubana · offline-first · nativo")
                    .font(.subheadline)
                TextField("Correo", text: $email)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.emailAddress)
                    .autocorrectionDisabled()
                SecureField("Contraseña", text: $password)
                Button(isLoading ? "Conectando…" : "Iniciar sesión") {
                    Task { await performLogin() }
                }
                .disabled(isLoading || email.isEmpty || password.isEmpty)
            }
            if let errorMessage {
                Section {
                    Text(errorMessage).foregroundStyle(.red)
                }
            }
        }
    }

    private func home(_ user: UserResponse, context: AuthContext?, discovery: DiscoveryHome?) -> some View {
        List {
            Section("Cuenta") {
                Text("Hola, \(user.displayName)")
                Text("País: \(user.country)")
                    .foregroundStyle(.secondary)
            }
            if let context {
                Section("Accesos") {
                    Text(context.isArtist ? "Artista habilitado" : "Cuenta de usuario")
                    if context.isAdmin { Text("Administración habilitada") }
                }
            }
            if let discovery {
                Section("Descubrimiento · \(discovery.country)") {
                    Text("Artistas locales: \(discovery.localArtists.prefix(5).map(\.name).joined(separator: ", "))")
                    ForEach(discovery.newReleases.prefix(10), id: \.id) { track in
                        HStack {
                            VStack(alignment: .leading) {
                                Text(track.title)
                                if let duration = track.duration {
                                    Text(formatDuration(duration))
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            Spacer()
                            Button(audioPlayer.currentTrackID == track.id && audioPlayer.isPlaying ? "Pausa" : "Reproducir") {
                                Task { await audioPlayer.toggle(track: track) }
                            }
                            .buttonStyle(.borderless)
                        }
                    }
                    Text("Tendencias: \(discovery.trending.prefix(5).compactMap(\.title).joined(separator: ", "))")
                }
            }
            Section("KubanFy") {
                NavigationLink("Buscar") { SearchView() }
                Text("Inicio")
                Text("Biblioteca")
                Text("Playlists")
                if context?.isArtist == true { Text("Panel de artista") }
                if context?.isAdmin == true { Text("Administración") }
            }
            Section {
                Button("Cerrar sesión", role: .destructive) {
                    APIClient.shared.logout()
                    self.user = nil
                    self.authContext = nil
                    self.discovery = nil
                }
            }
        }
    }

    private func performLogin() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            user = try await APIClient.shared.login(email: email, password: password).user
            authContext = try await APIClient.shared.context()
            discovery = try await APIClient.shared.discoveryHome()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct SearchView: View {
    @State private var query = ""
    @State private var results: [TrackSearchResult] = []
    @State private var errorMessage: String?
    @State private var isLoading = false

    var body: some View {
        List {
            Section {
                TextField("Canción o artista", text: $query)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Button(isLoading ? "Buscando…" : "Buscar") {
                    Task { await performSearch() }
                }
                .disabled(isLoading || query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }

            if let errorMessage {
                Section {
                    Text(errorMessage).foregroundStyle(.red)
                }
            }

            Section("Resultados") {
                if results.isEmpty && !isLoading {
                    Text("No hay resultados todavía.")
                        .foregroundStyle(.secondary)
                }
                ForEach(results) { track in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(track.title).font(.headline)
                        Text(track.artists.joined(separator: ", "))
                            .foregroundStyle(.secondary)
                        if let album = track.album {
                            Text(album)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .navigationTitle("Buscar")
    }

    private func performSearch() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            results = try await APIClient.shared.search(query: query)
        } catch {
            errorMessage = error.localizedDescription
            results = []
        }
    }
}

@MainActor
private final class AudioPlayer: ObservableObject {
    @Published private(set) var currentTrackID: UUID?
    @Published private(set) var errorMessage: String?
    @Published private(set) var isPlaying = false
    @Published private(set) var position: Double = 0

    private var player: AVPlayer?
    private var timeObserver: Any?
    private var currentTrack: DiscoveryHome.Track?
    private var currentPlayback: PlaybackResponse?
    private var playbackToken: String?
    private var playbackSessionID: UUID?
    private var heartbeatTask: Task<Void, Never>?
    private var renewalTask: Task<Void, Never>?
    private var notificationTokens: [NSObjectProtocol] = []

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

    private func start(track: DiscoveryHome.Track) async {
        do {
            heartbeatTask?.cancel()
            renewalTask?.cancel()
            let session = try await APIClient.shared.startPlayback(
                trackId: track.id,
                quality: "low"
            )
            playbackToken = session.playbackToken
            playbackSessionID = session.playbackSessionId
            let playback = try await APIClient.shared.playback(trackId: track.id, quality: "low")
            currentTrack = track
            currentTrackID = track.id
            currentPlayback = playback
            position = 0
            try? AVAudioSession.sharedInstance().setActive(true)
            replaceItem(with: playback.url, position: 0)
            isPlaying = true
            updateNowPlaying()
            player?.play()
            startHeartbeatLoop(interval: session.heartbeatIntervalSeconds)
            startRenewalLoop(expiresIn: playback.expiresInSeconds)
        } catch {
            resetPlaybackState()
            errorMessage = error.localizedDescription
        }
    }

    private func replaceItem(with url: URL, position: Double) {
        let item = AVPlayerItem(url: url)
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
            replaceItem(with: playback.url, position: savedPosition)
            if !isPlaying { player?.pause() }
            startRenewalLoop(expiresIn: playback.expiresInSeconds)
        } catch {
            // Keep the current item alive; the next playback error will retry renewal.
            startRenewalLoop(expiresIn: max(15, currentPlayback?.expiresInSeconds ?? 30))
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

    private func seek(to seconds: Double) {
        guard seconds.isFinite, seconds >= 0 else { return }
        player?.seek(to: CMTime(seconds: seconds, preferredTimescale: 600))
        position = seconds
        updateNowPlaying()
    }

    private func handlePlaybackEnded() async {
        isPlaying = false
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
        guard let typeValue = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
              let type = AVAudioSession.InterruptionType(rawValue: typeValue) else { return }
        if type == .ended {
            try? AVAudioSession.sharedInstance().setActive(true)
        } else {
            isPlaying = false
            Task { await sendHeartbeat(completed: false) }
        }
        updateNowPlaying()
    }

    private func resetPlaybackState() {
        heartbeatTask?.cancel()
        renewalTask?.cancel()
        heartbeatTask = nil
        renewalTask = nil
        playbackToken = nil
        playbackSessionID = nil
        currentPlayback = nil
        currentTrack = nil
        currentTrackID = nil
        position = 0
        isPlaying = false
    }

    deinit {
        heartbeatTask?.cancel()
        renewalTask?.cancel()
        if let timeObserver, let player {
            player.removeTimeObserver(timeObserver)
        }
        for token in notificationTokens {
            NotificationCenter.default.removeObserver(token)
        }
        player?.pause()
    }
}

private func formatDuration(_ seconds: Double) -> String {
    guard seconds.isFinite, seconds >= 0 else { return "--:--" }
    let totalSeconds = Int(seconds.rounded())
    return String(format: "%d:%02d", totalSeconds / 60, totalSeconds % 60)
}
