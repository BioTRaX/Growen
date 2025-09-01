import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const port = Number(process.env.VITE_PORT || 5175)

export default defineConfig({
  plugins: [react()],
  base: '/',
  define: {
    'import.meta.env.VITE_API_URL': JSON.stringify(process.env.VITE_API_URL || 'http://127.0.0.1:8000'),
  },
  server: {
    host: '127.0.0.1',
    port,
  hmr: { host: '127.0.0.1', protocol: 'ws', port },
    proxy: {
      '/ws': { target: 'http://127.0.0.1:8000', ws: true, changeOrigin: true },
      '/chat': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/actions': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    }
  }
})
