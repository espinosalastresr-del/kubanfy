import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import { registerServiceWorker } from "./swRegister";
import { initInstallPromptCapture } from "./installPrompt";

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
