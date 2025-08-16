import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

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
