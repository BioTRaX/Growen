import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import http from '../services/http'

export default function ResetPassword() {
  const { token } = useParams()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Las contraseñas no coinciden')
      return
    }
    try {
      await http.post(`/auth/reset/${token}`, { password })
      alert('Contraseña actualizada')
      navigate('/login')
    } catch {
      setError('Token inválido o expirado')
    }
  }

  return (
    <div
      className="flex items-center justify-center h-screen"
      style={{ background: 'var(--bg-color)' }}
    >
      <form
        onSubmit={submit}
        className="panel p-4 flex flex-col gap-2"
        style={{ width: 300 }}
      >
        <input
          className="input"
          type="password"
          placeholder="Nueva contraseña"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <input
          className="input"
          type="password"
          placeholder="Repetir contraseña"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        {error && <div style={{ color: 'var(--primary)', fontSize: 12 }}>{error}</div>}
        <button className="btn-primary" type="submit">
          Guardar
        </button>
      </form>
    </div>
  )
}

