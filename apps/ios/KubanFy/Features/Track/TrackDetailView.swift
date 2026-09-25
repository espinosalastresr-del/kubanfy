import SwiftUI

private struct TrackDetailView: View {
    let track: DiscoveryHome.Track
    @ObservedObject var audioPlayer: AudioPlayer
    @State private var detail: TrackDetail?
    @State private var isLoading = true
    @State private var errorMessage: String?

    private var artistsText: String {
        detail?.artists.map(\.name).joined(separator: ", ") ?? "KubanFy"
    }

    private var isCurrentTrack: Bool {
        audioPlayer.currentTrackID == track.id
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            ScrollView {
                VStack(spacing: 0) {
                    artwork
                    VStack(alignment: .leading, spacing: 14) {
                        Text(detail?.title ?? track.title)
                            .font(.system(size: 28, weight: .bold))
                            .lineLimit(3)
                        HStack(spacing: 5) {
                            if detail?.artists.contains(where: { $0.verified }) == true {
                                Image(systemName: "checkmark.seal.fill").foregroundStyle(.green)
                            }
                            Text(artistsText)
                                .font(.headline)
                                .foregroundStyle(.white.opacity(0.68))
                                .lineLimit(2)
                        }
                        if let detail {
                            HStack(spacing: 8) {
                                if detail.explicit {
                                    Text("E").font(.caption.weight(.bold)).padding(4).background(Color.white.opacity(0.16)).clipShape(RoundedRectangle(cornerRadius: 4))
                                }
                                if let duration = detail.duration ?? track.duration {
                                    Text(formatDuration(duration))
                                }
                                if let date = detail.releaseDate {
                                    Text("•")
                                    Text(date.formatted(.dateTime.year().month(.abbreviated).day()))
                                }
                            }
                            .font(.caption)
                            .foregroundStyle(.white.opacity(0.45))
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 24)

                    HStack(spacing: 18) {
                        Button { Task { await audioPlayer.toggle(track: track) } } label: {
                            ZStack {
                                Circle().fill(Color.green).frame(width: 62, height: 62)
                                if audioPlayer.isLoading && isCurrentTrack {
                                    ProgressView().tint(.black)
                                } else {
                                    Image(systemName: isCurrentTrack && audioPlayer.isPlaying ? "pause.fill" : "play.fill")
                                        .font(.title2.weight(.bold)).foregroundStyle(.black)
                                }
                            }
                        }
                        .buttonStyle(.plain)
                        Button { } label: {
                            Image(systemName: "plus.circle").font(.system(size: 30))
                        }
                        Button { } label: {
                            Image(systemName: "arrow.down.circle").font(.system(size: 30))
                        }
                        Spacer()
                        Button { } label: {
                            Image(systemName: "ellipsis").font(.title2.weight(.bold))
                        }
                    }
                    .padding(.top, 24)

                    if let errorMessage {
                        Text(errorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.top, 14)
                    }
                    if audioPlayer.currentTrackID == track.id, let error = audioPlayer.errorMessage {
                        Text(error)
                            .font(.footnote)
                            .foregroundStyle(.red)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.top, 8)
                    }

                    VStack(alignment: .leading, spacing: 14) {
                        Text("Más información").font(.title3.weight(.bold))
                        infoRow("Artista", artistsText)
                        if let isrc = detail?.isrc, !isrc.isEmpty { infoRow("ISRC", isrc) }
                        if let language = detail?.language, !language.isEmpty { infoRow("Idioma", language.uppercased()) }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 34)
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 32)
            }
        }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadDetail() }
        .animation(.easeInOut(duration: 0.25), value: detail != nil)
        .preferredColorScheme(.dark)
    }

    private var artwork: some View {
        Group {
            if let artworkURL = detail?.artworkURL, let url = URL(string: artworkURL) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image): image.resizable().scaledToFill()
                    default: placeholderArtwork
                    }
                }
            } else {
                placeholderArtwork
            }
        }
        .frame(maxWidth: 360)
        .aspectRatio(1, contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .shadow(radius: 18)
        .padding(.top, 20)
    }

    private var placeholderArtwork: some View {
        RoundedRectangle(cornerRadius: 18)
            .fill(LinearGradient(colors: [Color.green.opacity(0.72), Color.white.opacity(0.08)], startPoint: .topLeading, endPoint: .bottomTrailing))
            .overlay(Image(systemName: "music.note").font(.system(size: 70)).foregroundStyle(.white.opacity(0.88)))
    }

    private func infoRow(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label).foregroundStyle(.white.opacity(0.45))
            Spacer()
            Text(value).fontWeight(.semibold).multilineTextAlignment(.trailing)
        }
    }

    private func loadDetail() async {
        do {
            detail = try await APIClient.shared.trackDetail(trackId: track.id)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
