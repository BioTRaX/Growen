// NG-HEADER: Nombre de archivo: vite.config.ts
// NG-HEADER: Ubicación: frontend-vue/vite.config.ts
// NG-HEADER: Descripción: Vite Vue con assets aislados y proxy único hacia FastAPI.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const apiTarget = env.VITE_API_TARGET || env.VITE_API_URL || 'http://127.0.0.1:8000'

  return {
    base: mode === 'production' ? '/vue-assets/' : '/',
    plugins: [vue(), vuetify({ autoImport: true })],
    server: {
      host: true,
      port: 5176,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          ws: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
        '/media': { target: apiTarget, changeOrigin: true },
      },
    },
  }
})
