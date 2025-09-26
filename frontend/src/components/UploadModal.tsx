// NG-HEADER: Nombre de archivo: UploadModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/UploadModal.tsx
// NG-HEADER: Descripción: Modal para subir archivos externos (PDF/EML).
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import {
  uploadPriceList,
  downloadTemplate,
  downloadGenericTemplate,
} from '../services/imports'
import SupplierAutocomplete from './supplier/SupplierAutocomplete'
import type { SupplierSearchItem } from '../services/suppliers'
import CreateSupplierModal from './CreateSupplierModal'
import { useAuth } from '../auth/AuthContext'

interface Props {
  open: boolean
  onClose: () => void
  onUploaded: (info: { jobId: number; summary: any }) => void
  preselectedFile?: File | null
}

export default function UploadModal({ open, onClose, onUploaded, preselectedFile }: Props) {
  const { state } = useAuth()
  const [supplierSel, setSupplierSel] = useState<SupplierSearchItem | null>(null)
  const [supplierId, setSupplierId] = useState<number | ''>('')
  const [file, setFile] = useState<File | null>(preselectedFile || null)
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const MAX_MB = Number(import.meta.env.VITE_MAX_UPLOAD_MB ?? 15)

  function refresh() { /* ya no requiere prefetch: se usa autocomplete */ }

  useEffect(() => {
    if (open) refresh()
  }, [open])

  useEffect(() => {
    if (preselectedFile) setFile(preselectedFile)
  }, [preselectedFile])

  useEffect(() => {
    if (state.role === 'proveedor' && state.user?.supplier_id) {
      setSupplierId(state.user.supplier_id)
    }
  }, [state])

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null
    setError('')
    setFile(f)
  }

  const canSubmit = !!file && !!supplierId

  async function onSubmit() {
    if (!file || !supplierId) return
    const ext = file.name.toLowerCase()
    if (!ext.endsWith('.xlsx') && !ext.endsWith('.csv')) {
      setError('Formato no soportado. Usa .xlsx o .csv')
      return
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`Archivo supera el límite de ${MAX_MB} MB`)
      return
    }
    try {
      const r = await uploadPriceList(Number(supplierId), file)
      onUploaded({ jobId: r.job_id, summary: r.summary })
      onClose()
    } catch (e: any) {
      const msg =
        e?.response?.data?.detail || e?.message || 'Error al subir archivo'
      setError(msg)
    }
  }

  if (!open) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.3)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div className="panel p-4" style={{ width: 400 }}>
        <h3>Adjuntar lista de precios</h3>
        {error && <div style={{ color: 'var(--primary)', marginBottom: 8 }}>{error}</div>}
        <div style={{ margin: '8px 0' }}>
          <SupplierAutocomplete
            value={supplierSel}
            onChange={(item) => { setSupplierSel(item); setSupplierId(item ? item.id : '') }}
            placeholder="Selecciona proveedor"
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            {state.role !== 'proveedor' && (
              <button onClick={() => setCreateOpen(true)}>Crear proveedor</button>
            )}
            <button onClick={downloadGenericTemplate}>
              Descargar plantilla genérica
            </button>
            <button
              onClick={() => supplierId && downloadTemplate(Number(supplierId))}
              disabled={!supplierId}
            >
              Descargar plantilla
            </button>
          </div>
        </div>
        <div style={{ margin: '8px 0' }}>
          <input
            type="file"
            accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
            onChange={handleFile}
            disabled={!supplierId}
          />
          {file && (
            <small className="badge-muted">
              #{file.name} — {(file.size / 1024 / 1024).toFixed(2)} MB
            </small>
          )}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
          <button onClick={onClose}>Cancelar</button>
          <button className="btn-primary" disabled={!canSubmit} onClick={onSubmit}>
            Subir
          </button>
        </div>
        {createOpen && (
          <CreateSupplierModal
            open={createOpen}
            onClose={() => setCreateOpen(false)}
            onCreated={(s) => {
              setCreateOpen(false)
              refresh()
              setSupplierId(s.id)
            }}
          />
        )}
      </div>
    </div>
  )
}
