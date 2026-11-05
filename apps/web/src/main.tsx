import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import { registerServiceWorker } from "./swRegister";

void registerServiceWorker({
  onUpdateAvailable: () => {
    window.dispatchEvent(new CustomEvent("kubanfy:sw-update"));
  },
  onControlling: () => {
    // New SW took control after SKIP_WAITING — soft reload once.
    window.location.reload();
  },
});

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
