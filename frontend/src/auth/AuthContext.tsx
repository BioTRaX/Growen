import { createContext, useContext, useEffect, useState } from 'react'
import http from '../services/http'

export type Role = 'guest' | 'cliente' | 'proveedor' | 'colaborador' | 'admin'

interface User {
  id: number
  email: string
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
  login: (email: string, password: string) => Promise<void>
  loginAsGuest: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextShape | undefined>(undefined)

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [state, setState] = useState<AuthState>({ role: 'guest', isAuthenticated: false })

  const refreshMe = async () => {
    const resp = await http.get('/auth/me')
    if (resp.data.is_authenticated) {
      setState({ user: resp.data.user, role: resp.data.role, isAuthenticated: true })
    }
  }

  useEffect(() => {
    refreshMe()
  }, [])

  const login = async (email: string, password: string) => {
    const resp = await http.post('/auth/login', { email, password })
    setState({ user: resp.data, role: resp.data.role, isAuthenticated: true })
  }

  const loginAsGuest = async () => {
    const resp = await http.post('/auth/guest')
    setState({ role: resp.data.role, isAuthenticated: true })
  }

  const logout = async () => {
    await http.post('/auth/logout')
    setState({ role: 'guest', isAuthenticated: false, user: undefined })
  }

  return (
    <AuthContext.Provider value={{ state, login, loginAsGuest, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

