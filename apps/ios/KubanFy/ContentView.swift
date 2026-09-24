import SwiftUI
import AVFoundation
import MediaPlayer
import UIKit

struct ContentView: View {
    @State private var email = ""
    @State private var password = ""
    @State private var showPassword = false
    @State private var user: UserResponse?
    @State private var authContext: AuthContext?
    @State private var discovery: DiscoveryHome?
    @State private var errorMessage: String?
    @State private var isLoading = false
    @State private var saveCredentials = false
    @State private var showRecoveryInfo = false
    @State private var showRegister = false
    @StateObject private var audioPlayer = AudioPlayer()

    var body: some View {
        ZStack {
            if let user {
                home(user, context: authContext, discovery: discovery)
            } else {
                login
            }
        }
        .preferredColorScheme(.dark)
        .task {
            if let savedEmail = APIClient.shared.savedEmail { email = savedEmail }
            if let savedPassword = APIClient.shared.savedPassword {
                password = savedPassword
                saveCredentials = true
            }
            await restoreSession()
        }
        .alert("Recuperar contraseña", isPresented: $showRecoveryInfo) {
            Button("OK", role: .cancel) {}
        } message: {
            Text("La recuperación todavía no está habilitada por el servidor. El enlace ya está preparado en la app y se conectará al endpoint cuando esté disponible.")
        }
    }

