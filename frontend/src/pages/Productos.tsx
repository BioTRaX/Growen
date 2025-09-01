// NG-HEADER: Nombre de archivo: Productos.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Productos.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import AppToolbar from '../components/AppToolbar'
import ProductsDrawer from '../components/ProductsDrawer'
import ToastContainer from '../components/Toast'

export default function ProductosPage() {
  return (
    <>
      <AppToolbar />
      <ProductsDrawer open={true} onClose={() => history.back()} />
      <ToastContainer />
    </>
  )
}
