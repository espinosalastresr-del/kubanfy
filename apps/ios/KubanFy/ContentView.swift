import SwiftUI

struct ContentView: View {
    let sections = ["Inicio", "Buscar", "Biblioteca", "Playlists", "Artista", "Administración"]

    var body: some View {
        NavigationStack {
            List(sections, id: \.self) { section in
                NavigationLink(section) { Text(section).navigationTitle(section) }
            }
            .navigationTitle("KubanFy")
            .safeAreaInset(edge: .bottom) {
                Text("Música cubana · offline-first · nativo").font(.footnote).padding(.vertical, 8)
            }
        }
    }
}
