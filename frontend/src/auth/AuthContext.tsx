// NG-HEADER: Nombre de archivo: AuthContext.tsx
// NG-HEADER: Ubicación: frontend/src/auth/AuthContext.tsx
// NG-HEADER: Descripción: Pendiente de descripción
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
  const navigate = useNavigate()

  const refreshMe = async () => {
    const resp = await http.get('/auth/me')
    if (resp.data.is_authenticated) {
      setState({ user: resp.data.user, role: resp.data.role, isAuthenticated: true })
    } else {
      setState({ role: 'guest', isAuthenticated: false })
    }
  }

  useEffect(() => {
    refreshMe()
  }, [])

  const login = async (identifier: string, password: string) => {
    const resp = await http.post('/auth/login', { identifier, password })
    const user = resp.data
    // Reflejar estado inmediatamente según respuesta del backend
    setState({ user, role: user.role, isAuthenticated: true })
    // Confirmar en segundo plano; solo aplicamos si está autenticado
    try {
      const me = await http.get('/auth/me')
      if (me.data?.is_authenticated) {
        setState({ user: me.data.user, role: me.data.role, isAuthenticated: true })
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