    private var login: some View {
        ZStack {
            LinearGradient(colors: [Color(red: 0.025, green: 0.045, blue: 0.035), .black], startPoint: .topLeading, endPoint: .bottomTrailing)
                .ignoresSafeArea()
            Circle().fill(Color.green.opacity(0.16)).frame(width: 280, height: 280).blur(radius: 70).offset(x: 150, y: -330)

            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Spacer(minLength: 54)
                    HStack(spacing: 10) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 13).fill(Color.green).frame(width: 48, height: 48)
                            Image(systemName: "music.note").font(.system(size: 24, weight: .bold)).foregroundStyle(.black)
                        }
                        Text("KubanFy").font(.system(size: 30, weight: .bold, design: .rounded))
                    }
                    Text("Tu música. Tu isla. Tu ritmo.").font(.title3.weight(.semibold)).foregroundStyle(.white.opacity(0.72)).padding(.top, 12)
                    Text("Inicia sesión para continuar").font(.subheadline).foregroundStyle(.white.opacity(0.48)).padding(.top, 5)
                    Toggle(isOn: $saveCredentials) { Text("Guardar credenciales").font(.subheadline) }
                        .tint(.green).padding(.top, 16)

                    VStack(spacing: 14) {
                        loginField("Correo electrónico", "envelope", $email)
                            .textInputAutocapitalization(.never).keyboardType(.emailAddress).autocorrectionDisabled()
                        HStack(spacing: 12) {
                            Image(systemName: "lock").foregroundStyle(.white.opacity(0.45)).frame(width: 20)
                            Group {
                                if showPassword { TextField("Contraseña", text: $password) }
                                else { SecureField("Contraseña", text: $password) }
                            }
                            .textInputAutocapitalization(.never).autocorrectionDisabled().disabled(isLoading)
                            Button { showPassword.toggle() } label: {
                                Image(systemName: showPassword ? "eye.slash" : "eye").foregroundStyle(.white.opacity(0.55)).frame(width: 32, height: 32)
                            }.disabled(isLoading)
                        }
                        .padding(.horizontal, 15).frame(height: 56).background(Color.white.opacity(0.075))
                        .overlay(RoundedRectangle(cornerRadius: 15).stroke(Color.white.opacity(0.08), lineWidth: 1))
                        .clipShape(RoundedRectangle(cornerRadius: 15))
                    }.padding(.top, 30)

                    HStack {
                        Button("Crear cuenta") { showRegister = true }
                            .font(.subheadline.weight(.bold)).foregroundStyle(Color.green).disabled(isLoading)
                        Spacer()
                        Button("¿Olvidaste tu contraseña?") { showRecoveryInfo = true }
                            .font(.subheadline.weight(.semibold)).foregroundStyle(Color.green).disabled(isLoading)
                    }.padding(.top, 14)

                    if let errorMessage {
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: "exclamationmark.triangle.fill")
                            Text(errorMessage).font(.subheadline)
                        }
                        .foregroundStyle(.red.opacity(0.95)).padding(14).frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.red.opacity(0.10)).clipShape(RoundedRectangle(cornerRadius: 14)).padding(.top, 18)
                    }

                    Button { hideKeyboard(); Task { await performLogin() } } label: {
                        HStack(spacing: 10) {
                            if isLoading { ProgressView().tint(.black); Text("Conectando…") }
                            else { Text("Iniciar sesión"); Image(systemName: "arrow.right").font(.system(size: 15, weight: .bold)) }
                        }
                        .font(.headline.weight(.bold)).foregroundStyle(.black).frame(maxWidth: .infinity).frame(height: 56)
                        .background(canSubmit ? Color.green : Color.white.opacity(0.16)).clipShape(RoundedRectangle(cornerRadius: 17))
                    }
                    .disabled(!canSubmit || isLoading).padding(.top, 24)

                    Text("La conexión al servidor es necesaria para autenticarte y cargar tu contenido.")
                        .font(.caption).foregroundStyle(.white.opacity(0.35)).multilineTextAlignment(.center)
                        .frame(maxWidth: .infinity).padding(.top, 20)
                    Spacer(minLength: 30)
                }
                .padding(.horizontal, 24).frame(maxWidth: 560).frame(maxWidth: .infinity)
            }
            .scrollDismissesKeyboard(.interactively).scrollIndicators(.hidden)
        }
        .ignoresSafeArea(.keyboard, edges: .bottom)
        .sheet(isPresented: $showRegister) {
            RegisterView { registeredEmail, registeredPassword in
                email = registeredEmail
                password = registeredPassword
                saveCredentials = true
            }
        }
    }

    private var canSubmit: Bool {
        !email.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !password.isEmpty
    }

    private func loginField(_ title: String, _ icon: String, _ text: Binding<String>) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon).foregroundStyle(.white.opacity(0.45)).frame(width: 20)
            TextField(title, text: text).disabled(isLoading)
        }
        .padding(.horizontal, 15).frame(height: 56).background(Color.white.opacity(0.075))
        .overlay(RoundedRectangle(cornerRadius: 15).stroke(Color.white.opacity(0.08), lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 15))
    }

    private func home(_ user: UserResponse, context: AuthContext?, discovery: DiscoveryHome?) -> some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()
                ScrollView {
                    VStack(alignment: .leading, spacing: 26) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Hola, \(user.displayName)").font(.title2.weight(.bold))
                                Text(discovery.map { "Descubre música en \($0.country)" } ?? "Descubre tu música")
                                    .foregroundStyle(.white.opacity(0.5))
                            }
                            Spacer()
                            Circle().fill(Color.white.opacity(0.10)).frame(width: 44, height: 44).overlay(Image(systemName: "person.fill"))
                        }
                        if let discovery {
                            Text("Nuevos lanzamientos").font(.title3.weight(.bold))
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 14) {
                                    ForEach(discovery.newReleases.prefix(12), id: \.id) { track in
                                        VStack(alignment: .leading, spacing: 8) {
                                            RoundedRectangle(cornerRadius: 14)
                                                .fill(LinearGradient(colors: [Color.green.opacity(0.75), Color.white.opacity(0.08)], startPoint: .topLeading, endPoint: .bottomTrailing))
                                                .frame(width: 150, height: 150)
                                                .overlay(Image(systemName: "music.note").font(.system(size: 42)).foregroundStyle(.white.opacity(0.9)))
                                                .overlay(alignment: .bottomTrailing) {
                                                    Button { Task { await audioPlayer.toggle(track: track) } } label: {
                                                        Image(systemName: audioPlayer.currentTrackID == track.id && audioPlayer.isPlaying ? "pause.fill" : "play.fill")
                                                            .font(.system(size: 17, weight: .bold)).foregroundStyle(.black).frame(width: 42, height: 42)
                                                            .background(Color.green).clipShape(Circle())
                                                    }.padding(8)
                                                }
                                            Text(track.title).font(.subheadline.weight(.semibold)).lineLimit(2).frame(width: 150, alignment: .leading)
                                            if let duration = track.duration { Text(formatDuration(duration)).font(.caption).foregroundStyle(.white.opacity(0.4)) }
                                        }
                                    }
                                }
                            }
                            Text("Tendencias").font(.title3.weight(.bold)).padding(.top, 2)
                            ForEach(discovery.trending.prefix(5), id: \.rank) { item in
                                HStack(spacing: 14) {
                                    Text(String(item.rank)).font(.headline.monospacedDigit()).foregroundStyle(.white.opacity(0.35)).frame(width: 24)
                                    VStack(alignment: .leading) {
                                        Text(item.title ?? "Sin título").font(.subheadline.weight(.semibold))
                                        Text("\(item.metrics["plays"] ?? 0) reproducciones").font(.caption).foregroundStyle(.white.opacity(0.4))
                                    }
                                    Spacer()
                                    Image(systemName: "chevron.right").foregroundStyle(.white.opacity(0.25))
                                }.padding(.vertical, 7)
                            }
                        } else {
                            ProgressView("Cargando tu inicio…").tint(.green).frame(maxWidth: .infinity).padding(.vertical, 50)
                        }

                        HStack(spacing: 10) {
                            NavigationLink { SearchView() } label: { quickAction("magnifyingglass", "Buscar") }
                            quickAction("rectangle.stack", "Biblioteca")
                            quickAction("music.note.list", "Playlists")
                        }
                        if context?.isArtist == true { quickAction("person.crop.rectangle.stack", "Panel de artista") }
                    }.padding(20)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Text("KubanFy").font(.headline.weight(.bold)) }
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button("Cerrar sesión", role: .destructive) {
                            APIClient.shared.logout(); self.user = nil; authContext = nil; self.discovery = nil
                        }
                    } label: { Image(systemName: "ellipsis") }
                }
            }
        }
    }

    private func quickAction(_ icon: String, _ title: String) -> some View {
        HStack(spacing: 8) { Image(systemName: icon); Text(title).font(.subheadline.weight(.semibold)) }
            .foregroundStyle(.white).padding(.horizontal, 13).frame(height: 40)
            .background(Color.white.opacity(0.08)).clipShape(Capsule())
    }

    private func restoreSession() async {
        guard APIClient.shared.hasStoredSession else { return }
        if let cachedUser = APIClient.shared.cachedUser() {
            user = cachedUser
        }
        do {
            try await APIClient.shared.refreshIfNeeded()
            let restoredUser = try await APIClient.shared.me()
            user = restoredUser
            APIClient.shared.cacheUser(restoredUser)
            authContext = try await APIClient.shared.context()
            discovery = try await APIClient.shared.discoveryHome()
        } catch {
            // Network failure must not erase the local authenticated shell.
        }
    }

    private func performLogin() async {
        hideKeyboard()
        isLoading = true; errorMessage = nil
        defer { isLoading = false }
        do {
            let response = try await APIClient.shared.login(email: email, password: password, saveCredentials: saveCredentials)
            user = response.user
            APIClient.shared.cacheUser(response.user)
            authContext = try await APIClient.shared.context()
            discovery = try await APIClient.shared.discoveryHome()
        } catch {
            errorMessage = userFacingError(error)
        }
    }

    private func userFacingError(_ error: Error) -> String {
        if let apiError = error as? APIError {
            switch apiError {
            case .network: return "No se pudo conectar con KubanFy. El servidor puede estar apagado o no disponible. Comprueba tu conexión e inténtalo de nuevo."
            case let .http(code, message):
                if code == 401 { return "Correo o contraseña incorrectos." }
                if code == 429 { return "Demasiados intentos. Espera un momento y vuelve a intentarlo." }
                return "\(message) (HTTP \(code))"
            default: return apiError.localizedDescription
            }
        }
        if let urlError = error as? URLError {
            switch urlError.code {
            case .timedOut, .cannotFindHost, .cannotConnectToHost, .networkConnectionLost, .notConnectedToInternet:
                return "No se pudo conectar con KubanFy. El servidor puede estar apagado o no disponible."
            default: break
            }
        }
        return error.localizedDescription
    }

    private func hideKeyboard() {
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }
}

