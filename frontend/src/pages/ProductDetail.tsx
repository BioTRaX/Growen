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
import { getProductDetailStylePref, putProductDetailStylePref, ProductDetailStyle, updateSalePrice, updateSupplierBuyPrice } from '../services/productsEx'
import { listProductVariants, linkSupplierProduct, ProductVariantItem, patchProduct, updateVariantSku } from '../services/products'
import { listCategories, Category } from '../services/categories'
import SupplierAutocomplete from '../components/supplier/SupplierAutocomplete'
import type { SupplierSearchItem } from '../services/suppliers'
import { showToast } from '../components/Toast'

type Prod = {
  id: number
  title: string
  slug?: string
  stock: number
  sku_root?: string
  description_html?: string | null
  category_path?: string | null
  images: { id: number; url: string; alt_text?: string; title_text?: string; is_primary?: boolean; locked?: boolean; active?: boolean }[]
  canonical_product_id?: number | null
  canonical_sale_price?: number | null
  canonical_sku?: string | null
  canonical_ng_sku?: string | null
  canonical_name?: string | null
  // Campos enriquecidos opcionales (si backend los provee en el futuro)
  weight_kg?: number | null
  height_cm?: number | null
  width_cm?: number | null
  depth_cm?: number | null
  market_price_reference?: number | null
  enrichment_sources_url?: string | null
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
  const [editingSale, setEditingSale] = useState(false)
  const [saleVal, setSaleVal] = useState('')
  const [offeringsTick, setOfferingsTick] = useState(0)
  const [linkOpen, setLinkOpen] = useState(false)
  const [linkBusy, setLinkBusy] = useState(false)
  const [variants, setVariants] = useState<ProductVariantItem[]>([])
  const [selectedVariantId, setSelectedVariantId] = useState<number | null>(null)
  const [supplierSel, setSupplierSel] = useState<SupplierSearchItem | null>(null)
  const [supplierSku, setSupplierSku] = useState('')
  const [supplierTitle, setSupplierTitle] = useState('')
  const [categories, setCategories] = useState<Category[]>([])
  const [savingCat, setSavingCat] = useState(false)
  const [skuEditing, setSkuEditing] = useState<{ id: number; val: string } | null>(null)
  const [selectedCatId, setSelectedCatId] = useState<string>('')
  const [techEditing, setTechEditing] = useState<null | { field: 'weight_kg'|'height_cm'|'width_cm'|'depth_cm'|'market_price_reference'; val: string }>(null)
  const [srcOpen, setSrcOpen] = useState(false)
  const [srcLoading, setSrcLoading] = useState(false)
  const [srcText, setSrcText] = useState<string>('')
  const [iaMenuOpen, setIaMenuOpen] = useState(false)

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

  useEffect(() => {
    let mounted = true
    ;(async () => {
      if (!pid) return
      try {
        const v = await listProductVariants(pid)
        if (mounted) setVariants(v)
        if (mounted && v.length > 0) setSelectedVariantId(v[0].id)
      } catch {
        if (mounted) setVariants([])
      }
    })()
    return () => { mounted = false }
  }, [pid])

  // Cargar categorías para selector
  useEffect(() => {
    let mounted = true
    ;(async () => {
      try { const cs = await listCategories(); if (mounted) setCategories(cs) } catch {}
    })()
    return () => { mounted = false }
  }, [])

  // Derivar selección actual por path si existe
  useEffect(() => {
    if (!prod) { setSelectedCatId(''); return }
    const p = (prod.category_path || '').trim()
    if (!p) { setSelectedCatId(''); return }
    const match = categories.find(c => (c.path || '').trim() === p)
    setSelectedCatId(match ? String(match.id) : '')
  }, [prod, categories])

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

  const isDescDirty = useMemo(() => {
    if (!prod) return false
    // Normalizar null/undefined/empty string para comparación
    const currentDesc = desc || ''
    const originalDesc = prod.description_html || ''
    return currentDesc !== originalDesc
  }, [desc, prod])

  // Enriquecer con IA: dispara POST al backend y refresca datos
  const handleEnrich = async () => {
    if (isDescDirty && !window.confirm('La descripción tiene cambios manuales que se perderán. ¿Deseas sobrescribirlos con el enriquecimiento de IA?')) {
      return
    }
    try {
      setLoading(true)
      // Nota: el cliente http ya incluye el prefijo base (ej.: /api)
      await http.post(`/products/${pid}/enrich`)
      showToast('success', 'Producto enriquecido con IA')
      await refresh()
    } catch (e: any) {
      showToast('error', e?.response?.data?.detail || 'Error al enriquecer producto')
    } finally {
      setLoading(false)
    }
  }

  // Reenriquecer con IA (force=true)
  const handleReenrich = async () => {
    if (isDescDirty && !window.confirm('La descripción tiene cambios manuales que se perderán. ¿Deseas sobrescribirlos con el enriquecimiento de IA?')) {
      return
    }
    try {
      setLoading(true)
      await http.post(`/products/${pid}/enrich?force=true`)
      showToast('success', 'Reenriquecimiento ejecutado')
      await refresh()
    } catch (e: any) {
      showToast('error', e?.response?.data?.detail || 'Error al reenriquecer')
    } finally {
      setLoading(false)
      setIaMenuOpen(false)
    }
  }

  // Limpiar enriquecimiento IA
  const handleLimpiarIA = async () => {
    try {
      setLoading(true)
      await http.delete(`/products/${pid}/enrichment`)
      showToast('success', 'Enriquecimiento borrado')
      await refresh()
    } catch (e: any) {
      showToast('error', e?.response?.data?.detail || 'No se pudo borrar el enriquecimiento')
    } finally {
      setLoading(false)
      setIaMenuOpen(false)
    }
  }

  function parseDecimalInput(s: string): number | null {
    if (!s) return null
    const x = s.replace(/\s+/g, '').replace(',', '.')
    const num = Number(x)
    if (!isFinite(num) || num <= 0) return null
    return Math.round(num * 100) / 100
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
          <button className="btn" onClick={() => { setSupplierSel(null); setSupplierSku(''); setSupplierTitle(''); setLinkOpen(true) }}>Agregar SKU de proveedor</button>
          {canEdit && prod?.title && (
            <button
              className="btn"
              onClick={handleEnrich}
              disabled={loading}
              style={{ borderColor: theme.accentPink, color: '#f5d0fe' }}
            >
              {loading ? 'Enriqueciendo...' : 'Enriquecer con IA'}
            </button>
          )}
          {canEdit && prod?.title && prod?.enrichment_sources_url && (
            <div style={{ position: 'relative' }}>
              <button
                className="btn"
                onClick={() => setIaMenuOpen(v => !v)}
                disabled={loading}
                style={{ borderColor: theme.accentPink, color: '#f5d0fe' }}
              >
                Acciones IA ▾
              </button>
              {iaMenuOpen && (
                <div className="panel" style={{ position: 'absolute', top: '110%', right: 0, zIndex: 50, minWidth: 220, padding: 6 }}>
                  <button className="btn w-full" onClick={handleReenrich} disabled={loading}>Reenriquecer</button>
                  <button className="btn w-full" onClick={handleLimpiarIA} disabled={loading} style={{ color: '#ef4444', borderColor: '#ef4444', marginTop: 6 }}>Borrar enriquecimiento</button>
                </div>
              )}
            </div>
          )}
          {canEdit && prod?.enrichment_sources_url && (
            <button className="btn" onClick={async () => {
              setSrcOpen(true)
              setSrcLoading(true)
              setSrcText('')
              try {
                const r = await fetch(prod.enrichment_sources_url!)
                const txt = await r.text()
                setSrcText(txt)
              } catch (e: any) {
                setSrcText(e?.message || 'No se pudieron cargar las fuentes')
              } finally {
                setSrcLoading(false)
              }
            }}>📄 Fuentes consultadas</button>
          )}
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

      {/* Descripción enriquecida */}
      <div className="card" style={{ background: theme.card, padding: 12, borderRadius: theme.radius, border: `1px solid ${theme.border}`, marginTop: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ fontWeight: 600 }}>Descripción enriquecida</div>
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

      {/* Datos básicos */}
      <div className="card" style={{ background: theme.card, padding: 12, borderRadius: theme.radius, border: `1px solid ${theme.border}`, marginTop: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Datos</div>
        <div className="row" style={{ gap: 16, flexWrap: 'wrap' }}>
          <div><span style={{ opacity: 0.7 }}>ID:</span> {prod?.id}</div>
          {prod?.slug && <div><span style={{ opacity: 0.7 }}>Slug:</span> {prod.slug}</div>}
            {(prod?.canonical_sku || prod?.sku_root) && (
              <div title={prod?.canonical_sku ? 'Si hay canónico, se muestra su SKU (preferido)' : 'SKU propio del producto interno'}>
                <span style={{ opacity: 0.7 }}>SKU:</span> {prod?.canonical_sku || prod?.sku_root}
              </div>
            )}
          <div><span style={{ opacity: 0.7 }}>Stock:</span> {prod?.stock}</div>
          <div><span style={{ opacity: 0.7 }}>Tiene imagen:</span> {(prod?.images?.length || 0) > 0 ? 'Sí' : 'No'}</div>
          {prod?.canonical_product_id ? (
            <div>
              <span style={{ opacity: 0.7 }}>Precio venta:</span>{' '}
              {canEdit ? (
                editingSale ? (
                  <>
                    <input className="input" style={{ width: 120 }} value={saleVal} onChange={(e) => setSaleVal(e.target.value)} onKeyDown={async (e) => { if (e.key === 'Enter') { const v = parseDecimalInput(saleVal); if (v == null) { showToast('error', 'Valor inválido'); return } try { await updateSalePrice(prod.canonical_product_id!, v); await refresh(); showToast('success', 'Precio guardado'); setEditingSale(false) } catch (err: any) { showToast('error', err?.message || 'Error') } } if (e.key === 'Escape') setEditingSale(false) }} onBlur={async () => { const v = parseDecimalInput(saleVal); if (v == null) { showToast('error', 'Valor inválido'); return } try { await updateSalePrice(prod.canonical_product_id!, v); await refresh(); showToast('success', 'Precio guardado'); setEditingSale(false) } catch (err: any) { showToast('error', err?.message || 'Error') } }} />
                  </>
                ) : (
                  <>
                    <span>{prod?.canonical_sale_price != null ? `$ ${Number(prod.canonical_sale_price).toFixed(2)}` : '-'}</span>
                    <button className="btn-secondary" style={{ marginLeft: 6 }} onClick={() => { setEditingSale(true); setSaleVal(String(prod?.canonical_sale_price ?? '')) }}>✎</button>
                  </>
                )
              ) : (
                <span>{prod?.canonical_sale_price ?? '-'}</span>
              )}
            </div>
          ) : null}
        </div>
        {/* Selector de categoría */}
        <div className="row" style={{ gap: 8, marginTop: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ fontWeight: 600 }}>Categoría</div>
          <div className="row" style={{ gap: 8, alignItems: 'center' }}>
            <span style={{ opacity: .8, fontSize: 12 }}>Actual:</span>
            <span>{prod?.category_path || 'Sin categoría'}</span>
          </div>
          {canEdit && (
            <>
              <select className="select" value={selectedCatId} onChange={(e) => setSelectedCatId(e.target.value)}>
                <option value="">Seleccionar categoría…</option>
                {categories.map(c => (
                  <option key={c.id} value={String(c.id)}>{c.path || c.name}</option>
                ))}
              </select>
              <button className="btn-primary" disabled={savingCat || !prod} onClick={async () => {
                const cid = selectedCatId ? Number(selectedCatId) : null
                if (cid == null) { showToast('error', 'Seleccione una categoría'); return }
                setSavingCat(true)
                try {
                  await patchProduct(pid, { category_id: cid })
                  await refresh()
                  showToast('success', 'Categoría guardada')
                } catch (e: any) {
                  showToast('error', e?.message || 'No se pudo guardar la categoría')
                } finally {
                  setSavingCat(false)
                }
              }}>{savingCat ? 'Guardando...' : 'Guardar'}</button>
            </>
          )}
        </div>
      </div>

      {/* Datos técnicos (sólo Admin/Colab). Edit-in-place: intenta PATCH y si backend no soporta, informa. */}
      {canEdit && (
        <div className="card" style={{ background: theme.card, padding: 12, borderRadius: theme.radius, border: `1px solid ${theme.border}`, marginTop: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Datos técnicos</div>
          <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
            {([
              { key: 'weight_kg', label: 'Peso KG', isNumber: true },
              { key: 'height_cm', label: 'Alto CM', isNumber: true },
              { key: 'width_cm', label: 'Ancho CM', isNumber: true },
              { key: 'depth_cm', label: 'Profundidad CM', isNumber: true },
              { key: 'market_price_reference', label: 'Valor de mercado estimado', isNumber: false },
            ] as const).map((f) => (
              <div key={f.key} style={{ minWidth: 220 }}>
                <span style={{ opacity: .8, fontSize: 12 }}>{f.label}</span>
                <div>
                  {techEditing?.field === f.key ? (
                    <input
                      className="input"
                      autoFocus
                      value={techEditing.val}
                      onChange={(e) => setTechEditing({ field: f.key, val: e.target.value })}
                      onKeyDown={async (e) => {
                        if (e.key === 'Enter') {
                          let payload: any = {}
                          if (f.isNumber) {
                            const v = parseDecimalInput(techEditing.val)
                            if (v == null) { showToast('error', 'Valor inválido'); return }
                            payload[f.key] = v
                          } else {
                            payload[f.key] = (techEditing.val || '').trim()
                          }
                          try {
                            await http.patch(`/products/${pid}`, payload)
                            showToast('success', 'Campo guardado')
                            await refresh()
                          } catch (err: any) {
                            showToast('error', err?.response?.data?.detail || 'Campo no soportado aún en backend')
                          } finally {
                            setTechEditing(null)
                          }
                        }
                        if (e.key === 'Escape') setTechEditing(null)
                      }}
                      onBlur={async () => {
                        // Guardar en blur con misma lógica que Enter
                        let payload: any = {}
                        if (f.isNumber) {
                          const v = parseDecimalInput(techEditing?.val || '')
                          if (v == null) { setTechEditing(null); return }
                          payload[f.key] = v
                        } else {
                          payload[f.key] = (techEditing?.val || '').trim()
                        }
                        try {
                          await http.patch(`/products/${pid}`, payload)
                          showToast('success', 'Campo guardado')
                          await refresh()
                        } catch (err: any) {
                          showToast('error', err?.response?.data?.detail || 'Campo no soportado aún en backend')
                        } finally {
                          setTechEditing(null)
                        }
                      }}
                    />
                  ) : (
                    <>
                      <span style={{ marginRight: 6 }}>{(prod as any)?.[f.key] ?? '-'}</span>
                      <button className="btn-secondary" onClick={() => setTechEditing({ field: f.key, val: String((prod as any)?.[f.key] ?? '') })}>✎</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Proveedores y precios */}
  <SupplierOfferings key={`offer-${offeringsTick}`} productId={pid} theme={theme} />

      {/* Variantes y SKU propio */}
      <div className="card" style={{ background: theme.card, padding: 12, borderRadius: theme.radius, border: `1px solid ${theme.border}`, marginTop: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Variantes (SKU propio)</div>
        {variants.length === 0 ? (
          <div style={{ opacity: .8 }}>Sin variantes.</div>
        ) : (
          <table className="table w-full">
            <thead>
              <tr>
                <th>ID</th>
                <th>SKU</th>
                <th>Nombre</th>
                <th>Valor</th>
                {canEdit && <th className="text-center" style={{ width: 120 }}>Acciones</th>}
              </tr>
            </thead>
            <tbody>
              {variants.map(v => (
                <tr key={v.id}>
                  <td>{v.id}</td>
                  <td>
                    {skuEditing?.id === v.id ? (
                      <input className="input" style={{ width: 180 }} value={skuEditing.val} onChange={(e) => setSkuEditing({ id: v.id, val: e.target.value })}
                        onKeyDown={async (e) => {
                          if (e.key === 'Enter') {
                            try { await updateVariantSku(v.id, skuEditing.val.trim()); setVariants(prev => prev.map(x => x.id === v.id ? ({ ...x, sku: skuEditing.val.trim() }) : x)); setSkuEditing(null); showToast('success', 'SKU actualizado') } catch (err: any) { showToast('error', err?.message || 'Error') }
                          }
                          if (e.key === 'Escape') setSkuEditing(null)
                        }}
                        onBlur={async () => {
                          try { await updateVariantSku(v.id, skuEditing?.val.trim() || v.sku); setVariants(prev => prev.map(x => x.id === v.id ? ({ ...x, sku: skuEditing?.val.trim() || v.sku }) : x)); setSkuEditing(null); showToast('success', 'SKU actualizado') } catch (err: any) { showToast('error', err?.message || 'Error') }
                        }} />
                    ) : (
                      <span>{v.sku}</span>
                    )}
                  </td>
                  <td>{v.name || ''}</td>
                  <td>{v.value || ''}</td>
                  {canEdit && (
                    <td className="text-center">
                      {skuEditing?.id === v.id ? (
                        <button className="btn-secondary" onClick={() => setSkuEditing(null)}>Cancelar</button>
                      ) : (
                        <button className="btn-secondary" onClick={() => setSkuEditing({ id: v.id, val: v.sku })}>✎</button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

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

      {/* Modal: Fuentes consultadas (txt) */}
      {srcOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 75 }}>
          <div className="panel" style={{ padding: 16, minWidth: 520, maxWidth: 900 }}>
            <h4 style={{ marginTop: 0 }}>Fuentes consultadas</h4>
            <div style={{ maxHeight: 360, overflow: 'auto', whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 13 }}>
              {srcLoading ? 'Cargando...' : (srcText || 'Sin contenido')}
            </div>
            <div className="row" style={{ gap: 8, marginTop: 10 }}>
              <button className="btn-primary" onClick={() => setSrcOpen(false)}>Cerrar</button>
              {prod?.enrichment_sources_url && (
                <a className="btn" href={prod.enrichment_sources_url} target="_blank" rel="noreferrer">Descargar .txt</a>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal: Agregar SKU de proveedor */}
      {linkOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 70 }}>
          <div className="panel" style={{ padding: 16, minWidth: 520 }}>
            <h4 style={{ marginTop: 0 }}>Agregar SKU de proveedor</h4>
            <div className="row" style={{ gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 240 }}>
                <label className="label">Proveedor</label>
                <SupplierAutocomplete value={supplierSel} onChange={setSupplierSel} placeholder="Buscar proveedor..." />
              </div>
              <div style={{ flex: 1, minWidth: 200 }}>
                <label className="label">SKU proveedor</label>
                <input className="input" value={supplierSku} onChange={(e) => setSupplierSku(e.target.value)} placeholder="Ej: ABC-123" />
              </div>
            </div>
            <div className="row" style={{ gap: 12, alignItems: 'flex-start', flexWrap: 'wrap', marginTop: 10 }}>
              <div style={{ flex: 1, minWidth: 240 }}>
                <label className="label">Variante interna</label>
                <select className="select" value={selectedVariantId ?? ''} onChange={(e) => setSelectedVariantId(Number(e.target.value))}>
                  {variants.map(v => (
                    <option key={v.id} value={v.id}>{v.sku}{v.name ? ` — ${v.name}` : ''}{v.value ? ` (${v.value})` : ''}</option>
                  ))}
                </select>
              </div>
              <div style={{ flex: 1, minWidth: 200 }}>
                <label className="label">Título (opcional)</label>
                <input className="input" value={supplierTitle} onChange={(e) => setSupplierTitle(e.target.value)} placeholder="Nombre del item en proveedor" />
              </div>
            </div>
            <div className="row" style={{ gap: 8, marginTop: 12 }}>
              <button className="btn-secondary" onClick={() => setLinkOpen(false)} disabled={linkBusy}>Cancelar</button>
              <button className="btn-primary" disabled={linkBusy || !supplierSel || !supplierSku.trim() || !selectedVariantId} onClick={async () => {
                if (!supplierSel || !selectedVariantId) return
                setLinkBusy(true)
                try {
                  await linkSupplierProduct({ supplier_id: supplierSel.id, supplier_product_id: supplierSku.trim(), internal_variant_id: selectedVariantId, title: supplierTitle || undefined })
                  showToast('success', 'Vínculo creado')
                  setLinkOpen(false)
                  // Refrescar ofertas
                  try { await refresh() } catch {}
                  setOfferingsTick(t => t + 1)
                } catch (e: any) {
                  showToast('error', e?.message || 'No se pudo crear el vínculo')
                } finally {
                  setLinkBusy(false)
                }
              }}>{linkBusy ? 'Guardando...' : 'Guardar'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function SupplierOfferings({ productId, theme }: { productId: number; theme: { card: string; border: string } }) {
  const { state } = useAuth()
  const canEdit = state.role === 'admin' || state.role === 'colaborador'
  const [rows, setRows] = useState<{ supplier_item_id: number; supplier_name: string; supplier_sku: string; buy_price: number | null; updated_at?: string | null }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [buyVal, setBuyVal] = useState('')

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
                    <td>
                      {canEdit ? (
                        editingId === r.supplier_item_id ? (
                          <input className="input" style={{ width: 120 }} value={buyVal} onChange={(e) => setBuyVal(e.target.value)} onKeyDown={async (e) => { if (e.key === 'Enter') { const v = Number(buyVal.replace(',', '.')); if (!isFinite(v) || v <= 0) { showToast('error', 'Valor inválido'); return } try { await updateSupplierBuyPrice(r.supplier_item_id, Math.round(v * 100) / 100); setRows(prev => prev.map(x => x.supplier_item_id === r.supplier_item_id ? { ...x, buy_price: Math.round(v * 100) / 100 } : x)); setEditingId(null); showToast('success', 'Precio guardado') } catch (err: any) { showToast('error', err?.message || 'Error') } } if (e.key === 'Escape') setEditingId(null) }} onBlur={async () => { const v = Number(buyVal.replace(',', '.')); if (!isFinite(v) || v <= 0) { showToast('error', 'Valor inválido'); return } try { await updateSupplierBuyPrice(r.supplier_item_id, Math.round(v * 100) / 100); setRows(prev => prev.map(x => x.supplier_item_id === r.supplier_item_id ? { ...x, buy_price: Math.round(v * 100) / 100 } : x)); setEditingId(null); showToast('success', 'Precio guardado') } catch (err: any) { showToast('error', err?.message || 'Error') } }} />
                        ) : (
                          <>
                            <span>{r.buy_price != null ? `$ ${r.buy_price.toFixed(2)}` : '-'}</span>
                            <button className="btn-secondary" style={{ marginLeft: 6 }} onClick={() => { setEditingId(r.supplier_item_id); setBuyVal(String(r.buy_price ?? '')) }}>✎</button>
                          </>
                        )
                      ) : (
                        <span>{r.buy_price != null ? `$ ${r.buy_price.toFixed(2)}` : '-'}</span>
                      )}
                    </td>
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

