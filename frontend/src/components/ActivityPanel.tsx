// NG-HEADER: Nombre de archivo: ActivityPanel.tsx
// NG-HEADER: Ubicación: frontend/src/components/ActivityPanel.tsx
// NG-HEADER: Descripción: Panel compacto para mostrar actividad reciente (audit logs) de un producto
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import { getProductAuditLogs, ProductAuditItem } from '../services/products'

export default function ActivityPanel({ productId, onClose }: { productId: number; onClose: () => void }) {
  const [items, setItems] = useState<ProductAuditItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    getProductAuditLogs(productId, 50)
      .then((r) => { if (mounted) setItems(r.items || []) })
      .catch((e: any) => { if (mounted) setError(e?.message || 'No se pudo cargar actividad') })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [productId])

  return (
    <div className="modal-backdrop">
      <div className="modal" style={{ width: 520, maxWidth: '92%' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h3 style={{ flex: 1, margin: 0 }}>Actividad de producto #{productId}</h3>
          <button className="btn" onClick={onClose}>✕</button>
        </div>
        {loading ? (
          <div style={{ marginTop: 12 }}>Cargando…</div>
        ) : error ? (
          <div style={{ marginTop: 12, color: '#fda4af' }}>{error}</div>
        ) : items.length === 0 ? (
          <div style={{ marginTop: 12, opacity: 0.8 }}>Sin actividad reciente</div>
        ) : (
          <ul style={{ marginTop: 12, maxHeight: 360, overflow: 'auto', paddingLeft: 16 }}>
            {items.map((it, idx) => (
              <li key={idx} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', gap: 8 }}>
                  <span className="badge-muted" style={{ minWidth: 80, textAlign: 'center' }}>{it.action}</span>
                  <span style={{ opacity: 0.8, fontSize: 12 }}>{it.created_at ? new Date(it.created_at).toLocaleString() : ''}</span>
                </div>
                {it.meta && (
                  <pre style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid #2a3042', padding: 8, borderRadius: 6, marginTop: 6, whiteSpace: 'pre-wrap', overflowX: 'auto', fontSize: 12 }}>
                    {JSON.stringify(it.meta, null, 2)}
                  </pre>
                )}
              </li>
            ))}
          </ul>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
          <button className="btn" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  )
}
