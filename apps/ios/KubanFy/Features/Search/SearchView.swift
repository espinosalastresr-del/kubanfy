import SwiftUI

struct SearchView: View {
    @ObservedObject var audioPlayer: AudioPlayer
    @State private var query = ""
    @State private var results: [TrackSearchResult] = []
    @State private var errorMessage: String?
    @State private var isLoading = false
    @FocusState private var searchFocused: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var selectedTrack: DiscoveryHome.Track?
    @State private var recentSearches: [String] = UserDefaults.standard.stringArray(forKey: "kubanfy.search.history") ?? []

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Text("Buscar")
                        .font(.system(size: 34, weight: .bold, design: .rounded))

                    HStack(spacing: 10) {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(.secondary)
                        TextField("Artistas, canciones o álbumes", text: $query)
                            .focused($searchFocused)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .submitLabel(.search)
                            .onSubmit { Task { await performSearch() } }
                        if !query.isEmpty {
                            Button {
                                query = ""
                                results = []
                                errorMessage = nil
                                searchFocused = true
                            } label: {
                                Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal, 14)
                    .frame(height: 48)
                    .background(Color.white.opacity(0.11))
                    .clipShape(RoundedRectangle(cornerRadius: 12))

                    if !recentSearches.isEmpty && results.isEmpty && !isLoading {
                        HStack {
                            Text("Historial").font(.title3.weight(.bold))
                            Spacer()
                            Button("Borrar") {
                                recentSearches.removeAll()
                                UserDefaults.standard.removeObject(forKey: "kubanfy.search.history")
                            }
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.green)
                        }
                        LazyVStack(spacing: 0) {
                            ForEach(recentSearches, id: \.self) { item in
                                Button {
                                    query = item
                                    searchFocused = false
                                    Task { await performSearch() }
                                } label: {
                                    HStack(spacing: 12) {
                                        Image(systemName: "clock.arrow.circlepath").foregroundStyle(.white.opacity(0.45))
                                        Text(item).font(.body).lineLimit(1)
                                        Spacer()
                                        Image(systemName: "arrow.up.left").foregroundStyle(.white.opacity(0.25))
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.vertical, 10)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }

                    if isLoading {
                        HStack(spacing: 10) {
                            ProgressView().tint(.green)
                            Text("Buscando…").foregroundStyle(.white.opacity(0.55))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                    } else if let errorMessage {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("No se pudo completar la búsqueda")
                                .font(.headline)
                            Text(errorMessage)
                                .font(.subheadline)
                                .foregroundStyle(.white.opacity(0.55))
                            Button("Reintentar") { Task { await performSearch() } }
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(.green)
                        }
                        .padding(.vertical, 8)
                    } else if results.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("¿Qué quieres escuchar?")
                                .font(.title3.weight(.bold))
                            Text("Busca una canción, un artista o un álbum en el catálogo de KubanFy.")
                                .foregroundStyle(.white.opacity(0.5))
                        }
                        .padding(.top, 8)
                    } else {
                        Text("Resultados")
                            .font(.title3.weight(.bold))
                        LazyVStack(spacing: 0) {
                            ForEach(results) { result in
                                searchRow(result)
                            }
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .padding(.bottom, 32)
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Cancelar") {
                    searchFocused = false
                    dismiss()
                }
                .foregroundStyle(.green)
            }
        }
        .task {
            searchFocused = true
        }
        .preferredColorScheme(.dark)
    }

    @ViewBuilder
    private func searchRow(_ result: TrackSearchResult) -> some View {
        HStack(spacing: 12) {
            if let trackId = result.trackId {
                NavigationLink { TrackDetailView(track: DiscoveryHome.Track(id: trackId, title: result.title, duration: result.duration), audioPlayer: audioPlayer) } label: {
                    HStack(spacing: 12) {
                        searchArtwork(result)
                        searchText(result)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            } else {
                HStack(spacing: 12) {
                    searchArtwork(result)
                    searchText(result)
                }
            }

            Spacer(minLength: 4)

            if let trackId = result.trackId {
                Button {
                    let track = DiscoveryHome.Track(
                        id: trackId,
                        title: result.title,
                        duration: result.duration
                    )
                    Task { await audioPlayer.toggle(track: track) }
                } label: {
                    ZStack {
                        Circle().fill(Color.green)
                        if audioPlayer.isLoading && audioPlayer.currentTrackID == trackId {
                            ProgressView().tint(.black)
                        } else {
                            Image(
                                systemName: audioPlayer.currentTrackID == trackId && audioPlayer.isPlaying
                                    ? "pause.fill"
                                    : "play.fill"
                            )
                            .foregroundStyle(.black)
                        }
                    }
                    .frame(width: 38, height: 38)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.vertical, 9)
    }

    private func searchArtwork(_ result: TrackSearchResult) -> some View {
        RoundedRectangle(cornerRadius: 8)
            .fill(Color.white.opacity(0.09))
            .frame(width: 56, height: 56)
            .overlay(
                Image(systemName: "music.note")
                    .foregroundStyle(.white.opacity(0.45))
            )
    }

    private func searchText(_ result: TrackSearchResult) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(result.title)
                .font(.body.weight(.semibold))
                .lineLimit(1)
            Text(result.artists.joined(separator: ", "))
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.5))
                .lineLimit(1)
            if let album = result.album {
                Text(album)
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.35))
                    .lineLimit(1)
            }
        }
    }

    private func performSearch() async {
        let value = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return }
        isLoading = true
        errorMessage = nil
        do {
            results = try await APIClient.shared.search(query: value)
            recentSearches.removeAll { $0.caseInsensitiveCompare(value) == .orderedSame }
            recentSearches.insert(value, at: 0)
            recentSearches = Array(recentSearches.prefix(8))
            UserDefaults.standard.set(recentSearches, forKey: "kubanfy.search.history")
        } catch {
            results = []
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
