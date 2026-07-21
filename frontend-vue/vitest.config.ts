// NG-HEADER: Nombre de archivo: vitest.config.ts
// NG-HEADER: Ubicación: frontend-vue/vitest.config.ts
// NG-HEADER: Descripción: Configuración de pruebas unitarias del frontend Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'

export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true })],
  test: {
    environment: 'jsdom',
    globals: true,
    server: { deps: { inline: ['vuetify'] } },
    exclude: ['tests/e2e/**', 'node_modules/**', 'dist/**'],
  },
})
