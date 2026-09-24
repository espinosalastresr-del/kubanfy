import SwiftUI

struct ContentView: View {
    @State private var email = ""
    @State private var password = ""
    @State private var user: UserResponse?
    @State private var errorMessage: String?
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            Group {
                if let user {
                    home(user)
                } else {
                    login
                }
            }
            .navigationTitle("KubanFy")
        }
        .task {
            guard user == nil else { return }
            user = try? await APIClient.shared.me()
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

    private func home(_ user: UserResponse) -> some View {
        List {
            Section("Cuenta") {
                Text("Hola, \(user.displayName)")
                Text("País: \(user.country)")
                    .foregroundStyle(.secondary)
            }
            Section("KubanFy") {
                ForEach(["Inicio", "Buscar", "Biblioteca", "Playlists", "Artista", "Administración"], id: \.self) {
                    Text($0)
                }
            }
            Section {
                Button("Cerrar sesión", role: .destructive) {
                    APIClient.shared.logout()
                    self.user = nil
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
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
