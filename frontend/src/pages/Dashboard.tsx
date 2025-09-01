// NG-HEADER: Nombre de archivo: Dashboard.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Dashboard.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import AppToolbar from '../components/AppToolbar'
import { useNavigate } from 'react-router-dom'
import { PATHS } from '../routes/paths'
import { useAuth } from '../auth/AuthContext'
import ChatWindow from '../components/ChatWindow'
import ToastContainer from '../components/Toast'

export default function Dashboard() {
  const nav = useNavigate()
  const { state } = useAuth()
  return (
    <>
      <AppToolbar />
      {state.role !== 'guest' && (
        <div className="panel" style={{ margin: 16, padding: 12, display: 'flex', gap: 8 }}>
          <button className="btn-dark btn-lg" onClick={() => nav(PATHS.purchases)}>Compras</button>
        </div>
      )}
      <ChatWindow />
      <ToastContainer />
    </>
  )
}
