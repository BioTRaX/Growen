import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ws': {
        target: 'http://localhost:8000',
        ws: true,
      },
      '/chat': 'http://localhost:8000',
      '/actions': 'http://localhost:8000'
    }
  }
})
