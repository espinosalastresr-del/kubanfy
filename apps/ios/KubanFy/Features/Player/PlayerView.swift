import SwiftUI

struct PlayerView: View {
    @ObservedObject var audioPlayer: AudioPlayer
    @Environment(\.dismiss) private var dismiss
    @State private var isLiked = false
    @State private var showPlaylists = false
    @State private var showMore = false
    @State private var isDownloading = false
    @State private var actionMessage: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 22) {
                    RoundedRectangle(cornerRadius: 28)
                        .fill(LinearGradient(colors: [Color.green.opacity(0.72), Color.white.opacity(0.08)], startPoint: .topLeading, endPoint: .bottomTrailing))
                        .frame(maxWidth: 330).aspectRatio(1, contentMode: .fit)
                        .overlay(Image(systemName: "music.note").font(.system(size: 72)).foregroundStyle(.white.opacity(0.9)))
                        .padding(.top, 8)
                    VStack(spacing: 6) {
                        Text(audioPlayer.currentTitle ?? "Sin reproducción").font(.title2.weight(.bold)).lineLimit(2).multilineTextAlignment(.center)
                        Text("KubanFy").foregroundStyle(.white.opacity(0.45))
                    }
                    VStack(spacing: 8) {
                        Slider(value: Binding(get: { audioPlayer.position }, set: { audioPlayer.seek(to: $0) }), in: 0...max(audioPlayer.duration, 1))
                        HStack { Text(formatDuration(audioPlayer.position)); Spacer(); Text(formatDuration(audioPlayer.duration)) }.font(.caption).foregroundStyle(.white.opacity(0.4))
                    }
                    HStack(spacing: 34) {
                        Button { audioPlayer.toggleShuffle() } label: {
                            Image(systemName: "shuffle").font(.title3).foregroundStyle(audioPlayer.isShuffled ? .green : .white)
                        }
                        Button { audioPlayer.seek(to: max(0, audioPlayer.position - 10)) } label: { Image(systemName: "gobackward.10").font(.title2) }
                        Button { Task { await audioPlayer.toggleCurrent() } } label: { Image(systemName: audioPlayer.isPlaying ? "pause.circle.fill" : "play.circle.fill").font(.system(size: 62)) }
                        Button { audioPlayer.seek(to: audioPlayer.position + 10) } label: { Image(systemName: "goforward.10").font(.title2) }
                        Button { audioPlayer.cycleRepeat() } label: {
                            Image(systemName: audioPlayer.repeatMode == .one ? "repeat.1" : "repeat").font(.title3).foregroundStyle(audioPlayer.repeatMode == .off ? .white : .green)
                        }
                    }
                    HStack(spacing: 30) {
                        Button {
                            Task {
                                guard let id = audioPlayer.currentTrackID else { return }
                                do {
                                    if isLiked { try await APIClient.shared.removeFavorite(trackId: id) }
                                    else { _ = try await APIClient.shared.addFavorite(trackId: id) }
                                    isLiked.toggle()
                                    actionMessage = isLiked ? "Añadida a Me gusta" : "Eliminada de Me gusta"
                                } catch { actionMessage = error.localizedDescription }
                            }
                        } label: { Image(systemName: isLiked ? "heart.fill" : "heart").font(.title2).foregroundStyle(isLiked ? .green : .white) }
                        Button { showPlaylists = true } label: { Image(systemName: "plus.circle").font(.title2) }
                        Button {
                            Task {
                                guard let id = audioPlayer.currentTrackID else { return }
                                isDownloading = true
                                defer { isDownloading = false }
                                do {
                                    let ticket = try await APIClient.shared.issueDownloadTicket(trackId: id)
                                    let playback = try await APIClient.shared.playback(trackId: id, quality: "low")
                                    let localURL = try await APIClient.shared.fetchAndDecryptKBY(playback)
                                    let downloads = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("Downloads", isDirectory: true)
                                    try FileManager.default.createDirectory(at: downloads, withIntermediateDirectories: true)
                                    let destination = downloads.appendingPathComponent("\(id.uuidString).kby")
                                    try? FileManager.default.removeItem(at: destination)
                                    try FileManager.default.copyItem(at: localURL, to: destination)
                                    let size = (try FileManager.default.attributesOfItem(atPath: destination.path)[.size] as? NSNumber)?.intValue ?? 0
                                    try await APIClient.shared.completeDownload(ticket: ticket.downloadTicket, sizeBytes: size)
                                    actionMessage = "Descarga completada"
                                } catch { actionMessage = error.localizedDescription }
                            }
                        } label: {
                            if isDownloading { ProgressView().tint(.green) } else { Image(systemName: "arrow.down.circle").font(.title2) }
                        }
                        Button { showMore = true } label: { Image(systemName: "ellipsis.circle").font(.title2) }
                    }
                    if let message = actionMessage { Text(message).font(.footnote).foregroundStyle(.white.opacity(0.65)).multilineTextAlignment(.center) }
                    if let error = audioPlayer.errorMessage { Text(error).font(.caption).foregroundStyle(.red).multilineTextAlignment(.center) }
                }.padding(24)
            }
            .background(Color.black.ignoresSafeArea())
            .navigationTitle(audioPlayer.currentTitle ?? "Reproduciendo")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { dismiss() } label: { Image(systemName: "chevron.down") }
                }
            }
            .sheet(isPresented: $showPlaylists) { PlaylistPicker(trackID: audioPlayer.currentTrackID) }
            .confirmationDialog("Más opciones", isPresented: $showMore, titleVisibility: .visible) {
                Button("Compartir") { }
                Button("Cancelar", role: .cancel) { }
            }
        }.preferredColorScheme(.dark)
    }
}
