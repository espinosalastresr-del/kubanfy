import SwiftUI

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
