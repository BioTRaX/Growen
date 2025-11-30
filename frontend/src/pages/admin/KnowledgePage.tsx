// NG-HEADER: Nombre de archivo: KnowledgePage.tsx
// NG-HEADER: Ubicación: frontend/src/pages/admin/KnowledgePage.tsx
// NG-HEADER: Descripción: Página de administración de Knowledge Base (Cerebro) - gestión de documentos RAG
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useCallback, useEffect, useRef, useState } from 'react'
import http from '../../services/http'

// --- Tipos ---
interface KnowledgeFile {
  filename: string
  path: string
  full_path: string
  extension: string
  size_bytes: number
  modified_at: string
  indexed: boolean
  source_id: number | null
  chunks_count: number
  indexed_at: string | null
  needs_reindex: boolean
}

interface KnowledgeStatus {
  total_sources: number
  total_chunks: number
  total_tokens_estimated: number
  files_in_folder: number
  files_pending: number
  files_need_reindex: number
  last_indexed_at: string | null
  knowledge_path: string
  tasks_running: number
  current_task: Task | null
}

interface Task {
  id: string
  type: string
  target: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  started_at: string
  completed_at: string | null
  result: any
  error: string | null
}

// --- Helpers ---
function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function extIcon(ext: string): string {
  switch (ext) {
    case '.pdf': return '📕'
    case '.md': return '📝'
    case '.txt': return '📄'
    default: return '📁'
  }
}

