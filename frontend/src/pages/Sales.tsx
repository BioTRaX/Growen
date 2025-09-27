// NG-HEADER: Nombre de archivo: Sales.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Sales.tsx
// NG-HEADER: Descripción: Registro básico de ventas (items y cliente)
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import AppToolbar from '../components/AppToolbar'
import { createSale, listSales, annulSale, confirmSale, deliverSale, type SaleItem } from '../services/sales'
import { listCustomers, type Customer } from '../services/customers'
import { listProducts } from '../services/products'

type ProductLite = { id: number; title: string; stock: number }

export default function SalesPage() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [products, setProducts] = useState<ProductLite[]>([])
  const [customerId, setCustomerId] = useState<number | 'new'>('new')
  const [newCustomerName, setNewCustomerName] = useState('')
  const [items, setItems] = useState<SaleItem[]>([])
  const [productSel, setProductSel] = useState<number | ''>('')
  const [qty, setQty] = useState<number>(1)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [recentSales, setRecentSales] = useState<any[]>([])

  useEffect(() => {
    (async () => {
      const c = await listCustomers({ page_size: 500 })
      setCustomers(c.items)
      const p = await listProducts({ page: 1, page_size: 200, stock: 'gt:0' } as any)
      setProducts(p.items.map((x:any)=>({ id: x.id, title: x.title, stock: x.stock })))
      const s = await listSales({ page: 1, page_size: 10 })
      setRecentSales(s.items)
    })()
  }, [])

  function addItem() {
    if (!productSel || qty <= 0) return
    setItems(prev => [...prev, { product_id: Number(productSel), qty }])
    setProductSel(''); setQty(1)
  }

  async function onSave() {
    if (!items.length) return
    setSaving(true)
    try {
      const customer = customerId === 'new' ? { name: newCustomerName || 'Consumidor Final' } : { id: Number(customerId) }
      const r = await createSale({ customer, items, note })
      alert(`Venta #${r.sale_id} creada. Total $${r.total}`)
  setItems([]); setCustomerId('new'); setNewCustomerName(''); setNote('')
  const s = await listSales({ page: 1, page_size: 10 })
  setRecentSales(s.items)
    } catch (e:any) {
      alert(e?.response?.data?.detail || e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <AppToolbar />
      <div className="panel" style={{ margin: 16, padding: 12 }}>
        <h2>Ventas</h2>
        <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:12 }}>
          <label>Cliente:</label>
          <select value={customerId as any} onChange={e => setCustomerId((e.target.value==='new'?'new':Number(e.target.value)))}>
            <option value="new">Nuevo cliente</option>
            {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          {customerId === 'new' && (
            <input placeholder="Nombre nuevo cliente" value={newCustomerName} onChange={e=>setNewCustomerName(e.target.value)} />
          )}
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:8 }}>
          <select value={productSel as any} onChange={e=>setProductSel(Number(e.target.value))}>
            <option value="">Producto…</option>
            {products.map(p => <option key={p.id} value={p.id}>{p.title} (stock {p.stock})</option>)}
          </select>
          <input type="number" min={1} value={qty} onChange={e=>setQty(Number(e.target.value))} style={{ width:80 }} />
          <button className="btn-dark" onClick={addItem}>Agregar</button>
        </div>
        <ul>
          {items.map((it, idx) => (
            <li key={idx}>#{idx+1} - Prod {it.product_id} x {it.qty}</li>
          ))}
        </ul>
        <textarea placeholder="Nota" value={note} onChange={e=>setNote(e.target.value)} style={{ width:'100%', minHeight:80, marginTop:8 }} />
        <div style={{ marginTop:8 }}>
          <button disabled={saving || !items.length} className="btn-dark" onClick={onSave}>Guardar venta</button>
        </div>
        <h3 style={{ marginTop:16 }}>Últimas ventas</h3>
        <table className="table">
          <thead><tr><th>ID</th><th>Fecha</th><th>Estado</th><th>Total</th><th>Acciones</th></tr></thead>
          <tbody>
            {recentSales.map(s => (
              <tr key={s.id}>
                <td>{s.id}</td>
                <td>{new Date(s.sale_date).toLocaleString()}</td>
                <td>{s.status}</td>
                <td>${s.total?.toFixed?.(2) ?? s.total}</td>
                <td style={{ display:'flex', gap:6 }}>
                  {s.status==='BORRADOR' && (
                    <button onClick={async()=>{
                      try { await confirmSale(s.id); const ns = await listSales({ page: 1, page_size: 10 }); setRecentSales(ns.items) } catch (e:any) { alert(e?.response?.data?.detail || e.message) }
                    }}>Confirmar</button>
                  )}
                  {s.status==='CONFIRMADA' && (
                    <button onClick={async()=>{
                      try { await deliverSale(s.id); const ns = await listSales({ page: 1, page_size: 10 }); setRecentSales(ns.items) } catch (e:any) { alert(e?.response?.data?.detail || e.message) }
                    }}>Entregar</button>
                  )}
                  {(s.status==='CONFIRMADA' || s.status==='ENTREGADA') && (
                    <button onClick={async()=>{
                      const reason = prompt('Motivo de anulación:')
                      if (!reason) return
                      try {
                        await annulSale(s.id, reason)
                        const ns = await listSales({ page: 1, page_size: 10 })
                        setRecentSales(ns.items)
                      } catch (e:any) { alert(e?.response?.data?.detail || e.message) }
                    }}>Anular</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
