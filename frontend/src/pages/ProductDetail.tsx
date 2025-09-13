// NG-HEADER: Nombre de archivo: ProductDetail.tsx
// NG-HEADER: Ubicación: frontend/src/pages/ProductDetail.tsx
// NG-HEADER: Descripción: Ficha de producto con galería, estilo y acciones (Minimal Dark + upload Admin)
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import http from '../services/http'
import { uploadProductImage, addImageFromUrl, setPrimary, lockImage, deleteImage, refreshSEO, pushTN, removeBg, watermark } from '../services/images'
import { serviceStatus, startService, tailServiceLogs, ServiceLogItem } from '../services/servicesAdmin'
import { useAuth } from '../auth/AuthContext'
import { getProductDetailStylePref, putProductDetailStylePref, ProductDetailStyle } from '../services/productsEx'
import { showToast } from '../components/Toast'

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
  const isAdmin = state.role === 'admin'
  const canEdit = isAdmin || state.role === 'colaborador'

  const [prod, setProd] = useState<Prod | null>(null)
  const [desc, setDesc] = useState('')
  const [savingDesc, setSavingDesc] = useState(false)
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadPct, setUploadPct] = useState(0)
  const [gateImgNeeded, setGateImgNeeded] = useState(false)
  const [gateImgBusy, setGateImgBusy] = useState(false)
  const [gateImgLogs, setGateImgLogs] = useState<ServiceLogItem[]>([])
  const [styleVariant, setStyleVariant] = useState<ProductDetailStyle>('default')
  const [imgDiag, setImgDiag] = useState<{ action: string; created_at?: string; meta?: any; image_id?: number }[]>([])
  const [prodDiag, setProdDiag] = useState<{ action: string; created_at?: string; meta?: any }[]>([])

  const theme = useMemo(() => ({
    bg: styleVariant === 'minimalDark' ? '#0b0f14' : '#0d1117',
    card: styleVariant === 'minimalDark' ? 'rgba(17,24,39,0.7)' : '#111827',
    border: '#1f2937',
    title: '#f8fafc',
    text: '#e5e7eb',
    accentGreen: '#22c55e',
    accentPink: '#f0f',
    radius: styleVariant === 'minimalDark' ? 14 : 8,
  }), [styleVariant])

  async function refresh() {
    const r = await http.get<Prod>(`/products/${pid}`)
    setProd(r.data)
    setDesc(r.data?.description_html || '')
  }

  useEffect(() => {
    if (pid) refresh()
  }, [pid])

  // Preferencia de estética de ficha
  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const r = await getProductDetailStylePref()
        if ((r as any)?.style && mounted) setStyleVariant((r as any).style as ProductDetailStyle)
        else {
          const local = (localStorage.getItem('ng_product_detail_style') || 'default') as ProductDetailStyle
          if (mounted) setStyleVariant(local)
        }
      } catch {
        const local = (localStorage.getItem('ng_product_detail_style') || 'default') as ProductDetailStyle
        if (mounted) setStyleVariant(local)
      }
    })()
    return () => { mounted = false }
  }, [])

  // Validaciones de imagen
  async function validateImage(file: File): Promise<string | null> {
    const allowed = ['image/jpeg', 'image/png', 'image/webp']
    if (!allowed.includes(file.type)) return 'Formato no permitido (JPG/PNG/WebP)'
    if (file.size > 10 * 1024 * 1024) return 'Tamaño máximo 10 MB'
    const blobUrl = URL.createObjectURL(file)
    try {
      const dim = await new Promise<{ w: number; h: number }>((resolve, reject) => {
        const img = new Image()
        img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight })
        img.onerror = () => reject(new Error('No se pudo leer la imagen'))
        img.src = blobUrl
      })
      if (dim.w < 600 || dim.h < 600) return 'La imagen debe ser de al menos 600×600'
      return null
    } finally {
      URL.revokeObjectURL(blobUrl)
    }
  }

  const onUploadInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return
    setUploadFile(e.target.files[0])
  }

  const doUpload = async () => {
    if (!pid || !uploadFile) return
    const err = await validateImage(uploadFile)
    if (err) { showToast('error', err); return }
    setLoading(true)
    setUploadPct(0)
    try {
      await uploadProductImage(pid, uploadFile, (p) => setUploadPct(p))
      showToast('success', 'Imagen subida')
      setUploadOpen(false)
      setUploadFile(null)
      await refresh()
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Error al subir imagen'
      showToast('error', String(msg))
    } finally {
      setLoading(false)
      setUploadPct(0)
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

  async function ensureImageProcessing(): Promise<boolean> {
    try {
      const st = await serviceStatus('image_processing')
      if ((st?.status || '') !== 'running') {
        setGateImgNeeded(true)
        try { setGateImgLogs(await tailServiceLogs('image_processing', 80)) } catch {}
        return false
      }
      return true
    } catch {
      return true
    }
  }

  async function startImageProcessingNow() {
    setGateImgBusy(true)
    try {
      await startService('image_processing')
      await new Promise(r => setTimeout(r, 600))
      setGateImgNeeded(false)
      alert('Procesador de imágenes iniciado')
    } catch (e) {
      alert('No se pudo iniciar image_processing (ver logs)')
      try { setGateImgLogs(await tailServiceLogs('image_processing', 120)) } catch {}
    } finally {
      setGateImgBusy(false)
    }
  }

  const primary = (prod?.images || []).find(i => i.is_primary) || (prod?.images || [])[0]
  const others = (prod?.images || []).filter(i => i.id !== primary?.id)

  return (
    <div className="panel p-4" style={{ background: theme.bg, color: theme.text, minHeight: '100vh' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button className="btn-dark btn-lg" onClick={() => nav(-1)}>Volver</button>
        <h2 style={{ margin: 0, color: theme.title }}>{prod?.title || 'Producto'}</h2>
        <div style={{ marginLeft: 'auto' }}>Stock: {prod?.stock ?? ''}</div>
      </div>

      {/* Selector de estética */}
      <div className="row" style={{ gap: 8, marginTop: 10, alignItems: 'center' }}>
        <span style={{ fontSize: 12, opacity: .8 }}>Estética:</span>
        <select
          className="select"
          value={styleVariant}
          onChange={async (e) => {
            const v = e.target.value as ProductDetailStyle
            setStyleVariant(v)
            try { await putProductDetailStylePref(v) } catch {}
            try { localStorage.setItem('ng_product_detail_style', v) } catch {}
          }}
          style={{ borderColor: theme.accentGreen }}
        >
          <option value="default">Default</option>
          <option value="minimalDark">Minimal Dark</option>
        </select>
      </div>

      {(isAdmin || canEdit) && (
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          {isAdmin && (
            <button className="btn" onClick={() => setUploadOpen(true)} style={{ borderColor: theme.accentPink, color: '#f5d0fe' }}>Subir imagen</button>
          )}
          <input className="input" placeholder="Pegar URL de imagen" value={url} onChange={(e) => setUrl(e.target.value)} />
          <button className="btn" onClick={onFromUrl} disabled={!url || loading}>Descargar</button>
          <button className="btn" onClick={async () => { await pushTN(pid); alert('Push Tiendanube encolado/ejecutado'); }}>Enviar a Tiendanube</button>
          <button className="btn" onClick={async () => { try { const a = await http.get(`/products/${pid}/images/audit-logs`, { params: { limit: 50 } }); setImgDiag(a.data.items || []); const b = await http.get(`/catalog/products/${pid}/audit-logs`, { params: { limit: 50 } }); setProdDiag(b.data.items || []) } catch (e: any) { showToast('error', e?.response?.data?.detail || 'No se pudieron obtener diagnósticos') } }}>Ver diagnósticos</button>
        </div>
      )}

      {/* Galería principal + secundarias */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 16, marginTop: 16, alignItems: 'start' }}>
        <div className="card" style={{ background: theme.card, padding: 10, borderRadius: theme.radius, border: `1px solid ${theme.border}`, minHeight: 320 }}>
          {primary ? (
            <img src={primary.url} alt={primary.alt_text || ''} style={{ width: '100%', height: 400, objectFit: 'cover', borderRadius: 6 }} />
          ) : (
            <div style={{ padding: 16, opacity: .7 }}>Sin imagen principal</div>
          )}
          {primary && canEdit && (
            <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
              {!primary.locked && <button className="btn-secondary" onClick={async () => { const ok = await ensureImageProcessing(); if (!ok) return; await watermark(pid, primary.id); refresh() }}>Watermark</button>}
              {!primary.locked && <button className="btn-secondary" onClick={async () => { const ok = await ensureImageProcessing(); if (!ok) return; await removeBg(pid, primary.id); refresh() }}>Quitar fondo</button>}
              <button className="btn-secondary" onClick={async () => { const ok = await ensureImageProcessing(); if (!ok) return; await refreshSEO(pid, primary.id); refresh() }}>SEO</button>
            </div>
          )}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 12 }}>
          {others.slice(0, 2).map((im) => (
            <div key={im.id} className="card" style={{ background: theme.card, padding: 8, borderRadius: theme.radius, border: `1px solid ${theme.border}` }}>
              <img src={im.url} alt={im.alt_text || ''} style={{ width: '100%', height: 190, objectFit: 'cover', borderRadius: 6 }} />
              {canEdit && (
                <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  {!im.is_primary && <button className="btn-secondary" onClick={async () => { await setPrimary(pid, im.id); refresh() }}>Portada</button>}
                  <button className="btn-secondary" onClick={async () => { await lockImage(pid, im.id); refresh() }}>{im.locked ? 'Unlock' : 'Lock'}</button>
                  <button className="btn" onClick={async () => { await deleteImage(pid, im.id); refresh() }}>Borrar</button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {loading && <div style={{ marginTop: 8 }}>Procesando...</div>}

      {/* Datos básicos */}
      <div className="card" style={{ background: theme.card, padding: 12, borderRadius: theme.radius, border: `1px solid ${theme.border}`, marginTop: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Datos</div>
        <div className="row" style={{ gap: 16, flexWrap: 'wrap' }}>
          <div><span style={{ opacity: 0.7 }}>ID:</span> {prod?.id}</div>
          {prod?.slug && <div><span style={{ opacity: 0.7 }}>Slug:</span> {prod.slug}</div>}
          {prod?.sku_root && <div><span style={{ opacity: 0.7 }}>SKU:</span> {prod.sku_root}</div>}
          <div><span style={{ opacity: 0.7 }}>Stock:</span> {prod?.stock}</div>
          <div><span style={{ opacity: 0.7 }}>Tiene imagen:</span> {(prod?.images?.length || 0) > 0 ? 'Sí' : 'No'}</div>
        </div>
      </div>

      {/* Descripción */}
      <div className="card" style={{ background: theme.card, padding: 12, borderRadius: theme.radius, border: `1px solid ${theme.border}`, marginTop: 12 }}>
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
                  showToast('success', 'Descripción guardada')
                } catch (e: any) {
                  showToast('error', e?.response?.data?.detail || 'No se pudo guardar la descripción')
                } finally {
                  setSavingDesc(false)
                }
              }}
            >{savingDesc ? 'Guardando...' : 'Guardar'}</button>
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

      {/* Proveedores y precios */}
      <SupplierOfferings productId={pid} theme={theme} />

      {(isAdmin || canEdit) && (imgDiag.length > 0 || prodDiag.length > 0) && (
        <div className="card" style={{ background: theme.card, padding: 12, borderRadius: theme.radius, border: `1px solid ${theme.border}`, marginTop: 12 }}>
          <details open>
            <summary>Diagnóstico reciente</summary>
            <div className="row" style={{ gap: 12, marginTop: 8, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 260 }}>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>Imágenes</div>
                <ul style={{ fontSize: 12, lineHeight: 1.35, maxHeight: 220, overflow: 'auto' }}>
                  {imgDiag.map((l, i) => (
                    <li key={i} style={{ color: '#9ca3af' }}>[{l.created_at}] {l.action} — {JSON.stringify(l.meta || {})}</li>
                  ))}
                </ul>
              </div>
              <div style={{ flex: 1, minWidth: 260 }}>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>Producto</div>
                <ul style={{ fontSize: 12, lineHeight: 1.35, maxHeight: 220, overflow: 'auto' }}>
                  {prodDiag.map((l, i) => (
                    <li key={i} style={{ color: '#9ca3af' }}>[{l.created_at}] {l.action} — {JSON.stringify(l.meta || {})}</li>
                  ))}
                </ul>
              </div>
            </div>
          </details>
        </div>
      )}

      {/* Puerta para iniciar image_processing */}
      {gateImgNeeded && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
          <div className="panel" style={{ padding: 16, minWidth: 460 }}>
            <h4 style={{ marginTop: 0 }}>Procesador de imágenes apagado</h4>
            <p className="text-sm" style={{ opacity: 0.9 }}>Esta acción requiere "Procesado de imágenes" encendido. ¿Iniciarlo ahora?</p>
            <div className="row" style={{ gap: 8, marginTop: 6 }}>
              <button className="btn-secondary" onClick={() => setGateImgNeeded(false)} disabled={gateImgBusy}>Cancelar</button>
              <button className="btn-primary" onClick={startImageProcessingNow} disabled={gateImgBusy}>{gateImgBusy ? 'Iniciando...' : 'Iniciar ahora'}</button>
            </div>
            <details style={{ marginTop: 8 }}>
              <summary>Ver logs recientes</summary>
              <ul style={{ maxHeight: 160, overflow: 'auto', fontSize: 12 }}>
                {gateImgLogs.map((l, i) => (
                  <li key={i}>[{l.level}] {l.created_at} — {l.action} — {l.ok ? 'OK' : 'FAIL'} — {(l as any).error || (l as any)?.payload?.detail || ''}</li>
                ))}
              </ul>
              <button className="btn" onClick={async () => { try { setGateImgLogs(await tailServiceLogs('image_processing', 120)) } catch {} }}>Actualizar logs</button>
            </details>
          </div>
        </div>
      )}

      {/* Modal de subida */}
      {uploadOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 70 }}>
          <div className="panel" style={{ padding: 16, minWidth: 420 }}>
            <h4 style={{ marginTop: 0 }}>Subir imagen</h4>
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={onUploadInput} />
            {uploadPct > 0 && (
              <div style={{ marginTop: 8 }}>
                <div style={{ height: 8, background: '#1f2937', borderRadius: 6 }}>
                  <div style={{ width: `${uploadPct}%`, height: 8, background: theme.accentPink, borderRadius: 6, transition: 'width .2s' }} />
                </div>
                <div style={{ fontSize: 12, opacity: .8, marginTop: 4 }}>{uploadPct}%</div>
              </div>
            )}
            <div className="row" style={{ gap: 8, marginTop: 10 }}>
              <button className="btn-secondary" onClick={() => { if (!loading) { setUploadOpen(false); setUploadFile(null); setUploadPct(0) } }} disabled={loading}>Cancelar</button>
              <button className="btn-primary" onClick={doUpload} disabled={!uploadFile || loading}>{loading ? 'Subiendo...' : 'Subir'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function SupplierOfferings({ productId, theme }: { productId: number; theme: { card: string; border: string } }) {
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
    <div className="card" style={{ background: theme.card, padding: 12, borderRadius: 14, border: `1px solid ${theme.border}`, marginTop: 12 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>Precios de compra y proveedores</div>
      {loading && <div>Cargando...</div>}
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

