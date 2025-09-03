// NG-HEADER: Nombre de archivo: main.tsx
// NG-HEADER: Ubicación: frontend/src/main.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/theme.css";
import "./styles/autocomplete.css";

// Ajusta el tema inicial según `prefers-color-scheme`.
const rootEl = document.documentElement;
if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
  rootEl.dataset.theme = "dark";
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
