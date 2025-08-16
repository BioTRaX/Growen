import { useEffect, useState } from 'react'
import { uploadPriceList } from '../services/imports'
import { listSuppliers, Supplier } from '../services/suppliers'
import CreateSupplierModal from './CreateSupplierModal'

interface Props {
  open: boolean
  onClose: () => void
  onUploaded: (info: { jobId: number; summary: any; kpis: any }) => void
  initialFile?: File | null
}

export default function UploadModal({ open, onClose, onUploaded, initialFile }: Props) {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [supplierId, setSupplierId] = useState('')
  const [file, setFile] = useState<File | null>(initialFile || null)
  const maxMb = Number(import.meta.env.VITE_MAX_UPLOAD_MB) || 8
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)

  function refresh() {
    listSuppliers()
      .then(setSuppliers)
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    if (open) refresh()
  }, [open])

  useEffect(() => {
    if (initialFile) setFile(initialFile)
  }, [initialFile])

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f && f.size > maxMb * 1024 * 1024) {
      setError(`Archivo supera ${maxMb} MB`)
      setFile(null)
    } else {
      setError('')
      setFile(f || null)
    }
  }

  async function submit() {
    if (!supplierId || !file) return
    try {
      const r = await uploadPriceList(Number(supplierId), file)
      onUploaded({ jobId: r.job_id, summary: r.summary, kpis: r.kpis })
      onClose()
    } catch (e: any) {
      let msg = 'Error al subir archivo'
      if (e?.response?.data?.detail) msg = e.response.data.detail
      else if (typeof e?.response?.data === 'string') msg = e.response.data
      else if (e?.message) msg = e.message
      setError(msg)
    }
  }

  if (!open) return null

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: '#fff', padding: 20, borderRadius: 8, width: 400 }}>
        <h3>Adjuntar lista de precios</h3>
        {error && <div style={{ color: 'red' }}>{error}</div>}
        {suppliers.length === 0 ? (
          <div style={{ margin: '8px 0' }}>
            <p>No hay proveedores aún.</p>
            <button onClick={() => setCreateOpen(true)}>Crear proveedor</button>
          </div>
        ) : (
          <div style={{ margin: '8px 0' }}>
            <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)} style={{ width: '100%', padding: 8 }}>
              <option value="">Selecciona proveedor</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <button style={{ marginTop: 8 }} onClick={() => setCreateOpen(true)}>
              Crear proveedor
            </button>
          </div>
        )}
        <div style={{ margin: '8px 0' }}>
          <input type="file" accept=".xlsx" onChange={handleFile} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
          <button onClick={onClose}>Cancelar</button>
          <button onClick={submit} disabled={!supplierId || !file}>
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
              setSupplierId(String(s.id))
            }}
          />
        )}
      </div>
    </div>
  )
}
