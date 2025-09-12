import { Suspense, lazy } from 'react'

const HealthPanel = lazy(() => import('../../components/HealthPanel'))
const ServicesPanel = lazy(() => import('../../components/ServicesPanel'))

export default function ServicesPage() {
  return (
    <div className="card" style={{ padding: 12 }}>
      <h3>Servicios y Health</h3>
      <div style={{ marginBottom: 8 }}>
        <Suspense fallback={<div>Cargando...</div>}>
          <HealthPanel />
        </Suspense>
      </div>
      <Suspense fallback={<div>Cargando...</div>}>
        <ServicesPanel />
      </Suspense>
    </div>
  )
}

