// NG-HEADER: Nombre de archivo: playwright.config.ts
// NG-HEADER: Ubicación: frontend-vue/playwright.config.ts
// NG-HEADER: Descripción: Configuración E2E del frontend Vue con API interceptable.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://127.0.0.1:5186',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
