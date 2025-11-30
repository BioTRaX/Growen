// NG-HEADER: Nombre de archivo: vitest.config.ts
// NG-HEADER: Ubicación: frontend/vitest.config.ts
// NG-HEADER: Descripción: Configuración de Vitest para pruebas de frontend.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { defineConfig } from 'vitest/config'
import path from 'node:path'

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    globals: true,
    exclude: [
      '**/node_modules/**',
      '**/tests/e2e/**',
    ],
    server: {
      deps: {
        inline: [
          'react',
          'react-dom',
          '@testing-library/react',
          '@testing-library/user-event',
          '@testing-library/jest-dom'
        ]
      }
    }
  },
  esbuild: {
    jsx: 'automatic',
    jsxImportSource: 'react'
  },
  resolve: {
    dedupe: ['react', 'react-dom'],
    alias: {
      react: path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
      'react/jsx-runtime': path.resolve(__dirname, 'node_modules/react/jsx-runtime.js')
    }
  }
})