private struct RegisterView: View {
    @Environment(\.dismiss) private var dismiss
    private let onRegistered: (String, String) -> Void

    init(onRegistered: @escaping (String, String) -> Void) {
        self.onRegistered = onRegistered
    }
    @State private var displayName = ""
    @State private var email = ""
    @State private var password = ""
    @State private var confirmPassword = ""
    @State private var showPassword = false
    @State private var showConfirmPassword = false
    @State private var errorMessage: String?
    @State private var successMessage: String?
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            ZStack {
                LinearGradient(colors: [Color(red: 0.025, green: 0.045, blue: 0.035), .black], startPoint: .topLeading, endPoint: .bottomTrailing).ignoresSafeArea()
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        HStack(spacing: 10) {
                            ZStack {
                                RoundedRectangle(cornerRadius: 13).fill(Color.green).frame(width: 48, height: 48)
                                Image(systemName: "person.badge.plus").font(.system(size: 23, weight: .bold)).foregroundStyle(.black)
                            }
                            Text("Crear cuenta").font(.system(size: 30, weight: .bold, design: .rounded))
                        }
                        Text("Únete a KubanFy").font(.title3.weight(.semibold)).foregroundStyle(.white.opacity(0.72)).padding(.top, 12)
                        Text("Crea tu cuenta para descubrir y escuchar música.").font(.subheadline).foregroundStyle(.white.opacity(0.48)).padding(.top, 5)
                        VStack(spacing: 14) {
                            registerField("Nombre", "person", $displayName)
                            registerField("Correo electrónico", "envelope", $email).textInputAutocapitalization(.never).keyboardType(.emailAddress).autocorrectionDisabled()
                            passwordField("Contraseña", $password, show: $showPassword)
                            passwordField("Repite la contraseña", $confirmPassword, show: $showConfirmPassword)
                        }.padding(.top, 30)
                        Text("Mínimo 8 caracteres e incluye letras y números o símbolos.").font(.caption).foregroundStyle(.white.opacity(0.38)).padding(.top, 12)
                        if let errorMessage {
                            HStack(alignment: .top, spacing: 10) { Image(systemName: "exclamationmark.triangle.fill"); Text(errorMessage).font(.subheadline) }
                                .foregroundStyle(.red.opacity(0.95)).padding(14).frame(maxWidth: .infinity, alignment: .leading)
                                .background(Color.red.opacity(0.10)).clipShape(RoundedRectangle(cornerRadius: 14)).padding(.top, 18)
                        }
                        if let successMessage {
                            HStack(alignment: .top, spacing: 10) { Image(systemName: "checkmark.circle.fill"); Text(successMessage).font(.subheadline) }
                                .foregroundStyle(Color.green).padding(14).frame(maxWidth: .infinity, alignment: .leading)
                                .background(Color.green.opacity(0.10)).clipShape(RoundedRectangle(cornerRadius: 14)).padding(.top, 18)
                        }
                        Button { hideKeyboard(); Task { await performRegister() } } label: {
                            HStack(spacing: 10) {
                                if isLoading { ProgressView().tint(.black); Text("Creando cuenta…") }
                                else { Text("Crear cuenta"); Image(systemName: "arrow.right").font(.system(size: 15, weight: .bold)) }
                            }.font(.headline.weight(.bold)).foregroundStyle(.black).frame(maxWidth: .infinity).frame(height: 56)
                                .background(canSubmit ? Color.green : Color.white.opacity(0.16)).clipShape(RoundedRectangle(cornerRadius: 17))
                        }.disabled(!canSubmit || isLoading).padding(.top, 24)
                        Text("El país y el idioma usan los valores predeterminados del servidor cuando no se especifican.")
                            .font(.caption).foregroundStyle(.white.opacity(0.30)).multilineTextAlignment(.center).frame(maxWidth: .infinity).padding(.top, 20)
                    }.padding(.horizontal, 24).padding(.bottom, 30).frame(maxWidth: 560).frame(maxWidth: .infinity)
                }.scrollDismissesKeyboard(.interactively).scrollIndicators(.hidden)
            }
            .toolbar { ToolbarItem(placement: .topBarLeading) { Button("Cancelar") { hideKeyboard(); dismiss() }.disabled(isLoading) } }
        }.preferredColorScheme(.dark)
    }

    private var canSubmit: Bool {
        let name = displayName.trimmingCharacters(in: .whitespacesAndNewlines)
        let mail = email.trimmingCharacters(in: .whitespacesAndNewlines)
        return name.count >= 1 && name.count <= 120 && mail.contains("@") && password.count >= 8 && password == confirmPassword
    }

    private func registerField(_ title: String, _ icon: String, _ text: Binding<String>) -> some View {
        HStack(spacing: 12) { Image(systemName: icon).foregroundStyle(.white.opacity(0.45)).frame(width: 20); TextField(title, text: text).disabled(isLoading) }
            .padding(.horizontal, 15).frame(height: 56).background(Color.white.opacity(0.075))
            .overlay(RoundedRectangle(cornerRadius: 15).stroke(Color.white.opacity(0.08), lineWidth: 1)).clipShape(RoundedRectangle(cornerRadius: 15))
    }

    private func passwordField(_ title: String, _ text: Binding<String>, show: Binding<Bool>) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "lock").foregroundStyle(.white.opacity(0.45)).frame(width: 20)
            Group { if show.wrappedValue { TextField(title, text: text) } else { SecureField(title, text: text) } }
                .textInputAutocapitalization(.never).autocorrectionDisabled().disabled(isLoading)
            Button { show.wrappedValue.toggle() } label: { Image(systemName: show.wrappedValue ? "eye.slash" : "eye").foregroundStyle(.white.opacity(0.55)).frame(width: 32, height: 32) }.disabled(isLoading)
        }.padding(.horizontal, 15).frame(height: 56).background(Color.white.opacity(0.075))
            .overlay(RoundedRectangle(cornerRadius: 15).stroke(Color.white.opacity(0.08), lineWidth: 1)).clipShape(RoundedRectangle(cornerRadius: 15))
    }

    private func performRegister() async {
        hideKeyboard(); isLoading = true; errorMessage = nil; successMessage = nil
        defer { isLoading = false }
        do {
            _ = try await APIClient.shared.register(email: email, password: password, displayName: displayName)
            successMessage = "Cuenta creada correctamente. Ya puedes iniciar sesión."
            onRegistered(email, password)
            password = ""; confirmPassword = ""
        } catch { errorMessage = registrationError(error) }
    }

    private func registrationError(_ error: Error) -> String {
        if let apiError = error as? APIError {
            switch apiError {
            case .network: return "No se pudo conectar con KubanFy. El servidor puede estar apagado o no disponible."
            case let .http(code, message):
                if code == 409 { return "Ese correo ya está registrado." }
                if code == 422 { return "Revisa el correo, el nombre y los requisitos de la contraseña." }
                if code == 429 { return "Demasiados intentos. Espera un momento y vuelve a intentarlo." }
                return "\(message) (HTTP \(code))"
            default: return apiError.localizedDescription
            }
        }
        return error.localizedDescription
    }

    private func hideKeyboard() { UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil) }
}

