import SwiftUI

private struct PlaylistPicker: View {
    let trackID: UUID?
    @Environment(\.dismiss) private var dismiss
    @State private var playlists: [PlaylistResponse] = []
    @State private var newName = ""
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            List {
                Section("Tus playlists") {
                    ForEach(playlists) { playlist in
                        Button(playlist.name) {
                            Task {
                                guard let trackID else { return }
                                do {
                                    try await APIClient.shared.addToPlaylist(playlistId: playlist.id, trackId: trackID)
                                    dismiss()
                                } catch { errorMessage = error.localizedDescription }
                            }
                        }
                    }
                }
                Section("Nueva playlist") {
                    HStack {
                        TextField("Nombre", text: $newName)
                        Button("Crear") {
                            Task {
                                let name = newName.trimmingCharacters(in: .whitespacesAndNewlines)
                                guard !name.isEmpty else { return }
                                do {
                                    let playlist = try await APIClient.shared.createPlaylist(name: name)
                                    if let trackID { try await APIClient.shared.addToPlaylist(playlistId: playlist.id, trackId: trackID) }
                                    dismiss()
                                } catch { errorMessage = error.localizedDescription }
                            }
                        }.disabled(newName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
                if let errorMessage { Text(errorMessage).foregroundStyle(.red) }
            }
            .navigationTitle("Agregar a playlist")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Cerrar") { dismiss() } } }
            .overlay { if isLoading { ProgressView() } }
            .task {
                do { playlists = try await APIClient.shared.listPlaylists() }
                catch { errorMessage = error.localizedDescription }
                isLoading = false
            }
        }.preferredColorScheme(.dark)
    }
}
