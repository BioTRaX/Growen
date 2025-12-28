// NG-HEADER: Nombre de archivo: WorkersPage.tsx
// NG-HEADER: Ubicación: frontend/src/pages/admin/WorkersPage.tsx
// NG-HEADER: Descripción: Página de administración de workers (ServicesPanel)
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { Suspense, lazy } from 'react'
import { useNavigate } from 'react-router-dom'
import { PATHS } from '../../routes/paths'

const ServicesPanel = lazy(() => import('../../components/ServicesPanel'))

export default function WorkersPage() {
    const nav = useNavigate()

    return (
        <div className="panel p-4" style={{ color: 'var(--text-color)' }}>
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h2>⚙️ Workers</h2>
                <button className="btn-secondary" onClick={() => nav(PATHS.adminServices)}>
                    ← Volver a Servicios
                </button>
            </div>

            <p style={{ color: '#9ca3af', marginBottom: 16 }}>
                Administración de servicios de background: Dramatiq, Scheduler, Drive Sync, Telegram Polling, etc.
            </p>

            <Suspense fallback={<div>Cargando workers...</div>}>
                <ServicesPanel />
            </Suspense>
        </div>
    )
}
