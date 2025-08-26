import { useAuth } from '../auth/AuthContext'
import { useNavigate } from 'react-router-dom'

export default function AppToolbar() {
  const { state, logout } = useAuth()
  const navigate = useNavigate()
  function toggleTheme() {
    const el = document.documentElement
    el.dataset.theme = el.dataset.theme === 'dark' ? 'light' : 'dark'
  }
  const canUpload = ['proveedor', 'colaborador', 'admin'].includes(state.role)
  const canSeeSuppliers = state.role !== 'guest'

  return (
    <div
      style={{
        position: 'sticky',
        top: 0,
        background: 'var(--panel-bg)',
        padding: 8,
        display: 'flex',
        gap: 8,
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        zIndex: 10,
        color: 'var(--text-color)',
      }}
    >
      {canUpload && (
        <button className="btn-dark btn-lg" onClick={() => window.dispatchEvent(new Event('open-upload'))}>
          Adjuntar Excel
        </button>
      )}
      {canSeeSuppliers && (
        <button className="btn-dark btn-lg" onClick={() => window.dispatchEvent(new Event('open-suppliers'))}>
          Proveedores
        </button>
      )}
      <button className="btn-dark btn-lg" onClick={() => window.dispatchEvent(new Event('open-products'))}>
        Productos
      </button>
      <button className="btn-dark btn-lg" onClick={toggleTheme}>Modo oscuro</button>
      <button className="btn-dark btn-lg" onClick={() => navigate('/stock')}>Stock</button>
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
        {state.role === 'admin' && (
          <button className="btn-dark btn-lg" onClick={() => navigate('/admin')}>Admin</button>
        )}
        <span style={{ opacity: 0.7 }}>Rol: {state.role}</span>
        {state.isAuthenticated ? (
          <button className="btn-dark btn-lg" onClick={logout}>Salir</button>
        ) : (
          <button className="btn-dark btn-lg" onClick={() => navigate('/login')}>Cambiar usuario</button>
        )}
      </div>
    </div>
  )
}
