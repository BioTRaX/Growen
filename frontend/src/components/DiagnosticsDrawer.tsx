// NG-HEADER: Nombre de archivo: DiagnosticsDrawer.tsx
// NG-HEADER: Ubicación: frontend/src/components/DiagnosticsDrawer.tsx
// NG-HEADER: Descripción: Panel lateral para ver requests recientes con correlation-id
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import { diagList, diagClear } from '../lib/corrStore'

interface Props {
  open: boolean
  onClose: () => void
}

export default function DiagnosticsDrawer({ open, onClose }: Props) {
  const [items, setItems] = useState(diagList())

  useEffect(() => {
    const t = setInterval(() => setItems(diagList()), 800)
    return () => clearInterval(t)
  }, [])

  if (!open) return null

  return (
    <div style={{ position: 'fixed', top: 0, right: 0, height: '100%', width: 460, background: 'var(--panel-bg)', borderLeft: '1px solid var(--border)', boxShadow: '0 0 24px rgba(0,0,0,0.35)', zIndex: 60, display: 'flex', flexDirection: 'column' }}>
      <div className="row" style={{ padding: 12, borderBottom: '1px solid var(--border)', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontWeight: 600 }}>Diagnóstico (últimas requests)</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button className="btn" onClick={() => setItems(diagList())}>Actualizar</button>
          <button className="btn" onClick={() => { diagClear(); setItems([]) }}>Limpiar</button>
          <button className="btn-secondary" onClick={onClose}>Cerrar</button>
        </div>
      </div>
      <div style={{ padding: 12, overflow: 'auto' }}>
        {items.length === 0 ? (
          <div style={{ opacity: 0.8 }}>Sin datos aún. Ejecutá acciones en la app para ver tráfico.</div>
        ) : (
          <table className="table w-full">
            <thead>
              <tr>
                <th>Hora</th>
                <th>Método</th>
                <th>URL</th>
                <th>Estado</th>
                <th>ms</th>
                <th>cid</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it, idx) => (
                <tr key={idx}>
                  <td>{new Date(it.ts).toLocaleTimeString()}</td>
                  <td>{it.method}</td>
                  <td className="truncate" title={it.url} style={{ maxWidth: 240 }}>{it.url}</td>
                  <td>{it.status}</td>
                  <td>{it.ms}</td>
                  <td>{it.cid || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
