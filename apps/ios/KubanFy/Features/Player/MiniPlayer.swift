import SwiftUI

private struct MiniPlayer: View {
    @ObservedObject var audioPlayer: AudioPlayer
    let onTap: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Button(action: onTap) {
                HStack(spacing: 12) {
                    RoundedRectangle(cornerRadius: 8).fill(Color.green.opacity(0.22)).frame(width: 44, height: 44)
                        .overlay(Image(systemName: "music.note").foregroundStyle(.green))
                    VStack(alignment: .leading, spacing: 3) {
                        Text(audioPlayer.currentTitle ?? "Reproduciendo").font(.subheadline.weight(.semibold)).lineLimit(1)
                        Text(audioPlayer.isPlaying ? "Reproduciendo" : "Pausado").font(.caption).foregroundStyle(.white.opacity(0.45))
                    }
                }
            }
            .buttonStyle(.plain)
            Spacer()
            Button { Task { await audioPlayer.toggleCurrent() } } label: {
                Image(systemName: audioPlayer.isPlaying ? "pause.fill" : "play.fill").font(.headline).frame(width: 40, height: 40)
            }
            .buttonStyle(.plain)
        }
        .padding(8)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}
