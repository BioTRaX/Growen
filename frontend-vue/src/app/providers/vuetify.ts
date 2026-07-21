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
          marketAligned: '#164E63',
          marketSlightlyCheaper: '#713F12',
          marketModeratelyCheaper: '#7C2D12',
          marketVeryCheaper: '#431407',
          marketMuchCheaper: '#7F1D1D',
          marketSlightlyExpensive: '#1E3A8A',
          marketModeratelyExpensive: '#701A75',
          marketVeryExpensive: '#581C87',
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
          marketAligned: '#007C91',
          marketSlightlyCheaper: '#8A5A00',
          marketModeratelyCheaper: '#A54800',
          marketVeryCheaper: '#8F2D00',
          marketMuchCheaper: '#B42318',
          marketSlightlyExpensive: '#175CD3',
          marketModeratelyExpensive: '#A10F85',
          marketVeryExpensive: '#7A005C',
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
