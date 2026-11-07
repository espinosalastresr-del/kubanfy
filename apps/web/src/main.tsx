import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import { registerServiceWorker } from "./swRegister";
import { initInstallPromptCapture } from "./installPrompt";

class AppErrorBoundary extends React.Component<React.PropsWithChildren, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error) {
    try { console.error("KubanFy UI startup/render error:", error); } catch {}
  }
  render() {
    if (this.state.failed) {
      return (
        <main style={{ minHeight: "100vh", display: "grid", placeContent: "center", padding: 24, background: "#09090b", color: "#fff", fontFamily: "system-ui", textAlign: "center" }}>
          <h1>KubanFy no pudo abrirse</h1>
          <p style={{ color: "#b7b7bf", maxWidth: 360 }}>Comprueba tu conexión e inténtalo de nuevo. Si el problema continúa, actualiza la página.</p>
          <button onClick={() => window.location.reload()} style={{ padding: "12px 18px", border: 0, borderRadius: 12, background: "#f5c542", color: "#09090b", fontWeight: 700 }}>Volver a intentar</button>
        </main>
      );
    }
    return this.props.children;
  }
}

initInstallPromptCapture();

void registerServiceWorker({
  onUpdateAvailable: () => {
    window.dispatchEvent(new CustomEvent("kubanfy:sw-update"));
  },
  onControlling: () => {
    window.location.reload();
  },
});

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