private struct SearchView: View {
    @State private var query = ""
    @State private var results: [TrackSearchResult] = []
    @State private var errorMessage: String?
    @State private var isLoading = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            List {
                Section {
                    TextField("Canción o artista", text: $query).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button(isLoading ? "Buscando…" : "Buscar") { Task { await performSearch() } }
                        .disabled(isLoading || query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                if let errorMessage { Section { Text(errorMessage).foregroundStyle(.red) } }
                Section("Resultados") {
                    if results.isEmpty && !isLoading { Text("Busca una canción o artista.").foregroundStyle(.secondary) }
                    ForEach(results) { track in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(track.title).font(.headline)
                            Text(track.artists.joined(separator: ", ")).foregroundStyle(.secondary)
                            if let album = track.album { Text(album).font(.caption).foregroundStyle(.secondary) }
                        }.padding(.vertical, 4)
                    }
                }
            }.scrollContentBackground(.hidden)
        }
        .navigationTitle("Buscar").preferredColorScheme(.dark)
    }

    private func performSearch() async {
        isLoading = true; errorMessage = nil
        defer { isLoading = false }
        do { results = try await APIClient.shared.search(query: query) }
        catch { errorMessage = error.localizedDescription; results = [] }
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
                    self.replaceItem(with: playback.url, position: savedPosition)
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
        recoveryTask?.cancel()
        heartbeatTask = nil
        renewalTask = nil
        playbackToken = nil
        playbackSessionID = nil
        currentPlayback = nil
        currentTrack = nil
        currentTrackID = nil
        position = 0
        isPlaying = false
        playbackGeneration = UUID()
    }

    deinit {
        heartbeatTask?.cancel()
        renewalTask?.cancel()
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

private func formatDuration(_ seconds: Double) -> String {
    guard seconds.isFinite, seconds >= 0 else { return "--:--" }
    let totalSeconds = Int(seconds.rounded())
    return String(format: "%d:%02d", totalSeconds / 60, totalSeconds % 60)
}
