"use client";

import { useEffect, useMemo, useState } from "react";

type Track = { id: string; title: string; artist: string; cover: string; tone: string; country: string; duration: string };
type Tab = "inicio" | "buscar" | "biblioteca" | "perfil";

const tracks: Track[] = [
  { id: "t1", title: "La vida es un carnaval", artist: "Celia Cruz", cover: "https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=640&q=85", tone: "coral", country: "CU", duration: "4:38" },
  { id: "t2", title: "Chan Chan", artist: "Buena Vista Social Club", cover: "https://images.unsplash.com/photo-1510915361894-db8b60106cb1?auto=format&fit=crop&w=640&q=85", tone: "gold", country: "CU", duration: "4:16" },
  { id: "t3", title: "Bailando", artist: "Enrique Iglesias", cover: "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=640&q=85", tone: "violet", country: "ES", duration: "4:03" },
  { id: "t4", title: "Vivir mi vida", artist: "Marc Anthony", cover: "https://images.unsplash.com/photo-1501386761578-eac5c94b800a?auto=format&fit=crop&w=640&q=85", tone: "blue", country: "US", duration: "4:12" },
  { id: "t5", title: "El cuarto de Tula", artist: "Buena Vista Social Club", cover: "https://images.unsplash.com/photo-1524368535925-5b5e00ddc76b?auto=format&fit=crop&w=640&q=85", tone: "green", country: "CU", duration: "7:25" },
  { id: "t6", title: "Despechá", artist: "Rosalía", cover: "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=640&q=85", tone: "pink", country: "ES", duration: "2:37" },
  { id: "t7", title: "Todo de ti", artist: "Rauw Alejandro", cover: "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&w=640&q=85", tone: "orange", country: "PR", duration: "3:19" },
  { id: "t8", title: "Patria y vida", artist: "Yotuel & friends", cover: "https://images.unsplash.com/photo-1506157786151-b8491531f063?auto=format&fit=crop&w=640&q=85", tone: "teal", country: "CU", duration: "4:05" },
];

const nav = [
  { id: "inicio" as Tab, label: "Inicio", glyph: "⌂" },
  { id: "buscar" as Tab, label: "Buscar", glyph: "⌕" },
  { id: "biblioteca" as Tab, label: "Tu biblioteca", glyph: "▤" },
  { id: "perfil" as Tab, label: "Perfil", glyph: "◉" },
];

function Cover({ track, size = "medium" }: { track: Track; size?: "small" | "medium" | "large" }) {
  return <div className={`cover cover-${size} tone-${track.tone}`} style={{ backgroundImage: `linear-gradient(145deg, rgba(9,12,20,.04), rgba(9,12,20,.4)), url("${track.cover}")` }} role="img" aria-label={`Portada de ${track.title}`} />;
}

