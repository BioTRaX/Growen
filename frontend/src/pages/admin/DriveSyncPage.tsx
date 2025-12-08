// NG-HEADER: Nombre de archivo: DriveSyncPage.tsx
// NG-HEADER: Ubicación: frontend/src/pages/admin/DriveSyncPage.tsx
// NG-HEADER: Descripción: Página de administración para sincronización de imágenes desde Google Drive.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState, useEffect, useRef } from 'react'
import http, { baseURL } from '../../services/http'
import { useToast } from '../../components/ToastProvider'

interface SyncProgress {
  status: 'idle' | 'initializing' | 'listing' | 'processing' | 'completed' | 'error'
  current: number
  total: number
  remaining?: number
  sku: string
  filename?: string
  message: string
  error?: string
  stats?: {
    processed: number
    errors: number
    no_sku: number
  }
}

export default function DriveSyncPage() {
  const [status, setStatus] = useState<'idle' | 'running' | 'completed' | 'error'>('idle')
  const [progress, setProgress] = useState<SyncProgress | null>(null)
  const [syncId, setSyncId] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const { push } = useToast()

  useEffect(() => {
    // Evitar múltiples conexiones en modo desarrollo de React
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return
    }

    // Cerrar conexión existente si hay una
    if (wsRef.current) {
      try {
        wsRef.current.close()
      } catch (e) {
        // Ignorar errores al cerrar
      }
    }

    // Conectar WebSocket al montar
    // Usar baseURL del backend en lugar de location.host (que es el frontend)
    const apiUrl = new URL(baseURL)
    const wsProtocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${apiUrl.host}/admin/drive-sync/ws`
    
    let ws: WebSocket | null = null
    let isMounted = true

    try {
      ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (isMounted) {
          console.log('WebSocket conectado para sincronización Drive')
        }
      }

      ws.onmessage = (event) => {
        if (!isMounted) return
        
        try {
          const data = JSON.parse(event.data)
          
          if (data.type === 'drive_sync_progress') {
            setProgress({
              status: data.status || 'processing',
              current: data.current || 0,
              total: data.total || 0,
              remaining: data.remaining || 0,
              sku: data.sku || '',
              filename: data.filename || '',
              message: data.message || '',
              error: data.error,
              stats: data.stats || { processed: 0, errors: 0, no_sku: 0 },
            })

            if (data.status === 'completed') {
              setStatus('completed')
              push({
                kind: 'success',
                title: 'Sincronización completada',
                message: data.message || 'La sincronización finalizó exitosamente',
              })
            } else if (data.status === 'error') {
              setStatus('error')
              push({
                kind: 'error',
                title: 'Error en sincronización',
                message: data.error || data.message || 'Ocurrió un error durante la sincronización',
              })
            } else if (data.status === 'processing' || data.status === 'initializing' || data.status === 'listing') {
              setStatus('running')
            }
          } else if (data.type === 'drive_sync_status') {
            if (data.status === 'running') {
              setStatus('running')
              setSyncId(data.sync_id)
            }
          } else if (data.type === 'ping') {
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'pong' }))
            }
          }
        } catch (e) {
          console.error('Error parseando mensaje WebSocket:', e)
        }
      }

      ws.onerror = (error) => {
        if (isMounted) {
          console.error('Error en WebSocket:', error)
        }
      }

      ws.onclose = () => {
        if (isMounted) {
          console.log('WebSocket desconectado')
        }
      }
    } catch (error) {
      console.error('Error creando WebSocket:', error)
    }

    // Cargar estado inicial
    loadStatus()

    return () => {
      isMounted = false
      if (wsRef.current) {
        try {
          wsRef.current.close()
        } catch (e) {
          // Ignorar errores al cerrar
        }
        wsRef.current = null
      }
    }
  }, []) // Remover 'push' de dependencias para evitar re-renders innecesarios

  const loadStatus = async () => {
    try {
      const res = await http.get('/admin/drive-sync/status')
      if (res.data.status === 'running') {
        setStatus('running')
        setSyncId(res.data.sync_id)
      } else {
        setStatus('idle')
      }
    } catch (e) {
      console.error('Error cargando estado:', e)
    }
  }

  const handleStart = async (sourceFolderId?: string) => {
    try {
      const params = sourceFolderId ? { source_folder_id: sourceFolderId } : {}
      const res = await http.post('/admin/drive-sync/start', null, { params })
      setStatus('running')
      setSyncId(res.data.sync_id)
      push({
        kind: 'success',
        title: 'Sincronización iniciada',
        message: sourceFolderId 
          ? 'Procesando archivos desde Errores_SKU...'
          : 'La sincronización de imágenes desde Google Drive ha comenzado',
      })
    } catch (e: any) {
      const message = e.response?.data?.detail || 'Error al iniciar sincronización'
      push({
        kind: 'error',
        title: 'Error',
        message,
      })
    }
  }

  const handleStartFromErrors = async () => {
    try {
      // Obtener ID de carpeta Errores_SKU
      const res = await http.get('/admin/drive-sync/errors-folder-id')
      
      if (!res.data || !res.data.folder_id) {
        const errorMsg = res.data?.error || res.data?.detail || 'No se pudo obtener el ID de la carpeta Errores_SKU'
        push({
          kind: 'error',
          title: 'Error',
          message: errorMsg,
        })
        return
      }
      
      const errorsFolderId = res.data.folder_id
      
      // Iniciar sincronización desde Errores_SKU
      await handleStart(errorsFolderId)
    } catch (e: any) {
      const message = e.response?.data?.detail || e.response?.data?.error || e.message || 'Error al obtener carpeta Errores_SKU'
      console.error('Error obteniendo carpeta Errores_SKU:', e)
      push({
        kind: 'error',
        title: 'Error',
        message,
      })
    }
  }

  const getStatusLabel = () => {
    switch (status) {
      case 'idle':
        return 'Inactivo'
      case 'running':
        return 'Procesando'
      case 'completed':
        return 'Completado'
      case 'error':
        return 'Error'
      default:
        return 'Desconocido'
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case 'idle':
        return 'var(--muted)'
      case 'running':
        return 'var(--primary)'
      case 'completed':
        return 'var(--success)'
      case 'error':
        return 'var(--danger)'
      default:
        return 'var(--muted)'
    }
  }

  return (
    <div className="card" style={{ padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3>Sincronización Google Drive</h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div
            style={{
              padding: '4px 12px',
              borderRadius: 4,
              backgroundColor: getStatusColor(),
              color: 'white',
              fontSize: 12,
              fontWeight: 'bold',
            }}
          >
            {getStatusLabel()}
          </div>
          <button
            className="btn"
            onClick={() => handleStart()}
            disabled={status === 'running'}
            style={{ opacity: status === 'running' ? 0.6 : 1 }}
          >
            {status === 'running' ? 'Sincronizando...' : 'Iniciar Sincronización'}
          </button>
          <button
            className="btn"
            onClick={handleStartFromErrors}
            disabled={status === 'running'}
            style={{ 
              opacity: status === 'running' ? 0.6 : 1,
              backgroundColor: 'var(--warning)',
              color: 'white',
            }}
            title="Procesar archivos desde la carpeta Errores_SKU"
          >
            Procesar Errores_SKU
          </button>
        </div>
      </div>

      {status === 'running' && progress && (
        <div style={{ marginTop: 16 }}>
          {/* Barra de progreso principal */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 14, fontWeight: 'bold' }}>Progreso General</span>
              <span style={{ fontSize: 14, color: 'var(--muted)' }}>
                {progress.current} / {progress.total} {progress.remaining !== undefined && progress.remaining > 0 && `(faltan ${progress.remaining})`}
              </span>
            </div>
            {/* Porcentaje destacado fuera de la barra */}
            {progress.total > 0 && (
              <div style={{ fontSize: 16, fontWeight: 'bold', color: 'var(--primary)', marginBottom: 8 }}>
                {Math.round((progress.current / progress.total) * 100)}% completado ({progress.current}/{progress.total} archivos)
              </div>
            )}
            <div
              style={{
                width: '100%',
                height: 28,
                backgroundColor: 'var(--bg-secondary)',
                borderRadius: 4,
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              <div
                style={{
                  width: `${progress.total > 0 ? (progress.current / progress.total) * 100 : 0}%`,
                  height: '100%',
                  backgroundColor: 'var(--primary)',
                  transition: 'width 0.3s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontSize: 14,
                  fontWeight: 'bold',
                }}
              >
                {progress.total > 0 ? `${Math.round((progress.current / progress.total) * 100)}%` : '0%'}
              </div>
            </div>
          </div>

          {/* Estadísticas */}
          {progress.stats && (
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(3, 1fr)', 
              gap: 8, 
              marginBottom: 16 
            }}>
              <div style={{ padding: 12, backgroundColor: 'var(--success-light)', borderRadius: 4, textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 'bold', color: 'var(--success)' }}>
                  {progress.stats.processed}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>Procesados</div>
              </div>
              <div style={{ padding: 12, backgroundColor: 'var(--danger-light)', borderRadius: 4, textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 'bold', color: 'var(--danger)' }}>
                  {progress.stats.errors}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>Errores</div>
              </div>
              <div style={{ padding: 12, backgroundColor: 'var(--warning-light)', borderRadius: 4, textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 'bold', color: 'var(--warning)' }}>
                  {progress.stats.no_sku}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>Sin SKU</div>
              </div>
            </div>
          )}

          {/* Nombre de archivo actual */}
          {progress.filename && (
            <div style={{ marginTop: 12, padding: 16, backgroundColor: 'var(--info-light)', borderRadius: 4, borderLeft: '4px solid var(--info)' }}>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4, textTransform: 'uppercase' }}>
                Archivo Actual
              </div>
              <div style={{ fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace', color: 'var(--text)', wordBreak: 'break-all' }}>
                {progress.filename}
              </div>
            </div>
          )}

          {/* SKU actual y mensaje */}
          {progress.sku && (
            <div style={{ marginTop: 12, padding: 16, backgroundColor: 'var(--bg-secondary)', borderRadius: 4, borderLeft: '4px solid var(--primary)' }}>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4, textTransform: 'uppercase' }}>
                SKU Actual
              </div>
              <div style={{ fontSize: 20, fontWeight: 'bold', marginBottom: 8 }}>{progress.sku}</div>
              {progress.message && (
                <div style={{ fontSize: 14, color: 'var(--text)', marginTop: 4 }}>{progress.message}</div>
              )}
            </div>
          )}

          {progress.message && !progress.sku && (
            <div style={{ marginTop: 12, padding: 12, backgroundColor: 'var(--bg-secondary)', borderRadius: 4 }}>
              <div style={{ fontSize: 14 }}>{progress.message}</div>
            </div>
          )}

          {/* Error actual (si hay) */}
          {progress.error && (
            <div
              style={{
                marginTop: 12,
                padding: 12,
                backgroundColor: 'var(--danger-light)',
                borderRadius: 4,
                borderLeft: '4px solid var(--danger)',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 'bold', color: 'var(--danger)', marginBottom: 4 }}>
                ⚠️ Error en archivo actual:
              </div>
              <div style={{ fontSize: 13, color: 'var(--danger)' }}>{progress.error}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8, fontStyle: 'italic' }}>
                El proceso continuará con los siguientes archivos...
              </div>
            </div>
          )}
        </div>
      )}

      {status === 'completed' && progress && (
        <div style={{ marginTop: 16 }}>
          <div style={{ padding: 16, backgroundColor: 'var(--success-light)', borderRadius: 4, marginBottom: 16 }}>
            <div style={{ fontSize: 18, fontWeight: 'bold', marginBottom: 8, color: 'var(--success)' }}>
              ✅ Sincronización completada
            </div>
            <div style={{ fontSize: 14, marginBottom: 12 }}>{progress.message}</div>
            
            {/* Estadísticas finales */}
            {progress.stats && (
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(3, 1fr)', 
                gap: 8, 
                marginTop: 12 
              }}>
                <div style={{ padding: 12, backgroundColor: 'white', borderRadius: 4, textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 'bold', color: 'var(--success)' }}>
                    {progress.stats.processed}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>Procesados</div>
                </div>
                <div style={{ padding: 12, backgroundColor: 'white', borderRadius: 4, textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 'bold', color: 'var(--danger)' }}>
                    {progress.stats.errors}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>Errores</div>
                </div>
                <div style={{ padding: 12, backgroundColor: 'white', borderRadius: 4, textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 'bold', color: 'var(--warning)' }}>
                    {progress.stats.no_sku}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>Sin SKU</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {status === 'error' && progress && (
        <div style={{ marginTop: 16, padding: 16, backgroundColor: 'var(--danger-light)', borderRadius: 4 }}>
          <div style={{ fontSize: 16, fontWeight: 'bold', marginBottom: 8, color: 'var(--danger)' }}>Error</div>
          <div style={{ fontSize: 14 }}>{progress.error || progress.message}</div>
        </div>
      )}

      <div style={{ marginTop: 24, padding: 16, backgroundColor: 'var(--bg-secondary)', borderRadius: 4 }}>
        <h4 style={{ marginBottom: 8, fontSize: 14 }}>Información</h4>
        <ul style={{ fontSize: 13, lineHeight: 1.6, margin: 0, paddingLeft: 20 }}>
          <li>Los archivos deben tener formato: <code>SKU #</code> (ej: <code>ABC_1234_XYZ 1.jpg</code>)</li>
          <li>El SKU debe ser canónico (formato: <code>XXX_####_YYY</code>)</li>
          <li>Los archivos procesados se mueven a la carpeta "Procesados"</li>
          <li>Los archivos con SKU no canónico se mueven a "SIN_SKU"</li>
          <li>Los archivos con errores se mueven a "Errores_SKU"</li>
        </ul>
      </div>
    </div>
  )
}

