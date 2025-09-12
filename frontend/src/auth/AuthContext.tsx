// NG-HEADER: Nombre de archivo: AuthContext.tsx
// NG-HEADER: Ubicación: frontend/src/auth/AuthContext.tsx
// NG-HEADER: Descripción: Contexto de autenticación con rehidratación local
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { createContext, useContext, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import http from '../services/http'

export type Role = 'guest' | 'cliente' | 'proveedor' | 'colaborador' | 'admin'

interface User {
  id: number
  identifier: string
  email?: string | null
  name?: string | null
  role: Role
  supplier_id?: number | null
}

interface AuthState {
  user?: User
  role: Role
  isAuthenticated: boolean
}

interface AuthContextShape {
  state: AuthState
  login: (identifier: string, password: string) => Promise<void>
  loginAsGuest: () => Promise<void>
  logout: () => Promise<void>
  refreshMe: () => Promise<void>
}

const AuthContext = createContext<AuthContextShape | undefined>(undefined)

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [state, setState] = useState<AuthState>({ role: 'guest', isAuthenticated: false })
  const [hydrated, setHydrated] = useState(false)
  const navigate = useNavigate()

  // Persist simple auth marker to avoid redirect on refresh
  type Persist = { role: Role; exp: number }
  const AUTH_KEY = 'auth'
  const savePersist = (role: Role, ttlSeconds = 12 * 60 * 60) => {
    const exp = Math.floor(Date.now() / 1000) + ttlSeconds
    try { localStorage.setItem(AUTH_KEY, JSON.stringify({ role, exp } as Persist)) } catch {}
  }
  const loadPersist = (): Persist | null => {
    try {
      const raw = localStorage.getItem(AUTH_KEY)
      if (!raw) return null
      const v = JSON.parse(raw) as Persist
      if (!v || typeof v.exp !== 'number') return null
      if (v.exp <= Math.floor(Date.now() / 1000)) { localStorage.removeItem(AUTH_KEY); return null }
      return v
    } catch { return null }
  }
  const clearPersist = () => { try { localStorage.removeItem(AUTH_KEY) } catch {} }

  const refreshMe = async () => {
    const resp = await http.get('/auth/me')
    if (resp.data.is_authenticated) {
      setState({ user: resp.data.user, role: resp.data.role, isAuthenticated: true })
      savePersist(resp.data.role as Role)
    } else {
      setState({ role: 'guest', isAuthenticated: false })
      clearPersist()
    }
    if (!hydrated) setHydrated(true)
  }

  useEffect(() => {
    // Optimistic local rehydration before calling /auth/me
    const persisted = loadPersist()
    if (persisted) {
      setState(prev => ({ ...prev, role: persisted.role, isAuthenticated: true }))
    }
    refreshMe().finally(() => setHydrated(true))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const login = async (identifier: string, password: string) => {
    const resp = await http.post('/auth/login', { identifier, password })
    const user = resp.data
    // Reflejar estado inmediatamente según respuesta del backend
    setState({ user, role: user.role, isAuthenticated: true })
    savePersist(user.role)
    // Confirmar en segundo plano; solo aplicamos si está autenticado
    try {
      const me = await http.get('/auth/me')
      if (me.data?.is_authenticated) {
        setState({ user: me.data.user, role: me.data.role, isAuthenticated: true })
        savePersist(me.data.role as Role)
      }
    } catch {}
    navigate('/')
  }

  const loginAsGuest = async () => {
    try {
      await http.post('/auth/guest')
    } finally {
      await refreshMe()
      navigate('/guest', { replace: true })
    }
  }

  const logout = async () => {
    try {
      await http.post('/auth/logout')
    } catch (e: any) {
      // If CSRF blocks logout (403), drop client-side state anyway
      if (e?.response?.status !== 403) throw e
    } finally {
      setState({ role: 'guest', isAuthenticated: false, user: undefined })
      clearPersist()
      navigate('/login', { replace: true })
    }
  }

  return (
    <AuthContext.Provider value={{ state, login, loginAsGuest, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

