// NG-HEADER: Nombre de archivo: store.ts
// NG-HEADER: Ubicación: frontend-vue/src/auth/store.ts
// NG-HEADER: Descripción: Estado Pinia de sesión y rehidratación de autenticación.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { http } from '../services/http'
import type { Role, User } from './types'

const AUTH_KEY = 'auth'
const SESSION_TTL_SECONDS = 12 * 60 * 60

interface PersistedAuth {
  role: Role
  exp: number
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User>()
  const role = ref<Role>('guest')
  const isAuthenticated = ref(false)
  const hydrated = ref(false)
  let hydrationPromise: Promise<void> | undefined

  const isStaff = computed(() => role.value === 'colaborador' || role.value === 'admin')

  function persist(nextRole: Role): void {
    const exp = Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS
    localStorage.setItem(AUTH_KEY, JSON.stringify({ role: nextRole, exp } satisfies PersistedAuth))
  }

  function clear(): void {
    user.value = undefined
    role.value = 'guest'
    isAuthenticated.value = false
    localStorage.removeItem(AUTH_KEY)
  }

  function clearSession(): void {
    clear()
    hydrated.value = true
  }

  function loadPersisted(): PersistedAuth | undefined {
    try {
      const value = JSON.parse(localStorage.getItem(AUTH_KEY) ?? 'null') as PersistedAuth | null
      if (!value || value.exp <= Math.floor(Date.now() / 1000)) return undefined
      return value
    } catch {
      return undefined
    }
  }

  async function refreshMe(): Promise<void> {
    try {
      const { data } = await http.get('/auth/me')
      if (!data.is_authenticated) {
        clear()
        return
      }
      user.value = data.user
      role.value = data.role
      isAuthenticated.value = true
      persist(data.role)
    } catch {
      clear()
    } finally {
      hydrated.value = true
    }
  }

  async function hydrate(): Promise<void> {
    if (hydrated.value) return
    if (!hydrationPromise) {
      const saved = loadPersisted()
      if (saved) {
        role.value = saved.role
        isAuthenticated.value = true
      }
      hydrationPromise = refreshMe()
    }
    await hydrationPromise
  }

  async function login(identifier: string, password: string): Promise<void> {
    const { data } = await http.post<User>('/auth/login', { identifier, password })
    user.value = data
    role.value = data.role
    isAuthenticated.value = true
    hydrated.value = true
    persist(data.role)
  }

  async function loginAsGuest(): Promise<void> {
    await http.post('/auth/guest')
    await refreshMe()
  }

  async function logout(): Promise<void> {
    try {
      await http.post('/auth/logout')
    } catch (error: unknown) {
      if (!axiosStatusIs(error, 403)) throw error
    } finally {
      clear()
      hydrated.value = true
    }
  }

  return { user, role, isAuthenticated, hydrated, isStaff, hydrate, refreshMe, login, loginAsGuest, logout, clearSession }
})

function axiosStatusIs(error: unknown, status: number): boolean {
  return typeof error === 'object' && error !== null && 'response' in error &&
    (error as { response?: { status?: number } }).response?.status === status
}