function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    search: "M21 21l-4.3-4.3M10.8 18a7.2 7.2 0 1 1 0-14.4 7.2 7.2 0 0 1 0 14.4Z",
    play: "m8 5 12 7-12 7V5Z",
    pause: "M8 5h3v14H8zM15 5h3v14h-3z",
    heart: "M20.8 8.8c0 5.2-8.8 10-8.8 10S3.2 14 3.2 8.8A4.7 4.7 0 0 1 12 6.1a4.7 4.7 0 0 1 8.8 2.7Z",
    next: "m5 5 10 7-10 7V5Zm13 0v14",
    previous: "m19 5-10 7 10 7V5ZM6 5v14",
    shuffle: "m3 7h3c5 0 7 10 12 10h3m-3-3 3 3-3 3M3 17h3c2 0 3.3-2.2 4.7-4.7M14 7h4c1 0 2 1 3 2m-3-5 3 3-3 3",
    repeat: "m17 2 4 4-4 4M3 11V8a2 2 0 0 1 2-2h16M7 22l-4-4 4-4m14-1v3a2 2 0 0 1-2 2H3",
    more: "M5 12h.01M12 12h.01M19 12h.01",
    close: "m18 6-12 12M6 6l12 12",
    arrow: "M5 12h14m-6-6 6 6-6 6",
  };
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true"><path d={paths[name] || paths.more} /></svg>;
}

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("inicio");
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState("CU");
  const [favorites, setFavorites] = useState<string[]>(["t2"]);
  const [current, setCurrent] = useState<Track>(tracks[1]);
  const [playing, setPlaying] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const userName = "Tu universo musical";

  useEffect(() => {
    try {
      const saved = localStorage.getItem("kubanfy-dashboard-v1");
      if (saved) {
        const data = JSON.parse(saved);
        if (data.country) setCountry(data.country);
        if (Array.isArray(data.favorites)) setFavorites(data.favorites);
      }
    } catch { /* Keep a clean default if local storage is unavailable. */ }
  }, []);

  useEffect(() => {
    try { localStorage.setItem("kubanfy-dashboard-v1", JSON.stringify({ country, favorites })); } catch { /* Private browsing may block storage. */ }
  }, [country, favorites]);

  const filtered = useMemo(() => {
    const value = query.trim().toLowerCase();
    return tracks.filter((track) => !value || `${track.title} ${track.artist}`.toLowerCase().includes(value));
  }, [query]);

  const toggleFavorite = (id: string) => setFavorites((old) => old.includes(id) ? old.filter((item) => item !== id) : [...old, id]);
  const playTrack = (track: Track) => { setCurrent(track); setPlaying(true); };
  const countryName = country === "CU" ? "Cuba" : country === "US" ? "Estados Unidos" : country === "ES" ? "España" : country === "PR" ? "Puerto Rico" : "México";

  async function logout() {
    try {
      await fetch("https://kubanfy-auth-v2.globumlatinmusic.workers.dev/api/v1/auth/logout", { method: "POST", credentials: "include" });
    } catch { /* The session may already have expired. */ }
    window.location.href = "https://kubanfy-auth-web.globumlatinmusic.workers.dev/login";
  }

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(e) => { e.preventDefault(); setTab("inicio"); }}>
          <span className="brand-mark">K<span>F</span></span><span>Kuban<span className="brand-accent">Fy</span><small>SONIDO SIN FRONTERAS</small></span>
        </a>
        <div className="side-label">TU ESPACIO</div>
        <nav className="side-nav" aria-label="Navegación principal">
          {nav.map((item) => <button key={item.id} className={tab === item.id ? "nav-item active" : "nav-item"} onClick={() => { setTab(item.id); setProfileOpen(false); }}><span className="nav-glyph">{item.glyph}</span>{item.label}</button>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note"><span className="note-orb">✳</span><p>La música que llevas<br/>también es tu hogar.</p></div>
          <button className="account-button" onClick={() => setProfileOpen(!profileOpen)}><span className="avatar">K</span><span className="account-copy"><strong>Cuenta de usuario</strong><small>Plan gratuito</small></span><span className="chevron">⌄</span></button>
          {profileOpen && <div className="account-popover"><button onClick={() => setTab("perfil")}>Ver perfil</button><button onClick={logout}>Cerrar sesión</button></div>}
        </div>
      </aside>

      <section className="main-column">
        <header className="topbar">
          <div className="mobile-brand"><span className="brand-mark">K<span>F</span></span><strong>Kuban<span className="brand-accent">Fy</span></strong></div>
          <label className="search-box"><Icon name="search"/><input value={query} onChange={(e) => { setQuery(e.target.value); if (e.target.value) setTab("buscar"); }} placeholder="Busca canciones, artistas, álbumes..." aria-label="Buscar música"/><kbd>⌘ K</kbd></label>
          <div className="top-actions"><span className="country-label">Música de</span><select aria-label="País de contenido" value={country} onChange={(e) => setCountry(e.target.value)}><option value="CU">🇨🇺 Cuba</option><option value="US">🇺🇸 Estados Unidos</option><option value="ES">🇪🇸 España</option><option value="PR">🇵🇷 Puerto Rico</option><option value="MX">🇲🇽 México</option></select><button className="top-avatar" aria-label="Abrir perfil" onClick={() => setTab("perfil")}>K</button></div>
        </header>

        <div className="content">
          {tab === "inicio" && <>
            <section className="welcome-row"><div><div className="eyebrow"><span className="eyebrow-dot"/> TU PUNTO DE ENCUENTRO</div><h1>Hola, <em>bienvenido.</em></h1><p>Tu cultura. Tu sonido. Tu lugar.</p></div><div className="welcome-stamp">K<span>F</span><i>✳</i></div></section>
            <section className="feature-card"><div className="feature-copy"><span className="feature-kicker">UNA ISLA EN CADA CANCIÓN</span><h2>Los sonidos de<br/><em>{countryName}</em></h2><p>Descubre ritmos, voces y canciones que conectan contigo.</p><button className="feature-button" onClick={() => { setTab("buscar"); setQuery(""); }}>Explorar música <Icon name="arrow"/></button></div><div className="feature-art"><div className="sun-disc"/><div className="art-line line-one"/><div className="art-line line-two"/><span className="art-caption">CULTURA<br/>EN MOVIMIENTO</span></div></section>
            <section className="section-block"><div className="section-heading"><div><span className="section-overline">VUELVE A TU RITMO</span><h2>Escuchado recientemente</h2></div><button className="text-action" onClick={() => setTab("biblioteca")}>Ver biblioteca <Icon name="arrow"/></button></div><div className="track-grid">{tracks.slice(0,4).map((track) => <TrackCard key={track.id} track={track} favorite={favorites.includes(track.id)} onFavorite={() => toggleFavorite(track.id)} onPlay={() => playTrack(track)}/>)}</div></section>
            <section className="section-block"><div className="section-heading"><div><span className="section-overline">SELECCIÓN KUBANFY</span><h2>Para sentirte en casa</h2></div><span className="pill">País · {countryName}</span></div><div className="wide-track-list">{tracks.filter(t => t.country === country || country === "CU").slice(0,3).map((track,i)=><TrackRow key={track.id} track={track} index={i+1} favorite={favorites.includes(track.id)} onFavorite={() => toggleFavorite(track.id)} onPlay={() => playTrack(track)}/>)}</div></section>
          </>}
          {tab === "buscar" && <section className="page-panel"><div className="eyebrow"><span className="eyebrow-dot"/> DESCUBRIMIENTO</div><h1>Encuentra tu <em>sonido.</em></h1><p className="page-intro">Busca entre canciones y artistas de la selección de KubanFy.</p><label className="search-large"><Icon name="search"/><input autoFocus value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="¿Qué quieres escuchar?"/></label><div className="section-heading search-results-head"><div><span className="section-overline">CATÁLOGO DE MUESTRA</span><h2>{query ? `Resultados para “${query}”` : "Canciones para descubrir"}</h2></div><span className="pill">{filtered.length} canciones</span></div>{filtered.length ? <div className="track-grid">{filtered.map(track=><TrackCard key={track.id} track={track} favorite={favorites.includes(track.id)} onFavorite={()=>toggleFavorite(track.id)} onPlay={()=>playTrack(track)}/>)}</div> : <div className="empty-state"><span>⌕</span><h3>No encontramos ese ritmo</h3><p>Prueba con otro nombre o artista.</p><button className="text-action" onClick={()=>setQuery("")}>Limpiar búsqueda</button></div>}</section>}
          {tab === "biblioteca" && <section className="page-panel"><div className="eyebrow"><span className="eyebrow-dot"/> TU COLECCIÓN</div><h1>Tu música, <em>tu mundo.</em></h1><p className="page-intro">Aquí se reúnen las canciones que guardas.</p><div className="library-summary"><div><strong>{favorites.length.toString().padStart(2,"0")}</strong><span>Canciones favoritas</span></div><div><strong>01</strong><span>Playlist personal</span></div><div><strong>—</strong><span>Álbumes guardados</span></div></div><div className="section-heading"><div><span className="section-overline">GUARDADAS POR TI</span><h2>Favoritos</h2></div></div>{favorites.length ? <div className="wide-track-list">{tracks.filter(t=>favorites.includes(t.id)).map((track,i)=><TrackRow key={track.id} track={track} index={i+1} favorite onFavorite={()=>toggleFavorite(track.id)} onPlay={()=>playTrack(track)}/>)}</div> : <div className="empty-state"><span>♡</span><h3>Tu biblioteca empieza aquí</h3><p>Guarda una canción con el corazón para encontrarla aquí.</p><button className="text-action" onClick={()=>setTab("buscar")}>Descubrir música <Icon name="arrow"/></button></div>}</section>}
          {tab === "perfil" && <section className="page-panel profile-page"><div className="eyebrow"><span className="eyebrow-dot"/> TU CUENTA</div><h1>Tu espacio, <em>tus reglas.</em></h1><p className="page-intro">Personaliza cómo KubanFy se conecta contigo.</p><div className="profile-card"><div className="profile-avatar">K</div><div><h2>{userName}</h2><p>Perfil de desarrollo · KubanFy 2</p><span className="pill">Plan gratuito</span></div></div><div className="settings-card"><div><strong>País de contenido</strong><p>Elige de qué escena musical quieres descubrir tendencias.</p></div><select value={country} onChange={(e)=>setCountry(e.target.value)}><option value="CU">🇨🇺 Cuba</option><option value="US">🇺🇸 Estados Unidos</option><option value="ES">🇪🇸 España</option><option value="PR">🇵🇷 Puerto Rico</option><option value="MX">🇲🇽 México</option></select></div><div className="settings-card"><div><strong>Sesión</strong><p>Salir de tu cuenta en este navegador.</p></div><button className="outline-button" onClick={logout}>Cerrar sesión</button></div><div className="prototype-note">La interfaz está en fase inicial. Los datos musicales son de demostración; las APIs de catálogo, perfil y biblioteca se conectarán en las siguientes tareas.</div></section>}
          <footer className="content-footer"><span>© KUBANFY 2</span><span>HECHO CON RITMO <b>✳</b></span></footer>
        </div>
      </section>

      <nav className="mobile-nav" aria-label="Navegación móvil">{nav.map(item=><button key={item.id} className={tab===item.id?"mobile-nav-item active":"mobile-nav-item"} onClick={()=>setTab(item.id)}><span>{item.glyph}</span><small>{item.id==="biblioteca"?"Biblioteca":item.label}</small></button>)}</nav>

      <div className="player-bar"><Cover track={current} size="small"/><div className="player-track"><strong>{current.title}</strong><small>{current.artist}</small></div><button className={favorites.includes(current.id)?"player-heart loved":"player-heart"} aria-label="Añadir a favoritos" onClick={()=>toggleFavorite(current.id)}><Icon name="heart"/></button><div className="player-controls"><button aria-label="Canción anterior" onClick={()=>playTrack(tracks[(tracks.findIndex(t=>t.id===current.id)+tracks.length-1)%tracks.length])}><Icon name="previous"/></button><button className="player-play" aria-label={playing?"Pausar":"Reproducir"} onClick={()=>setPlaying(!playing)}><Icon name={playing?"pause":"play"}/></button><button aria-label="Canción siguiente" onClick={()=>playTrack(tracks[(tracks.findIndex(t=>t.id===current.id)+1)%tracks.length])}><Icon name="next"/></button></div><div className="player-progress"><span/><i/></div><span className="player-duration">{current.duration}</span></div>
    </main>
  );
}

