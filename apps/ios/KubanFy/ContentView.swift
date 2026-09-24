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
    private var player: AVPlayer?
    private var timeObserver: Any?
    private var currentTrack: DiscoveryHome.Track?
    private var currentPlayback: PlaybackResponse?

    init() {
        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playback, mode: .default, options: [])
        try? session.setActive(true)

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleInterruption(_:)),
            name: AVAudioSession.interruptionNotification,
            object: session
        )

        let commands = MPRemoteCommandCenter.shared()
        commands.playCommand.addTarget { [weak self] _ in
            self?.player?.play()
            self?.isPlaying = true
            return .success
        }
        commands.pauseCommand.addTarget { [weak self] _ in
            self?.player?.pause()
            self?.isPlaying = false
            return .success
        }
    }

    func toggle(track: DiscoveryHome.Track) async {
        errorMessage = nil
        if currentTrackID == track.id {
            if isPlaying {
                player?.pause()
                isPlaying = false
            } else {
                player?.play()
                isPlaying = true
            }
            return
        }
        do {
            let playback = try await APIClient.shared.playback(trackId: track.id, quality: "low")
            player?.pause()
            player = AVPlayer(url: playback.url)
            currentTrack = track
            currentPlayback = playback
            currentTrackID = track.id
            isPlaying = true
            updateNowPlaying()
            player?.play()
        } catch {
            currentTrackID = nil
            isPlaying = false
            errorMessage = error.localizedDescription
        }
    }

    private func updateNowPlaying() {
        guard let track = currentTrack, let player else { return }
        var info: [String: Any] = [
            MPMediaItemPropertyTitle: track.title,
            MPNowPlayingInfoPropertyPlaybackRate: player.rate
        ]
        if let duration = track.duration {
            info[MPMediaItemPropertyPlaybackDuration] = duration
        }
        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
    }

    @objc private func handleInterruption(_ notification: Notification) {
        guard let typeValue = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
              let type = AVAudioSession.InterruptionType(rawValue: typeValue) else { return }
        if type == .ended {
            try? AVAudioSession.sharedInstance().setActive(true)
        } else {
            isPlaying = false
        }
    }

    deinit {
        if let timeObserver { player?.removeTimeObserver(timeObserver) }
        NotificationCenter.default.removeObserver(self)
        MPRemoteCommandCenter.shared().playCommand.removeTarget(self)
        MPRemoteCommandCenter.shared().pauseCommand.removeTarget(self)
        player?.pause()
    }
}

private func formatDuration(_ seconds: Double) -> String {
    guard seconds.isFinite, seconds >= 0 else { return "--:--" }
    let totalSeconds = Int(seconds.rounded())
    return String(format: "%d:%02d", totalSeconds / 60, totalSeconds % 60)
}
