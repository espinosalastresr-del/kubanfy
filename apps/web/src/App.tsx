import { useEffect, useRef, useState } from "react";
import { clearTokens, login, me, searchTracks } from "./api";
import { KbyPlayer } from "./player";

export default function App() {
  const [user, setUser] = useState<unknown>(null);
  const [email, setEmail] = useState("demo@kubanfy.local");
  const [password, setPassword] = useState("DemoPass123!");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [status, setStatus] = useState("Listo");
  const player = useRef(new KbyPlayer()).current;

  useEffect(() => {
    player.onState = setStatus;
    void me().then(setUser).catch(() => {});
    return () => player.stop();
  }, [player]);

  async function doLogin() {
    try { setStatus("Iniciando sesión…"); setUser(await login(email, password)); setStatus("Conectado"); }
    catch (e) { setStatus(e instanceof Error ? e.message : "Error de login"); }
  }

  async function search() {
    try { setStatus("Buscando…"); setResults(await searchTracks(query)); setStatus("Listo"); }
    catch (e) { setStatus(e instanceof Error ? e.message : "Error de búsqueda"); }
  }

  async function play(id: string) {
    try { await player.load(id, "low"); }
    catch (e) { setStatus(e instanceof Error ? e.message : "Error de reproducción"); }
  }

  return <main>
    <header className="topbar"><strong>KubanFy</strong><span>{status}</span></header>
    {!user ? <section className="card auth">
      <h1>Música cubana, incluso con mala conexión.</h1>
      <p>Cliente web/PWA de desarrollo.</p>
      <input value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" />
      <input value={password} onChange={e => setPassword(e.target.value)} placeholder="Contraseña" type="password" />
      <button onClick={doLogin}>Entrar</button>
    </section> : <section>
      <div className="card">
        <h1>Buscar música</h1>
        <div className="search"><input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && void search()} placeholder="Artista o canción" /><button onClick={search}>Buscar</button></div>
      </div>
      <div className="results">{results.map((r) => <article className="track card" key={r.provider_track_id}>
        <div><strong>{r.title}</strong><span>{r.artists.join(", ")}</span></div>
        {r.track_id && <button onClick={() => void play(r.track_id)}>▶ Reproducir</button>}
      </article>)}</div>
      <div className="player card"><audio controls ref={el => { if (el) { /* player owns the element */ } }} /><button onClick={() => { clearTokens(); location.reload(); }}>Salir</button></div>
    </section>}
  </main>;
}