function TrackCard({ track, favorite, onFavorite, onPlay }: { track: Track; favorite: boolean; onFavorite: () => void; onPlay: () => void }) {
  return <article className="track-card"><button className="cover-button" onClick={onPlay} aria-label={`Reproducir ${track.title}`}><Cover track={track}/><span className="cover-play"><Icon name="play"/></span></button><div className="track-card-meta"><div><strong>{track.title}</strong><span>{track.artist}</span></div><button className={favorite?"favorite-button loved":"favorite-button"} aria-label={favorite?"Quitar de favoritos":"Añadir a favoritos"} onClick={onFavorite}><Icon name="heart"/></button></div></article>;
}
function TrackRow({ track, index, favorite, onFavorite, onPlay }: { track: Track; index: number; favorite: boolean; onFavorite: () => void; onPlay: () => void }) {
  return <div className="track-row"><button className="track-index" onClick={onPlay} aria-label={`Reproducir ${track.title}`}>{String(index).padStart(2,"0")}<span><Icon name="play"/></span></button><Cover track={track} size="small"/><button className="track-row-info" onClick={onPlay}><strong>{track.title}</strong><small>{track.artist}</small></button><span className="track-country">{track.country}</span><button className={favorite?"favorite-button loved":"favorite-button"} aria-label={favorite?"Quitar favorito":"Añadir favorito"} onClick={onFavorite}><Icon name="heart"/></button><span className="track-time">{track.duration}</span></div>;
}
