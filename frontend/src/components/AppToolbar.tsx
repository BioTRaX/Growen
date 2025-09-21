// NG-HEADER: Nombre de archivo: AppToolbar.tsx
// NG-HEADER: Ubicación: frontend/src/components/AppToolbar.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useAuth } from '../auth/AuthContext'
import { useNavigate } from 'react-router-dom'
import { PATHS } from '../routes/paths'

export default function AppToolbar() {
  const { state, logout } = useAuth()
  const navigate = useNavigate()
  function toggleTheme() {
    const el = document.documentElement
    el.dataset.theme = el.dataset.theme === 'dark' ? 'light' : 'dark'
  }
  // Política de visibilidad:
  // - Invitado: no ve botones de navegación (solo Chat en el Dashboard)
  // - Staff (colaborador/admin): ve todo
  // - Cliente/Proveedor: ven Productos y Stock, pero no Proveedores ni Compras
  const isStaff = ['colaborador', 'admin'].includes(state.role)
  const isGuest = state.role === 'guest'
  const canUpload = isStaff
  const canSeeSuppliers = isStaff
  const canManagePurchases = isStaff

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
      {!isGuest && canUpload && (
        <button className="btn-dark btn-lg" onClick={() => window.dispatchEvent(new Event('open-upload'))}>
          Adjuntar Excel
        </button>
      )}
      {!isGuest && canSeeSuppliers && (
        <button className="btn-dark btn-lg" onClick={() => navigate(PATHS.suppliers)}>
          Proveedores
        </button>
      )}
      {!isGuest && (
        <button className="btn-dark btn-lg" onClick={() => navigate(PATHS.products)}>
          Productos
        </button>
      )}
      <button className="btn-dark btn-lg" onClick={toggleTheme}>Modo oscuro</button>
      {!isGuest && (
        <button className="btn-dark btn-lg" onClick={() => navigate(PATHS.stock)}>Stock</button>
      )}
      {!isGuest && canManagePurchases && (
        <button className="btn-dark btn-lg" onClick={() => navigate(PATHS.purchases)}>Compras</button>
      )}
      {isStaff && (
        <button className="btn-dark btn-lg" onClick={() => navigate(PATHS.imagesAdmin)}>Imágenes productos</button>
      )}
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
