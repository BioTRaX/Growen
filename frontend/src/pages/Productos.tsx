// NG-HEADER: Nombre de archivo: Productos.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Productos.tsx
// NG-HEADER: Descripción: Página de catálogo y gestión de productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import AppToolbar from '../components/AppToolbar'
import ProductsDrawer from '../components/ProductsDrawer'
import ToastContainer from '../components/Toast'
import { useNavigate } from 'react-router-dom'
import { PATHS } from '../routes/paths'

export default function ProductosPage() {
  const navigate = useNavigate()
  return (
    <>
      <AppToolbar />
      <div style={{ padding: 12 }}>
        <div className="panel p-4" style={{ margin: '0 auto 12px', maxWidth: 1400 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ color: 'var(--muted)', fontSize: 12 }}>Inicio › Productos</div>
              <h2 style={{ marginTop: 6, marginBottom: 0 }}>Productos</h2>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn" onClick={() => navigate(PATHS.home)}>Volver al inicio</button>
              <button className="btn" onClick={() => navigate(-1)}>Volver</button>
            </div>
          </div>
        </div>
        <ProductsDrawer open={true} onClose={() => navigate(-1)} mode="embedded" />
      </div>
      <ToastContainer />
    </>
  )
}
