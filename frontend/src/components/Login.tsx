// NG-HEADER: Nombre de archivo: Login.tsx
// NG-HEADER: Ubicación: frontend/src/components/Login.tsx
// NG-HEADER: Descripción: Formulario de inicio de sesión del frontend.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'

export default function Login() {
  const { login, loginAsGuest } = useAuth()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await login(identifier, password)
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 401) setError('Credenciales inválidas')
      else if (status === 429) setError('Demasiados intentos, espera unos minutos')
      else setError('Error al iniciar sesión')
    }
  }

  return (
    <div
      className="flex items-center justify-center h-screen"
      style={{ background: 'var(--bg-color)' }}
    >
      <form
        onSubmit={handleSubmit}
        className="panel p-4 flex flex-col gap-2"
        style={{ width: 300 }}
      >
        <input
          className="input"
          value={identifier}
          onChange={(e) => setIdentifier(e.target.value)}
          placeholder="Usuario o email"
          autoFocus
        />
        <input
          className="input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Contraseña"
        />
        {error && <div style={{ color: 'var(--primary)', fontSize: 12 }}>{error}</div>}
        <button className="btn-primary" type="submit">
          Ingresar
        </button>
        <button type="button" onClick={loginAsGuest}>
          Ingresar como invitado
        </button>
      </form>
    </div>
  )
}