// --- Componente Principal ---
export default function KnowledgePage() {
  const [files, setFiles] = useState<KnowledgeFile[]>([])
  const [status, setStatus] = useState<KnowledgeStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [indexing, setIndexing] = useState<string | null>(null) // filename o 'folder'
  const [currentTask, setCurrentTask] = useState<Task | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // --- Fetch data ---
  const fetchFiles = useCallback(async () => {
    try {
      const res = await http.get('/admin/knowledge/files')
      setFiles(res.data.files || [])
    } catch (e: any) {
      console.error('Error fetching files:', e)
    }
  }, [])

  const fetchStatus = useCallback(async () => {
    try {
      const res = await http.get('/admin/knowledge/status')
      setStatus(res.data)
      setCurrentTask(res.data.current_task)
    } catch (e: any) {
      console.error('Error fetching status:', e)
    }
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      await Promise.all([fetchFiles(), fetchStatus()])
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Error al cargar datos')
    } finally {
      setLoading(false)
    }
  }, [fetchFiles, fetchStatus])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Poll para tareas en curso
  useEffect(() => {
    if (!currentTask || currentTask.status === 'completed' || currentTask.status === 'failed') {
      return
    }
    const interval = setInterval(async () => {
      try {
        const res = await http.get(`/admin/knowledge/tasks/${currentTask.id}`)
        const task = res.data as Task
        setCurrentTask(task)
        if (task.status === 'completed' || task.status === 'failed') {
          setIndexing(null)
          await refresh()
        }
      } catch {
        // ignore
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [currentTask, refresh])

  // --- Upload ---
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await http.post('/admin/knowledge/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      await refresh()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Error al subir archivo')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // --- Index ---
  const handleIndex = async (target: string, force: boolean = false) => {
    setIndexing(target)
    setError(null)
    try {
      const res = await http.post('/admin/knowledge/index', {
        target,
        force_reindex: force,
      })
      const taskId = res.data.task_id
      // Empezar a poll
      const taskRes = await http.get(`/admin/knowledge/tasks/${taskId}`)
      setCurrentTask(taskRes.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Error al iniciar indexación')
      setIndexing(null)
    }
  }

  // --- Delete source (de DB) ---
  const handleDeleteSource = async (sourceId: number, filename: string) => {
    if (!window.confirm(`¿Eliminar indexación de "${filename}"? El archivo NO se borrará del disco.`)) {
      return
    }
    try {
      await http.delete(`/admin/knowledge/sources/${sourceId}`)
      await refresh()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Error al eliminar')
    }
  }

  // --- UI ---
  const isIndexingFile = (path: string) => indexing === path
  const isIndexingFolder = indexing === 'folder'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header con estadísticas */}
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h3 style={{ margin: 0, marginBottom: 8 }}>🧠 Cerebro (Knowledge Base)</h3>
            <p style={{ margin: 0, opacity: 0.7, fontSize: 13 }}>
              Gestiona documentos para el sistema RAG del chatbot
            </p>
          </div>
          <button className="btn" onClick={refresh} disabled={loading}>
            {loading ? 'Cargando...' : '↻ Actualizar'}
          </button>
        </div>

        {status && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginTop: 16 }}>
            <StatBox label="Fuentes indexadas" value={status.total_sources} />
            <StatBox label="Chunks (fragmentos)" value={status.total_chunks} />
            <StatBox label="Tokens estimados" value={status.total_tokens_estimated.toLocaleString()} />
            <StatBox label="Archivos en carpeta" value={status.files_in_folder} />
            <StatBox label="Pendientes de indexar" value={status.files_pending} highlight={status.files_pending > 0} />
            <StatBox label="Requieren re-index" value={status.files_need_reindex} highlight={status.files_need_reindex > 0} />
          </div>
        )}

        {status?.last_indexed_at && (
          <p style={{ marginTop: 12, marginBottom: 0, fontSize: 12, opacity: 0.6 }}>
            Última indexación: {formatDate(status.last_indexed_at)}
          </p>
        )}
      </div>

      {/* Errores */}
      {error && (
        <div style={{ padding: 12, backgroundColor: 'rgba(239, 68, 68, 0.15)', borderRadius: 6, color: '#fca5a5' }}>
          {error}
        </div>
      )}

      {/* Tarea en curso */}
      {currentTask && (currentTask.status === 'pending' || currentTask.status === 'running') && (
        <div style={{ padding: 12, backgroundColor: 'rgba(59, 130, 246, 0.15)', borderRadius: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="spinner" style={{ width: 16, height: 16 }} />
            <span>
              {currentTask.type === 'index_folder' 
                ? 'Indexando carpeta completa...' 
                : `Indexando: ${currentTask.target}...`}
            </span>
          </div>
        </div>
      )}

      {/* Resultado de tarea */}
      {currentTask && currentTask.status === 'completed' && currentTask.result && (
        <div style={{ padding: 12, backgroundColor: 'rgba(34, 197, 94, 0.15)', borderRadius: 6 }}>
          ✅ Indexación completada: {currentTask.result.chunks_created || currentTask.result.total_chunks || 0} chunks creados
        </div>
      )}

      {currentTask && currentTask.status === 'failed' && (
        <div style={{ padding: 12, backgroundColor: 'rgba(239, 68, 68, 0.15)', borderRadius: 6, color: '#fca5a5' }}>
          ❌ Error: {currentTask.error}
        </div>
      )}

      {/* Acciones globales */}
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Upload */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleUpload}
            accept=".md,.txt,.pdf"
            style={{ display: 'none' }}
          />
          <button
            className="btn-primary"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? 'Subiendo...' : '📤 Subir archivo'}
          </button>

          {/* Re-indexar carpeta */}
          <button
            className="btn"
            onClick={() => handleIndex('folder', false)}
            disabled={isIndexingFolder || loading}
          >
            {isIndexingFolder ? 'Indexando...' : '🔄 Indexar carpeta'}
          </button>

          {/* Re-indexar forzado */}
          <button
            className="btn"
            onClick={() => {
              if (window.confirm('¿Re-indexar TODO forzadamente? Esto regenerará todos los embeddings.')) {
                handleIndex('folder', true)
              }
            }}
            disabled={isIndexingFolder || loading}
            style={{ opacity: 0.8 }}
          >
            ⚡ Re-indexar (forzar)
          </button>
        </div>
        <p style={{ marginTop: 8, marginBottom: 0, fontSize: 12, opacity: 0.6 }}>
          Formatos soportados: PDF, Markdown (.md), Texto plano (.txt)
        </p>
      </div>

      {/* Tabla de archivos */}
      <div className="card" style={{ padding: 16 }}>
        <h4 style={{ margin: 0, marginBottom: 12 }}>Archivos en /Conocimientos</h4>
        
        {files.length === 0 ? (
          <p style={{ opacity: 0.6 }}>
            No hay archivos. Sube documentos para comenzar.
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>Archivo</th>
                  <th>Tamaño</th>
                  <th>Estado</th>
                  <th>Chunks</th>
                  <th>Última indexación</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {files.map((f) => (
                  <tr key={f.path}>
                    <td>
                      <span style={{ marginRight: 6 }}>{extIcon(f.extension)}</span>
                      {f.filename}
                    </td>
                    <td>{formatBytes(f.size_bytes)}</td>
                    <td>
                      <StatusBadge file={f} />
                    </td>
                    <td>{f.chunks_count || '-'}</td>
                    <td style={{ fontSize: 12 }}>{formatDate(f.indexed_at)}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          className="btn"
                          style={{ padding: '4px 8px', fontSize: 12 }}
                          onClick={() => handleIndex(f.path, f.needs_reindex)}
                          disabled={isIndexingFile(f.path) || isIndexingFolder}
                        >
                          {isIndexingFile(f.path) ? '...' : f.indexed ? '🔄' : '▶️'}
                        </button>
                        {f.source_id && (
                          <button
                            className="btn"
                            style={{ padding: '4px 8px', fontSize: 12 }}
                            onClick={() => handleDeleteSource(f.source_id!, f.filename)}
                            title="Eliminar de la base de datos (no borra el archivo)"
                          >
                            🗑️
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Spinner CSS */}
      <style>{`
        .spinner {
          border: 2px solid transparent;
          border-top-color: var(--primary, #3b82f6);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

// --- Componentes auxiliares ---
function StatBox({ label, value, highlight }: { label: string; value: number | string; highlight?: boolean }) {
  return (
    <div style={{
      padding: '10px 12px',
      backgroundColor: highlight ? 'rgba(251, 191, 36, 0.15)' : 'rgba(255,255,255,0.05)',
      borderRadius: 6,
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 22, fontWeight: 600, color: highlight ? '#fbbf24' : undefined }}>
        {value}
      </div>
      <div style={{ fontSize: 11, opacity: 0.7 }}>{label}</div>
    </div>
  )
}

function StatusBadge({ file }: { file: KnowledgeFile }) {
  if (!file.indexed) {
    return <span style={{ color: '#94a3b8', fontSize: 12 }}>⏳ Pendiente</span>
  }
  if (file.needs_reindex) {
    return <span style={{ color: '#fbbf24', fontSize: 12 }}>⚠️ Modificado</span>
  }
  return <span style={{ color: '#4ade80', fontSize: 12 }}>✅ Indexado</span>
}

