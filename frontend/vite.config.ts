// NG-HEADER: Nombre de archivo: vite.config.ts
// NG-HEADER: Ubicación: frontend/vite.config.ts
// NG-HEADER: Descripción: Configuración de Vite para la SPA.
// NG-HEADER: Lineamientos: Ver AGENTS.md
/// <reference types="node" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Puerto preferido (variable VITE_PORT opcional) y base API
const p = Number(process?.env?.VITE_PORT ?? NaN)
const port = (Number as any).isFinite ? (Number as any).isFinite(p) ? p : 5175 : 5175
const API_TARGET = process.env.VITE_API_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  define: {
    'import.meta.env.VITE_API_URL': JSON.stringify(API_TARGET),
  },
  server: {
    host: '127.0.0.1',
    port,
    hmr: { host: '127.0.0.1', protocol: 'ws', port },
    proxy: {
      // WebSocket principal
      '/ws': { target: API_TARGET, ws: true, changeOrigin: true },
      // Chat / acciones (ya existentes)
      '/chat': { target: API_TARGET, changeOrigin: true },
      '/actions': { target: API_TARGET, changeOrigin: true },
      // Auth / sesión
      '/auth': { target: API_TARGET, changeOrigin: true },
      // Catálogo (productos, proveedores, categorías, etc.)
      '/catalog': { target: API_TARGET, changeOrigin: true },
      // Productos extendidos y básicos
      '/products-ex': { target: API_TARGET, changeOrigin: true },
      '/products': { target: API_TARGET, changeOrigin: true },
      // Stock / compras / proveedores
      '/stock': { target: API_TARGET, changeOrigin: true },
      '/purchases': { target: API_TARGET, changeOrigin: true },
      '/suppliers': { target: API_TARGET, changeOrigin: true },
      // Media estática (imágenes) durante dev
      '/media': { target: API_TARGET, changeOrigin: true },
    }
  }
})
