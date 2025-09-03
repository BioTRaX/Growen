// NG-HEADER: Nombre de archivo: vite.config.ts
// NG-HEADER: Ubicación: frontend/vite.config.ts
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
/// <reference types="node" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Read from env var if present (set via cross-env or shell), else fallback
const p = Number(process?.env?.VITE_PORT ?? NaN)
const port = (Number as any).isFinite ? (Number as any).isFinite(p) ? p : 5175 : 5175

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port,
    hmr: { host: '127.0.0.1', protocol: 'ws', port },
    proxy: {
      '/ws': {
        target: 'http://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/actions': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    }
  }
})
