// NG-HEADER: Nombre de archivo: ThemeProvider.tsx
// NG-HEADER: Ubicación: frontend/src/theme/ThemeProvider.tsx
// NG-HEADER: Descripción: Proveedor de tema (light/dark) y hook de acceso.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'

export type ThemeName = 'light' | 'dark'

interface ThemeTokens {
  name: ThemeName
  bg: string
  text: string
  card: string
  border: string
  accent: string
  danger: string
}

const LIGHT: ThemeTokens = {
  name: 'light',
  bg: '#f8fafc',
  text: '#111827',
  card: '#ffffff',
  border: '#d1d5db',
  accent: '#22c55e',
  danger: '#ef4444',
}

const DARK: ThemeTokens = {
  name: 'dark',
  bg: '#111',
  text: '#eee',
  card: '#1f1f1f',
  border: '#333',
  accent: '#22c55e',
  danger: '#ef4444',
}

interface ThemeContextValue extends ThemeTokens {
  setTheme: (t: ThemeName) => void
  toggle: () => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const detectInitial = (): ThemeName => {
    try {
      const stored = localStorage.getItem('ng_theme') as ThemeName | null
      if (stored === 'light' || stored === 'dark') return stored
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark'
    } catch {}
    return 'light'
  }
  const [name, setName] = useState<ThemeName>(detectInitial)

  useEffect(() => {
    try { localStorage.setItem('ng_theme', name) } catch {}
    document.documentElement.dataset.theme = name
  }, [name])

  const setTheme = useCallback((t: ThemeName) => setName(t), [])
  const toggle = useCallback(() => setName(p => p === 'dark' ? 'light' : 'dark'), [])
  const tokens = name === 'dark' ? DARK : LIGHT
  const value: ThemeContextValue = { ...tokens, setTheme, toggle }
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme debe usarse dentro de ThemeProvider')
  return ctx
}
