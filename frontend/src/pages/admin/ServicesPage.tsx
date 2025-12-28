// NG-HEADER: Nombre de archivo: ServicesPage.tsx
// NG-HEADER: Ubicación: frontend/src/pages/admin/ServicesPage.tsx
// NG-HEADER: Descripción: Página resumen de servicios con navegación a Workers y MCP Tools
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PATHS } from '../../routes/paths'
import { listServices, ServiceItem } from '../../services/servicesAdmin'
import { checkMCPHealth, MCPServerStatus } from '../../services/mcpHealth'

export default function ServicesPage() {
  const nav = useNavigate()
  const [workers, setWorkers] = useState<ServiceItem[]>([])
  const [mcpServers, setMcpServers] = useState<MCPServerStatus[]>([])
  const [loadingWorkers, setLoadingWorkers] = useState(true)
  const [loadingMCP, setLoadingMCP] = useState(true)
  const [errorWorkers, setErrorWorkers] = useState<string | null>(null)
  const [errorMCP, setErrorMCP] = useState<string | null>(null)

  useEffect(() => {
    // Fetch workers status
    listServices()
      .then(data => setWorkers(data))
      .catch(e => setErrorWorkers(e?.response?.data?.detail || 'Error cargando workers'))
      .finally(() => setLoadingWorkers(false))

    // Fetch MCP status
    checkMCPHealth()
      .then(data => setMcpServers(data.servers || []))
      .catch(e => setErrorMCP(e?.response?.data?.detail || 'Error cargando MCP'))
      .finally(() => setLoadingMCP(false))
  }, [])

  const workersRunning = workers.filter(w => w.status === 'running').length
  const workersTotal = workers.length
  const mcpRunning = mcpServers.filter(s => s.status === 'running' && s.healthy).length
  const mcpTotal = mcpServers.length

  return (
    <div className="card" style={{ padding: 16 }}>
      <h3>Servicios</h3>
      <p style={{ color: '#9ca3af', marginBottom: 16 }}>
        Administración de servicios de background y herramientas MCP.
      </p>

      <div className="row" style={{ gap: 16, flexWrap: 'wrap' }}>
        {/* Workers Card */}
        <div
          className="card"
          style={{
            flex: '1 1 280px',
            padding: 20,
            cursor: 'pointer',
            border: '1px solid #2a2a2a',
            transition: 'border-color 0.2s',
            background: '#1a1a1a',
          }}
          onClick={() => nav(PATHS.adminServicesWorkers)}
          onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--primary)')}
          onMouseLeave={e => (e.currentTarget.style.borderColor = '#2a2a2a')}
        >
          <div className="row" style={{ alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <span style={{ fontSize: 28 }}>⚙️</span>
            <h4 style={{ margin: 0 }}>Workers</h4>
          </div>
          {loadingWorkers ? (
            <p style={{ color: '#9ca3af' }}>Cargando...</p>
          ) : errorWorkers ? (
            <p style={{ color: '#fca5a5', fontSize: 13 }}>{errorWorkers}</p>
          ) : (
            <div>
              <p style={{ fontSize: 24, fontWeight: 'bold', margin: '8px 0' }}>
                <span style={{ color: workersRunning > 0 ? '#22c55e' : '#ef4444' }}>
                  {workersRunning}
                </span>
                <span style={{ color: '#6b7280', fontWeight: 'normal' }}> / {workersTotal} online</span>
              </p>
              <p style={{ color: '#9ca3af', fontSize: 12 }}>
                Dramatiq, Scheduler, Notifier, etc.
              </p>
            </div>
          )}
          <button className="btn-primary" style={{ marginTop: 12, width: '100%' }}>
            Administrar Workers →
          </button>
        </div>

        {/* MCP Tools Card */}
        <div
          className="card"
          style={{
            flex: '1 1 280px',
            padding: 20,
            cursor: 'pointer',
            border: '1px solid #2a2a2a',
            transition: 'border-color 0.2s',
            background: '#1a1a1a',
          }}
          onClick={() => nav(PATHS.adminServicesMCP)}
          onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--primary)')}
          onMouseLeave={e => (e.currentTarget.style.borderColor = '#2a2a2a')}
        >
          <div className="row" style={{ alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <span style={{ fontSize: 28 }}>🔌</span>
            <h4 style={{ margin: 0 }}>MCP Tools</h4>
          </div>
          {loadingMCP ? (
            <p style={{ color: '#9ca3af' }}>Cargando...</p>
          ) : errorMCP ? (
            <p style={{ color: '#fca5a5', fontSize: 13 }}>{errorMCP}</p>
          ) : (
            <div>
              <p style={{ fontSize: 24, fontWeight: 'bold', margin: '8px 0' }}>
                <span style={{ color: mcpRunning > 0 ? '#22c55e' : '#ef4444' }}>
                  {mcpRunning}
                </span>
                <span style={{ color: '#6b7280', fontWeight: 'normal' }}> / {mcpTotal} online</span>
              </p>
              <p style={{ color: '#9ca3af', fontSize: 12 }}>
                MCP Products, MCP Web Search
              </p>
            </div>
          )}
          <button className="btn-primary" style={{ marginTop: 12, width: '100%' }}>
            Administrar MCP →
          </button>
        </div>
      </div>
    </div>
  )
}
