// NG-HEADER: Nombre de archivo: PurchaseNew.tsx
// NG-HEADER: Ubicación: frontend/src/pages/PurchaseNew.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useCallback, useEffect, useRef, useState } from 'react'
import AppToolbar from '../components/AppToolbar'
import http from '../services/http'
import ToastContainer, { showToast } from '../components/Toast'
import { useNavigate, Link } from 'react-router-dom'
import { PATHS } from '../routes/paths'
import type { PurchaseLine } from '../services/purchases'
import SupplierAutocomplete from '../components/supplier/SupplierAutocomplete'
import type { SupplierSearchItem } from '../services/suppliers'

export default function PurchaseNew() {
  const nav = useNavigate()
  const [form, setForm] = useState({ supplier_id: '', remito_number: '', remito_date: new Date().toISOString().slice(0,10), vat_rate: 0, note: '' })
  const [lines, setLines] = useState<PurchaseLine[]>([])
  const [saving, setSaving] = useState(false)
  const [supplierSel, setSupplierSel] = useState<SupplierSearchItem | null>(null)
  const dirtyRef = useRef(false)
  const timerRef = useRef<number | null>(null)
  const draftIdRef = useRef<number | null>(null)

  const save = useCallback(async () => {
    if (!dirtyRef.current) return
    // Require supplier and remito fields before attempting to save
    if (!form.supplier_id || !form.remito_number || !form.remito_date) return
    if (!lines.length) return
    // basic validation for lines
    for (const ln of lines) {
      if (!ln.title && !ln.product_id && !ln.supplier_sku) { showToast('error', 'Completa el título o el SKU'); return }
      if (!ln.qty || ln.qty <= 0) { showToast('error', 'Cantidad > 0'); return }
      if (!ln.unit_cost || ln.unit_cost <= 0) { showToast('error', 'Costo unitario > 0'); return }
    }
    setSaving(true)
    try {
  const payload = { ...form, supplier_id: Number(form.supplier_id), lines }
      if (!draftIdRef.current) {
        const r = await http.post('/purchases', { ...payload, lines: undefined })
        const id = r.data?.id
        if (id) {
          draftIdRef.current = id
          // persistir líneas inmediatamente
          await http.put(`/purchases/${id}`, { lines })
          showToast('success', 'Borrador creado')
          setTimeout(() => nav(`/compras/${id}`), 300)
        } else {
          showToast('success', 'Borrador guardado')
        }
      } else {
        await http.put(`/purchases/${draftIdRef.current}`, { ...payload })
        showToast('success', 'Borrador actualizado')
      }
      dirtyRef.current = false
    } catch (e) {
      showToast('error', 'No se pudo guardar')
    } finally {
      setSaving(false)
    }
  }, [form, lines])

  useEffect(() => {
    timerRef.current = window.setInterval(save, 30000)
    return () => { if (timerRef.current) window.clearInterval(timerRef.current) }
  }, [save])

  useEffect(() => { dirtyRef.current = true }, [form])
  useEffect(() => { dirtyRef.current = true }, [lines])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save() }
      if (e.key === 'Escape') { e.preventDefault(); nav(PATHS.purchases) }
      if (e.key === 'Enter') { e.preventDefault(); setLines(prev => [...prev, { title: '', supplier_sku: '', qty: 1, unit_cost: 0, line_discount: 0 }]) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [nav, save])

  return (
    <>
      <AppToolbar />
      <div className="panel p-4">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>Nueva compra</h2>
          <div className="row">
            <button className="btn-dark btn-lg" onClick={save} disabled={saving || !form.supplier_id || !form.remito_number || !lines.length}>
              {saving ? 'Guardando...' : 'Guardar borrador (Ctrl+S)'}
            </button>
            <Link to={PATHS.purchases} className="btn-secondary" style={{ textDecoration: 'none' }}>Cerrar</Link>
          </div>
        </div>
        <div className="text-sm" style={{ opacity: 0.8, marginBottom: 8 }}>
          Primero elegí el proveedor y el número de remito; después podés cargar líneas y guardar.
        </div>
        <div className="row mb-3">
          <div style={{ minWidth: 320 }}>
            <SupplierAutocomplete
              value={supplierSel}
              onChange={(it) => { setSupplierSel(it); setForm({ ...form, supplier_id: it ? String(it.id) : '' }) }}
              placeholder="Proveedor"
              autoFocus
              className="w-full"
            />
          </div>
          <input className="input" placeholder="N° de remito" value={form.remito_number} onChange={(e) => setForm({ ...form, remito_number: e.target.value })} />
          <input className="input" type="date" value={form.remito_date} onChange={(e) => setForm({ ...form, remito_date: e.target.value })} />
          {/* Descuento global removido; aplicar por línea */}
          <input className="input" type="number" step="0.01" placeholder="IVA %" value={form.vat_rate} onChange={(e) => setForm({ ...form, vat_rate: Number(e.target.value) })} />
        </div>
        <textarea className="input w-full" rows={3} placeholder="Nota" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginTop: 16 }}>
          <h3 style={{ margin: 0 }}>Líneas ({lines.length})</h3>
          <div className="row">
            <button className="btn" onClick={() => setLines(prev => [...prev, { title: '', supplier_sku: '', qty: 1, unit_cost: 0, line_discount: 0 }])}>Agregar línea (Enter)</button>
          </div>
        </div>
        <table className="table w-full">
          <thead>
            <tr>
              <th>SKU prov.</th>
              <th>Producto</th>
              <th className="text-center">Cant.</th>
              <th className="text-center">Costo unit.</th>
              <th className="text-center">Desc. %</th>
              <th>Nota</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {lines.map((ln, idx) => (
              <tr key={idx}>
                <td><input className="input" value={ln.supplier_sku || ''} onChange={(e) => setLines(prev => prev.map((p, i) => i === idx ? { ...p, supplier_sku: e.target.value } : p))} /></td>
                <td><input className="input w-full" value={ln.title || ''} onChange={(e) => setLines(prev => prev.map((p, i) => i === idx ? { ...p, title: e.target.value } : p))} /></td>
                <td className="text-center"><input className="input" type="number" step={0.01} value={ln.qty || 0} onChange={(e) => setLines(prev => prev.map((p, i) => i === idx ? { ...p, qty: Number(e.target.value) } : p))} style={{ width: 90 }} /></td>
                <td className="text-center"><input className="input" type="number" step={0.01} value={ln.unit_cost || 0} onChange={(e) => setLines(prev => prev.map((p, i) => i === idx ? { ...p, unit_cost: Number(e.target.value) } : p))} style={{ width: 110 }} /></td>
                <td className="text-center"><input className="input" type="number" step={0.01} value={ln.line_discount || 0} onChange={(e) => setLines(prev => prev.map((p, i) => i === idx ? { ...p, line_discount: Number(e.target.value) } : p))} style={{ width: 90 }} /></td>
                <td><input className="input w-full" value={ln.note || ''} onChange={(e) => setLines(prev => prev.map((p, i) => i === idx ? { ...p, note: e.target.value } : p))} /></td>
                <td><button className="btn-secondary" onClick={() => setLines(prev => prev.filter((_, i) => i !== idx))}>Borrar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ToastContainer />
    </>
  )
}
