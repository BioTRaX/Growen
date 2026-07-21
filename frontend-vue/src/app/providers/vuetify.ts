// NG-HEADER: Nombre de archivo: vuetify.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/providers/vuetify.ts
// NG-HEADER: Descripción: Temas y configuración global de Vuetify.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { createVuetify } from 'vuetify'

export const vuetify = createVuetify({
  theme: {
    defaultTheme: 'growenDark',
    themes: {
      growenDark: {
        dark: true,
        colors: {
          background: '#0f1115',
          surface: '#151821',
          primary: '#7c4dff',
          secondary: '#e879f9',
          success: '#22c55e',
          error: '#ef4444',
        },
      },
      growenLight: {
        dark: false,
        colors: {
          background: '#f8fafc',
          surface: '#ffffff',
          primary: '#6d28d9',
          secondary: '#c026d3',
          success: '#16a34a',
          error: '#dc2626',
        },
      },
    },
  },
  defaults: {
    VBtn: { rounded: 'lg' },
    VCard: { rounded: 'xl' },
    VTextField: { variant: 'outlined', density: 'comfortable' },
  },
})
