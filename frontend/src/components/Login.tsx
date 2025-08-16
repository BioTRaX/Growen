import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'

export default function Login() {
  const { login, loginAsGuest } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await login(email, password)
  }

  return (
    <div className="login-container">
      <form onSubmit={handleSubmit} className="login-card">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Contraseña"
        />
        <button type="submit">Ingresar</button>
      </form>
      <button onClick={loginAsGuest}>Ingresar como invitado</button>
    </div>
  )
}

