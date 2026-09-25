import SwiftUI
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
    @State private var showPlayer = false
    @State private var isRefreshing = false

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
                    VStack(alignment: .leading, spacing: 22) {
                        HStack(spacing: 10) {
                            NavigationLink { SearchView(audioPlayer: audioPlayer) } label: {
                                topAction("magnifyingglass", "Buscar")
                            }
                            quickTopLink("Biblioteca", "rectangle.stack")
                            quickTopLink("Playlists", "music.note.list")
                            Spacer()
                        }
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
                                        HStack(alignment: .top, spacing: 8) {
                                            NavigationLink {
                                                TrackDetailView(track: track, audioPlayer: audioPlayer)
                                            } label: {
                                                VStack(alignment: .leading, spacing: 8) {
                                                    RoundedRectangle(cornerRadius: 14)
                                                        .fill(LinearGradient(colors: [Color.green.opacity(0.75), Color.white.opacity(0.08)], startPoint: .topLeading, endPoint: .bottomTrailing))
                                                        .frame(width: 150, height: 150)
                                                        .overlay(Image(systemName: "music.note").font(.system(size: 42)).foregroundStyle(.white.opacity(0.9)))
                                                    Text(track.title).font(.subheadline.weight(.semibold)).lineLimit(2).frame(width: 150, alignment: .leading)
                                                    if let duration = track.duration { Text(formatDuration(duration)).font(.caption).foregroundStyle(.white.opacity(0.4)) }
                                                }
                                            }
                                            .buttonStyle(.plain)
                                            Button { Task { await audioPlayer.toggle(track: track) } } label: {
                                                ZStack {
                                                    Circle().fill(Color.green)
                                                    if audioPlayer.isLoading && audioPlayer.currentTrackID == track.id {
                                                        ProgressView().tint(.black)
                                                    } else {
                                                        Image(systemName: audioPlayer.currentTrackID == track.id && audioPlayer.isPlaying ? "pause.fill" : "play.fill")
                                                            .font(.system(size: 17, weight: .bold)).foregroundStyle(.black)
                                                    }
                                                }
                                                .frame(width: 42, height: 42)
                                            }
                                            .buttonStyle(.plain)
                                            .padding(.top, 142)
                                        }
                                    }
                                }
                            }
                            Text("Tendencias").font(.title3.weight(.bold)).padding(.top, 2)
                            ForEach(discovery.trending.prefix(5), id: \.rank) { item in
                                let trackID = item.trackId
                                if let title = item.title {
                                    NavigationLink {
                                        TrackDetailView(track: .init(id: trackID, title: title, duration: nil), audioPlayer: audioPlayer)
                                    } label: {
                                        HStack(spacing: 14) {
                                            Text(String(item.rank)).font(.headline.monospacedDigit()).foregroundStyle(.white.opacity(0.35)).frame(width: 24)
                                            VStack(alignment: .leading) {
                                                Text(title).font(.subheadline.weight(.semibold))
                                                Text("\(item.metrics["plays"] ?? 0) reproducciones").font(.caption).foregroundStyle(.white.opacity(0.4))
                                            }
                                            Spacer()
                                            Image(systemName: "chevron.right").foregroundStyle(.white.opacity(0.25))
                                        }.padding(.vertical, 7)
                                    }.buttonStyle(.plain)
                                }
                            }
                        } else {
                            ProgressView("Cargando tu inicio…").tint(.green).frame(maxWidth: .infinity).padding(.vertical, 50)
                        }

                        if audioPlayer.currentTrackID != nil {
                            MiniPlayer(audioPlayer: audioPlayer) { showPlayer = true }
                        }

                        if let playbackError = audioPlayer.errorMessage {
                            HStack(alignment: .top, spacing: 10) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                Text(playbackError)
                                    .font(.footnote)
                                    .foregroundStyle(.white.opacity(0.85))
                            }
                            .foregroundStyle(.red)
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.red.opacity(0.10))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        }

                        if context?.isArtist == true {
                            quickAction("person.crop.rectangle.stack", "Panel de artista")
                        }
                    }.padding(20)
                }
                .refreshable {
                    await refreshDiscovery()
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showPlayer) {
                PlayerView(audioPlayer: audioPlayer)
            }
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

    private func refreshDiscovery() async {
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        do {
            try await APIClient.shared.refreshIfNeeded()
            discovery = try await APIClient.shared.discoveryHome()
        } catch {
            errorMessage = userFacingError(error)
        }
    }

    private func topAction(_ icon: String, _ title: String) -> some View {
        HStack(spacing: 7) {
            Image(systemName: icon).font(.subheadline.weight(.bold))
            Text(title).font(.subheadline.weight(.semibold))
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 14)
        .frame(height: 40)
        .background(Color.white.opacity(0.10))
        .clipShape(Capsule())
    }

    private func quickTopLink(_ title: String, _ icon: String) -> some View {
        Button {} label: { topAction(icon, title) }
            .buttonStyle(.plain)
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
