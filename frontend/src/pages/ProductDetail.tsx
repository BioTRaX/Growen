// NG-HEADER: Nombre de archivo: ProductDetail.tsx
// NG-HEADER: Ubicación: frontend/src/pages/ProductDetail.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import http from '../services/http'
import { uploadProductImage, addImageFromUrl, setPrimary, lockImage, deleteImage, refreshSEO, pushTN } from '../services/images'
import { useAuth } from '../auth/AuthContext'

type Prod = {
  id: number
  title: string
  slug?: string
  stock: number
  sku_root?: string
  description_html?: string | null
  images: { id: number; url: string; alt_text?: string; title_text?: string; is_primary?: boolean; locked?: boolean; active?: boolean }[]
}

export default function ProductDetail() {
  const { id } = useParams()
  const pid = Number(id)
  const nav = useNavigate()
  const { state } = useAuth()
  const canEdit = state.role === 'admin' || state.role === 'colaborador'
  const [prod, setProd] = useState<Prod | null>(null)
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [desc, setDesc] = useState('')
  const [savingDesc, setSavingDesc] = useState(false)

  async function refresh() {
    const r = await http.get<Prod>(`/products/${pid}`)
    setProd(r.data)
    setDesc(r.data?.description_html || '')
  }

  useEffect(() => {
    if (pid) refresh()
  }, [pid])

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length || !pid) return
    setLoading(true)
    try {
      await uploadProductImage(pid, e.target.files[0])
      await refresh()
    } finally {
      setLoading(false)
    }
  }

  const onFromUrl = async () => {
    if (!url || !pid) return
    setLoading(true)
    try {
      await addImageFromUrl(pid, url)
      setUrl('')
      await refresh()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel p-4" style={{ background: '#0b0f14', color: '#e5e7eb', minHeight: '100vh' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button className="btn-dark btn-lg" onClick={() => nav(-1)}>Volver</button>
        <h2 style={{ margin: 0 }}>{prod?.title || 'Producto'}</h2>
        <div style={{ marginLeft: 'auto' }}>Stock: {prod?.stock ?? ''}</div>
      </div>

      {canEdit && (
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <label className="btn-primary">
            Subir archivo
            <input type="file" style={{ display: 'none' }} onChange={onUpload} />
          </label>
          <input className="input" placeholder="Pegar URL de imagen" value={url} onChange={(e) => setUrl(e.target.value)} />
          <button className="btn" onClick={onFromUrl} disabled={!url || loading}>Descargar</button>
          <button className="btn" onClick={async () => { await pushTN(pid); alert('Push Tiendanube encolado/ejecutado'); }}>Enviar a Tiendanube</button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, 220px)', gap: 12, marginTop: 16 }}>
        {prod?.images?.map((im) => (
          <div key={im.id} className="card" style={{ background: '#111827', padding: 8, borderRadius: 8 }}>
            <img src={im.url} alt={im.alt_text || ''} style={{ width: '100%', height: 180, objectFit: 'cover', borderRadius: 6 }} />
            <div style={{ fontSize: 12, opacity: 0.8, marginTop: 6 }}>{im.title_text || ''}</div>
            {canEdit && (
              <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                {!im.is_primary && <button className="btn-secondary" onClick={async () => { await setPrimary(pid, im.id); refresh() }}>Portada</button>}
                {!im.locked && <button className="btn-secondary" onClick={async () => { await lockImage(pid, im.id); refresh() }}>Lock</button>}
                <button className="btn-secondary" onClick={async () => { await refreshSEO(pid, im.id); refresh() }}>SEO</button>
                {!im.locked && <button className="btn" onClick={async () => { await deleteImage(pid, im.id); refresh() }}>Borrar</button>}
              </div>
            )}
          </div>
        ))}
      </div>
      {loading && <div style={{ marginTop: 8 }}>Procesando...</div>}

      {/* Ficha: Datos básicos */}
      <div className="card" style={{ background: '#111827', padding: 12, borderRadius: 8, marginTop: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Datos</div>
        <div className="row" style={{ gap: 16, flexWrap: 'wrap' }}>
          <div><span style={{ opacity: 0.7 }}>ID:</span> {prod?.id}</div>
          {prod?.slug && <div><span style={{ opacity: 0.7 }}>Slug:</span> {prod.slug}</div>}
          {prod?.sku_root && <div><span style={{ opacity: 0.7 }}>SKU:</span> {prod.sku_root}</div>}
          <div><span style={{ opacity: 0.7 }}>Stock:</span> {prod?.stock}</div>
        </div>
      </div>

      {/* Ficha: Descripción */}
      <div className="card" style={{ background: '#111827', padding: 12, borderRadius: 8, marginTop: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ fontWeight: 600 }}>Descripción</div>
          {canEdit && (
            <button
              className="btn-primary"
              style={{ marginLeft: 'auto' }}
              disabled={savingDesc}
              onClick={async () => {
                try {
                  setSavingDesc(true)
                  await http.patch(`/products/${pid}`, { description_html: desc })
                } finally {
                  setSavingDesc(false)
                }
              }}
            >{savingDesc ? 'Guardando…' : 'Guardar'}</button>
          )}
        </div>
        <div style={{ marginTop: 8 }}>
          {canEdit ? (
            <textarea className="input" rows={8} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Descripción (HTML o texto)" />
          ) : (
            <div style={{ whiteSpace: 'pre-wrap' }}>{desc || 'Sin descripción'}</div>
          )}
        </div>
      </div>

      {/* Ficha: Proveedores y precios de compra */}
      <SupplierOfferings productId={pid} />
    </div>
  )
}

function SupplierOfferings({ productId }: { productId: number }) {
  const [rows, setRows] = useState<{ supplier_item_id: number; supplier_name: string; supplier_sku: string; buy_price: number | null; updated_at?: string | null }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        setLoading(true)
        const r = await http.get(`/products-ex/products/internal/${productId}/offerings`)
        if (mounted) setRows(r.data || [])
      } catch (e: any) {
        if (mounted) setError(e?.message || 'Error')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [productId])

  return (
    <div className="card" style={{ background: '#111827', padding: 12, borderRadius: 8, marginTop: 12 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>Precios de compra y proveedores</div>
      {loading && <div>Cargando…</div>}
      {error && <div style={{ color: '#ef4444' }}>{error}</div>}
      {!loading && !error && (
        rows.length ? (
          <div style={{ overflowX: 'auto' }}>
            <table className="table w-full">
              <thead>
                <tr>
                  <th>Proveedor</th>
                  <th>SKU proveedor</th>
                  <th>Precio compra</th>
                  <th>Actualizado</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.supplier_item_id}>
                    <td>{r.supplier_name}</td>
                    <td>{r.supplier_sku}</td>
                    <td>{r.buy_price != null ? `$ ${r.buy_price.toFixed(2)}` : '-'}</td>
                    <td>{r.updated_at ? new Date(r.updated_at).toLocaleString() : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div>Sin ofertas registradas.</div>
      )}
    </div>
  )
}
