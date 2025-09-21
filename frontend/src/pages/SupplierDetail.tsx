// NG-HEADER: Nombre de archivo: SupplierDetail.tsx
// NG-HEADER: Ubicación: frontend/src/pages/SupplierDetail.tsx
// NG-HEADER: Descripción: Página de detalle y edición de proveedor; incluye gestión de archivos
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import AppToolbar from '../components/AppToolbar'
import { getSupplier, updateSupplier, Supplier, listSupplierFiles, uploadSupplierFile, SupplierFileMeta } from '../services/suppliers'
import { PATHS } from '../routes/paths'
import { useTheme } from '../theme/ThemeProvider'

export default function SupplierDetailPage() {
  const { id } = useParams<{ id: string }>()
  const supplierId = Number(id)
  const [data, setData] = useState<Supplier | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<any>({})
  const [edit, setEdit] = useState(false)
  const [files, setFiles] = useState<SupplierFileMeta[]>([])
  const [filesLoading, setFilesLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [notes, setNotes] = useState('')
  const theme = useTheme()

  useEffect(() => {
    (async () => {
      try {
        const sup = await getSupplier(supplierId)
        setData(sup)
        setForm({
          slug: sup.slug,
          name: sup.name,
          location: sup.location || '',
          contact_name: sup.contact_name || '',
          contact_email: sup.contact_email || '',
          contact_phone: sup.contact_phone || '',
          notes: sup.notes || ''
        })
      } catch (e: any) {
        setError(e.message || 'Error cargando proveedor')
      } finally {
        setLoading(false)
      }
    })()
  }, [supplierId])

  const loadFiles = async () => {
    setFilesLoading(true)
    try {
      const list = await listSupplierFiles(supplierId)
      setFiles(list)
    } catch (e: any) {
      setUploadError(e.message || 'Error listando archivos')
    } finally {
      setFilesLoading(false)
    }
  }

  useEffect(() => {
    if (!isNaN(supplierId)) {
      loadFiles()
    }
  }, [supplierId])

  const doSave = async () => {
    setSaving(true); setError(null)
    try {
      const updated = await updateSupplier(supplierId, form)
      setData(updated)
      setEdit(false)
    } catch (e: any) {
      setError(e.message || 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  const onUpload = async (ev: React.ChangeEvent<HTMLInputElement>) => {
    if (!ev.target.files || ev.target.files.length === 0) return
    const f = ev.target.files[0]
    setUploading(true)
    setUploadError(null)
    try {
      const meta = await uploadSupplierFile(supplierId, f, notes.trim() || undefined)
      // Si duplicado, mostrar aviso pero no duplicar en la lista
      if (meta.duplicate) {
        setUploadError('Archivo ya existe (hash coincidente)')
      }
      setNotes('')
      await loadFiles()
    } catch (e: any) {
      setUploadError(e.message || 'Error subiendo archivo')
    } finally {
      setUploading(false)
      ev.target.value = '' // reset input
    }
  }

  if (loading) return (<><AppToolbar /><div className="panel p-4" style={{ maxWidth: 1000, margin: '16px auto', background: theme.bg, color: theme.text }}>Cargando...</div></>)
  if (!data) return (<><AppToolbar /><div className="panel p-4" style={{ maxWidth: 1000, margin: '16px auto', background: theme.bg, color: theme.text }}>No encontrado <Link to={PATHS.suppliers}>Volver</Link></div></>)

  return (
    <>
      <AppToolbar />
      <div className="panel p-5" style={{ maxWidth: 1000, margin: '16px auto', background: theme.bg, color: theme.text }}>
        {/** Estilos base para inputs/textarea según tema */}
        {(() => null)()}
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>Proveedor: {data.name}</h2>
          <div className="row" style={{ gap: 8 }}>
            {!edit && <button className="btn-primary" onClick={() => setEdit(true)}>Editar</button>}
            {edit && <button className="btn-secondary" onClick={() => { setEdit(false); setForm({ ...form, name: data.name }) }}>Cancelar</button>}
            <Link to={PATHS.suppliers} className="btn-secondary" style={{ textDecoration: 'none' }}>Volver</Link>
          </div>
        </div>
        {error && <div className="alert-error" style={{ marginTop: 8 }}>{error}</div>}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 24, marginTop: 16 }}>
          <div className="card" style={{ background: theme.card, padding: 16, border: `1px solid ${theme.border}`, borderRadius: 8 }}>
            <h3 style={{ marginTop: 0 }}>Datos</h3>
            <label>Slug
              <input
                disabled
                value={form.slug}
                style={{
                  background: theme.name === 'dark' ? '#0f0f0f' : '#fff',
                  color: theme.text,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 6,
                  padding: '6px 8px',
                }}
              />
            </label>
            <label>Nombre
              <input
                disabled={!edit}
                value={form.name}
                onChange={e => setForm((f: any) => ({ ...f, name: e.target.value }))}
                style={{
                  background: !edit ? (theme.name === 'dark' ? '#0f0f0f' : '#f9fafb') : (theme.name === 'dark' ? '#111' : '#fff'),
                  color: theme.text,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 6,
                  padding: '6px 8px',
                }}
              />
            </label>
            <label>Ubicación
              <input
                disabled={!edit}
                value={form.location}
                onChange={e => setForm((f: any) => ({ ...f, location: e.target.value }))}
                style={{
                  background: !edit ? (theme.name === 'dark' ? '#0f0f0f' : '#f9fafb') : (theme.name === 'dark' ? '#111' : '#fff'),
                  color: theme.text,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 6,
                  padding: '6px 8px',
                }}
              />
            </label>
            {edit && <button className="btn-primary" disabled={saving} onClick={doSave}>{saving ? 'Guardando...' : 'Guardar cambios'}</button>}
          </div>
          <div className="card" style={{ background: theme.card, padding: 16, border: `1px solid ${theme.border}`, borderRadius: 8 }}>
            <h3 style={{ marginTop: 0 }}>Contacto</h3>
            <label>Nombre
              <input
                disabled={!edit}
                value={form.contact_name}
                onChange={e => setForm((f: any) => ({ ...f, contact_name: e.target.value }))}
                style={{
                  background: !edit ? (theme.name === 'dark' ? '#0f0f0f' : '#f9fafb') : (theme.name === 'dark' ? '#111' : '#fff'),
                  color: theme.text,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 6,
                  padding: '6px 8px',
                }}
              />
            </label>
            <label>Email
              <input
                disabled={!edit}
                value={form.contact_email}
                onChange={e => setForm((f: any) => ({ ...f, contact_email: e.target.value }))}
                style={{
                  background: !edit ? (theme.name === 'dark' ? '#0f0f0f' : '#f9fafb') : (theme.name === 'dark' ? '#111' : '#fff'),
                  color: theme.text,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 6,
                  padding: '6px 8px',
                }}
              />
            </label>
            <label>Teléfono
              <input
                disabled={!edit}
                value={form.contact_phone}
                onChange={e => setForm((f: any) => ({ ...f, contact_phone: e.target.value }))}
                style={{
                  background: !edit ? (theme.name === 'dark' ? '#0f0f0f' : '#f9fafb') : (theme.name === 'dark' ? '#111' : '#fff'),
                  color: theme.text,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 6,
                  padding: '6px 8px',
                }}
              />
            </label>
          </div>
          <div className="card" style={{ background: theme.card, padding: 16, border: `1px solid ${theme.border}`, borderRadius: 8 }}>
            <h3 style={{ marginTop: 0 }}>Notas</h3>
            <textarea
              rows={12}
              disabled={!edit}
              value={form.notes}
              onChange={e => setForm((f: any) => ({ ...f, notes: e.target.value }))}
              style={{
                background: !edit ? (theme.name === 'dark' ? '#0f0f0f' : '#f9fafb') : (theme.name === 'dark' ? '#111' : '#fff'),
                color: theme.text,
                border: `1px solid ${theme.border}`,
                borderRadius: 6,
                padding: 8,
                minHeight: 180,
              }}
            />
          </div>
          <div className="card" style={{ background: theme.card, padding: 16, border: `1px solid ${theme.border}`, borderRadius: 8 }}>
            <h3 style={{ marginTop: 0 }}>Archivos</h3>
            <p style={{ marginTop: 0, fontSize: 12, color: theme.name === 'dark' ? '#bbb' : '#555' }}>Formatos permitidos: pdf, txt, csv, xls, xlsx, ods, png, jpg, jpeg, webp (max 10MB)</p>
            {uploadError && <div className="alert-error" style={{ marginBottom: 8 }}>{uploadError}</div>}
            <label style={{ display: 'block', marginBottom: 8 }}>Notas (opcional)
              <input
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Descripción breve"
                style={{
                  background: theme.name === 'dark' ? '#111' : '#fff',
                  color: theme.text,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 6,
                  padding: '6px 8px',
                }}
              />
            </label>
            <input type="file" onChange={onUpload} disabled={uploading} />
            {uploading && <div style={{ fontSize: 12, marginTop: 4 }}>Subiendo...</div>}
            <div style={{ marginTop: 12 }}>
              {filesLoading ? <div>Cargando archivos...</div> : (
                files.length === 0 ? <div style={{ fontSize: 13, color: theme.name === 'dark' ? '#999' : '#666' }}>Sin archivos</div> : (
                  <table className="table" style={{ width: '100%', fontSize: 13 }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left' }}>Nombre</th>
                        <th>Tamaño</th>
                        <th>Fecha</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {files.map(f => {
                        const sizeKb = f.size_bytes ? (f.size_bytes / 1024).toFixed(1) + ' KB' : ''
                        return (
                          <tr key={f.id}>
                            <td title={f.original_name}>{f.original_name}</td>
                            <td style={{ textAlign: 'center' }}>{sizeKb}</td>
                            <td style={{ textAlign: 'center' }}>{new Date(f.uploaded_at).toLocaleString()}</td>
                            <td style={{ textAlign: 'right' }}>
                              <button onClick={() => window.open(`${import.meta.env.VITE_API_BASE || ''}/suppliers/files/${f.id}/download`, '_blank')} className="btn-secondary" style={{ fontSize: 12, padding: '2px 6px' }}>Descargar</button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
