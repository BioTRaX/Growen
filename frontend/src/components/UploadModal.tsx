import { useEffect, useState } from 'react'
import { uploadPriceList } from '../services/imports'
import { listSuppliers, Supplier } from '../services/suppliers'
import CreateSupplierModal from './CreateSupplierModal'
import { useAuth } from '../auth/AuthContext'

interface Props {
  open: boolean
  onClose: () => void
  onUploaded: (info: { jobId: number; summary: any; kpis: any }) => void
  preselectedFile?: File | null
}

export default function UploadModal({ open, onClose, onUploaded, preselectedFile }: Props) {
  const { state } = useAuth()
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [supplierId, setSupplierId] = useState<number | ''>('')
  const [file, setFile] = useState<File | null>(preselectedFile || null)
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const MAX_MB = Number(import.meta.env.VITE_MAX_UPLOAD_MB ?? 15)

  function refresh() {
    listSuppliers()
      .then(setSuppliers)
      .catch((e) => setError(e.message))
  }

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
      onUploaded({ jobId: r.job_id, summary: r.summary, kpis: r.kpis })
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
        {suppliers.length === 0 ? (
          <div style={{ margin: '8px 0' }}>
            <p>No hay proveedores aún.</p>
            <button onClick={() => setCreateOpen(true)}>Crear proveedor</button>
          </div>
        ) : (
          <div style={{ margin: '8px 0' }}>
            <select
              className="select w-full"
              value={supplierId}
              onChange={(e) => setSupplierId(Number(e.target.value))}
              disabled={state.role === 'proveedor'}
            >
              <option value="">Selecciona proveedor</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            {state.role !== 'proveedor' && (
              <button style={{ marginTop: 8 }} onClick={() => setCreateOpen(true)}>
                Crear proveedor
              </button>
            )}
          </div>
        )}
        <div style={{ margin: '8px 0' }}>
          <input
            type="file"
            accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
            onChange={handleFile}
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
