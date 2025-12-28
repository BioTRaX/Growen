// NG-HEADER: Nombre de archivo: MCPToolsPage.tsx
// NG-HEADER: Ubicación: frontend/src/pages/admin/MCPToolsPage.tsx
// NG-HEADER: Descripción: Página de administración de servidores MCP
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { Suspense, lazy } from 'react'
import { useNavigate } from 'react-router-dom'
import { PATHS } from '../../routes/paths'

const MCPStatusPanel = lazy(() => import('../../components/MCPStatusPanel'))

export default function MCPToolsPage() {
    const nav = useNavigate()

    return (
        <div className="panel p-4" style={{ color: 'var(--text-color)' }}>
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h2>🔌 MCP Tools</h2>
                <button className="btn-secondary" onClick={() => nav(PATHS.adminServices)}>
                    ← Volver a Servicios
                </button>
            </div>

            <p style={{ color: '#9ca3af', marginBottom: 16 }}>
                Servidores MCP (Model Context Protocol) para herramientas del ChatBot IA.
            </p>

            <Suspense fallback={<div>Cargando MCP...</div>}>
                <MCPStatusPanel />
            </Suspense>
        </div>
    )
}
