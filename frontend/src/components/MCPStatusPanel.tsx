// NG-HEADER: Nombre de archivo: MCPStatusPanel.tsx
// NG-HEADER: Ubicación: frontend/src/components/MCPStatusPanel.tsx
// NG-HEADER: Descripción: Panel de estado de servidores MCP (Model Context Protocol)
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useEffect, useState } from 'react'
import { checkMCPHealth, startMCPServer, stopMCPServer, MCPServerStatus } from '../services/mcpHealth'

function StatusDot({ status, healthy }: { status: string; healthy: boolean }) {
    const color = status === 'running' && healthy
        ? '#22c55e'
        : status === 'running'
            ? '#f59e0b'
            : '#ef4444'
    return (
        <span
            style={{
                display: 'inline-block',
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: color,
                marginRight: 8,
                boxShadow: `0 0 8px ${color}80`
            }}
        />
    )
}

export default function MCPStatusPanel() {
    const [servers, setServers] = useState<MCPServerStatus[]>([])
    const [loading, setLoading] = useState(true)
    const [busy, setBusy] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [initialized, setInitialized] = useState(false)

    async function refresh() {
        try {
            setError(null)
            const data = await checkMCPHealth()
            setServers(data.servers || [])
        } catch (e: any) {
            console.error('[MCPStatusPanel] Error fetching health:', e)
            const msg = e?.response?.data?.detail || e?.message || 'No se pudo conectar con los servicios MCP'
            setError(msg)
            setServers([])
        } finally {
            setLoading(false)
            setInitialized(true)
        }
    }

    useEffect(() => {
        refresh()
        const interval = setInterval(refresh, 15000)
        return () => clearInterval(interval)
    }, [])

    async function handleStart(name: string) {
        setBusy(name)
        try {
            await startMCPServer(name)
            setTimeout(refresh, 2000) // Dar tiempo al contenedor
        } catch (e: any) {
            setError(e?.response?.data?.detail || `Error al iniciar ${name}`)
        } finally {
            setBusy(null)
        }
    }

    async function handleStop(name: string) {
        setBusy(name)
        try {
            await stopMCPServer(name)
            await refresh()
        } catch (e: any) {
            setError(e?.response?.data?.detail || `Error al detener ${name}`)
        } finally {
            setBusy(null)
        }
    }

    return (
        <div className="card" style={{ padding: 16, marginBottom: 16 }}>
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ margin: 0 }}>🔌 Servidores MCP (Model Context Protocol)</h3>
                <button className="btn" onClick={refresh} disabled={loading}>
                    {loading ? 'Verificando...' : 'Actualizar'}
                </button>
            </div>

            <p style={{ fontSize: 13, color: '#9ca3af', marginBottom: 12 }}>
                Servicios de herramientas para el ChatBot IA. Permiten búsqueda de productos y enriquecimiento con web.
            </p>

            {error && (
                <div style={{
                    background: '#7f1d1d',
                    color: '#fca5a5',
                    padding: 8,
                    borderRadius: 6,
                    marginBottom: 12,
                    fontSize: 13
                }}>
                    ⚠️ {error}
                </div>
            )}

            {loading && servers.length === 0 ? (
                <div style={{ padding: 12, color: '#9ca3af' }}>Cargando estado...</div>
            ) : (
                <div className="col" style={{ gap: 10 }}>
                    {servers.map((server) => (
                        <div
                            key={server.name}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                padding: 12,
                                border: '1px solid #2a2a2a',
                                borderRadius: 8,
                                background: '#1a1a1a'
                            }}
                        >
                            <div>
                                <div style={{ display: 'flex', alignItems: 'center' }}>
                                    <StatusDot status={server.status} healthy={server.healthy} />
                                    <strong>{server.label}</strong>
                                    <span style={{
                                        marginLeft: 8,
                                        fontSize: 12,
                                        color: '#6b7280',
                                        fontFamily: 'monospace'
                                    }}>
                                        :{server.port}
                                    </span>
                                </div>
                                <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>
                                    Estado: {server.status === 'running' ? (server.healthy ? '✓ Corriendo y saludable' : '⚠ Corriendo pero sin respuesta') : '✗ Detenido'}
                                    {server.error && <span style={{ color: '#fca5a5' }}> · {server.error}</span>}
                                </div>
                            </div>

                            <div className="row" style={{ gap: 8 }}>
                                {server.status !== 'running' ? (
                                    <button
                                        className="btn-primary"
                                        disabled={busy === server.name}
                                        onClick={() => handleStart(server.name)}
                                    >
                                        {busy === server.name ? 'Iniciando...' : 'Iniciar'}
                                    </button>
                                ) : (
                                    <button
                                        className="btn"
                                        disabled={busy === server.name}
                                        onClick={() => handleStop(server.name)}
                                    >
                                        {busy === server.name ? 'Deteniendo...' : 'Detener'}
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}

                    {servers.length === 0 && !loading && (
                        <div style={{ padding: 12, color: '#9ca3af', textAlign: 'center' }}>
                            No hay servidores MCP configurados.
                        </div>
                    )}
                </div>
            )}

            <div style={{ marginTop: 12, fontSize: 12, color: '#6b7280' }}>
                💡 Tip: Estos contenedores Docker se pueden iniciar manualmente con:
                <code style={{
                    display: 'block',
                    background: '#0a0a0a',
                    padding: 8,
                    borderRadius: 4,
                    marginTop: 4,
                    fontFamily: 'monospace'
                }}>
                    docker compose up -d mcp_products mcp_web_search
                </code>
            </div>
        </div>
    )
}
