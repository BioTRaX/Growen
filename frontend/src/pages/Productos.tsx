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
