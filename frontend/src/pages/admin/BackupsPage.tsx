// NG-HEADER: Nombre de archivo: BackupsPage.tsx
// NG-HEADER: Ubicación: frontend/src/pages/admin/BackupsPage.tsx
// NG-HEADER: Descripción: Página de administración de backups: listar y ejecutar backup on-demand
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import { BackupItem, listBackups, runBackup, downloadBackup } from '../../services/backups'

export default function BackupsPage() {
  const [items, setItems] = useState<BackupItem[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function refresh() {
    try {
      setErr(null)
      const rows = await listBackups()
      setItems(rows)
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'No se pudo listar backups')
    }
  }

  useEffect(() => { refresh() }, [])

  return (
    <div className="card" style={{ padding: 12 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <h3>Backups</h3>
        <button className="btn-primary" disabled={busy} onClick={async () => {
          if (!window.confirm('¿Crear backup ahora?')) return
          setBusy(true)
          try {
            const r = await runBackup()
            await refresh()
            if (r.file) {
              if (window.confirm('Backup creado. ¿Descargar ahora?')) downloadBackup(r.file)
            }
          } catch (e: any) {
            setErr(e?.response?.data?.detail || 'No se pudo crear el backup')
          } finally { setBusy(false) }
        }}>{busy ? 'Creando…' : 'Backup ahora'}</button>
      </div>
      {err && <div style={{ color: '#fca5a5', marginTop: 8 }}>{err}</div>}
      <table className="table" style={{ width: '100%', marginTop: 12 }}>
        <thead>
          <tr>
            <th>Archivo</th>
            <th>Tamaño</th>
            <th>Fecha</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr><td colSpan={4} style={{ opacity: 0.7 }}>No hay backups aún</td></tr>
          )}
          {items.map(it => (
            <tr key={it.filename}>
              <td>{it.filename}</td>
              <td>{(it.size / 1024 / 1024).toFixed(2)} MB</td>
              <td>{new Date(it.modified).toLocaleString()}</td>
              <td><button className="btn" onClick={() => downloadBackup(it.filename)}>Descargar</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
