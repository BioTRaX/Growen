import { lazy, Suspense } from 'react'

// Reuse existing ImagesAdminPanel to reduce duplicated logic
const LegacyImagesAdminPanel = lazy(() => import('../ImagesAdminPanel'))

export default function ImagesCrawlerPage() {
  return (
    <div className="card" style={{ padding: 12 }}>
      <h3>Crawler de imágenes</h3>
      <Suspense fallback={<div>Cargando...</div>}>
        <LegacyImagesAdminPanel embedded />
      </Suspense>
    </div>
  )
}
