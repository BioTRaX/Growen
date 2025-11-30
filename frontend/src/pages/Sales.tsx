// NG-HEADER: Nombre de archivo: Sales.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Sales.tsx
// NG-HEADER: Descripción: Página de registro de ventas con selectores mejorados, costos adicionales y adjuntos
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import AppToolbar from '../components/AppToolbar'
import { 
  createSale, 
  listSales, 
  annulSale, 
  confirmSale, 
  deliverSale, 
  uploadSaleAttachment,
  type SaleItem,
  type AdditionalCost
} from '../services/sales'
import { listCustomers, type Customer } from '../services/customers'
import { listProducts } from '../services/products'

// Componentes de ventas
import CustomerSelector from '../components/sales/CustomerSelector'
import ProductSelector, { type ProductLite } from '../components/sales/ProductSelector'
import SalesChannelSelector from '../components/sales/SalesChannelSelector'
import AdditionalCostsEditor from '../components/sales/AdditionalCostsEditor'
import SaleDocumentDropzone from '../components/sales/SaleDocumentDropzone'

type FilePreview = { file: File; id: string }

type LineItem = SaleItem & {
  title: string
  stock: number
  price?: number
}

export default function SalesPage() {
  // Data
  const [customers, setCustomers] = useState<Customer[]>([])
  const [products, setProducts] = useState<ProductLite[]>([])
  const [recentSales, setRecentSales] = useState<any[]>([])

  // Form state
  const [customerId, setCustomerId] = useState<number | 'new'>('new')
  const [newCustomerName, setNewCustomerName] = useState('')
  const [items, setItems] = useState<LineItem[]>([])
  const [note, setNote] = useState('')
  const [channelId, setChannelId] = useState<number | null>(null)
  const [additionalCosts, setAdditionalCosts] = useState<AdditionalCost[]>([])
  const [documents, setDocuments] = useState<FilePreview[]>([])

  // UI state
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [cRes, pRes, sRes] = await Promise.all([
        listCustomers({ page_size: 500 }),
        listProducts({ page: 1, page_size: 500, stock: 'gt:0' } as any),
        listSales({ page: 1, page_size: 10 })
      ])
      setCustomers(cRes.items)
      // Mapear productos con stock > 0
      setProducts(pRes.items.filter((x: any) => x.stock > 0).map((x: any) => ({
        id: x.id,
        title: x.title,
        stock: x.stock,
        sku: x.sku || x.first_variant_sku,
        price: x.precio_venta || x.canonical_sale_price
      })))
      setRecentSales(sRes.items)
    } catch (err) {
      console.error('Error loading data:', err)
    } finally {
      setLoading(false)
    }
  }

  function handleProductSelect(product: ProductLite) {
    // Verificar si ya existe en items
    const existing = items.find(i => i.product_id === product.id)
    if (existing) {
      // Incrementar cantidad si hay stock disponible
      const currentQty = existing.qty
      const usedStock = items.filter(i => i.product_id === product.id).reduce((sum, i) => sum + i.qty, 0)
      if (usedStock < product.stock) {
        setItems(items.map(i => 
          i.product_id === product.id 
            ? { ...i, qty: i.qty + 1 }
            : i
        ))
      }
      return
    }
    
    setItems([...items, {
      product_id: product.id,
      qty: 1,
      unit_price: product.price,
      title: product.title,
      stock: product.stock,
      price: product.price
    }])
  }

  function updateItemQty(index: number, qty: number) {
    if (qty <= 0) {
      removeItem(index)
      return
    }
    const item = items[index]
    if (qty > item.stock) {
      qty = item.stock
    }
    setItems(items.map((it, i) => i === index ? { ...it, qty } : it))
  }

  function removeItem(index: number) {
    setItems(items.filter((_, i) => i !== index))
  }

  // Calcular totales
  const subtotal = items.reduce((sum, it) => sum + (it.unit_price || it.price || 0) * it.qty, 0)
  const costsTotal = additionalCosts.reduce((sum, c) => sum + c.amount, 0)
  const total = subtotal + costsTotal

  async function onSave() {
    if (!items.length) return
    setSaving(true)
    try {
      const customer = customerId === 'new' 
        ? { name: newCustomerName || 'Consumidor Final' } 
        : { id: Number(customerId) }
      
      const saleItems: SaleItem[] = items.map(it => ({
        product_id: it.product_id,
        qty: it.qty,
        unit_price: it.unit_price || it.price
      }))

      const r = await createSale({
        customer,
        items: saleItems,
        note: note || undefined,
        channel_id: channelId || undefined,
        additional_costs: additionalCosts.length > 0 ? additionalCosts : undefined
      })

      // Subir documentos si hay
      if (documents.length > 0) {
        for (const doc of documents) {
          try {
            await uploadSaleAttachment(r.sale_id, doc.file)
          } catch (err) {
            console.error('Error uploading document:', err)
          }
        }
      }

      alert(`Venta #${r.sale_id} creada. Total $${r.total.toFixed(2)}`)
      
      // Reset form
      setItems([])
      setCustomerId('new')
      setNewCustomerName('')
      setNote('')
      setChannelId(null)
      setAdditionalCosts([])
      setDocuments([])
      
      // Refresh sales list
      const s = await listSales({ page: 1, page_size: 10 })
      setRecentSales(s.items)
      
      // Refresh products (stock changed)
      const pRes = await listProducts({ page: 1, page_size: 500, stock: 'gt:0' } as any)
      setProducts(pRes.items.filter((x: any) => x.stock > 0).map((x: any) => ({
        id: x.id,
        title: x.title,
        stock: x.stock,
        sku: x.sku || x.first_variant_sku,
        price: x.precio_venta || x.canonical_sale_price
      })))
    } catch (e: any) {
      alert(e?.response?.data?.detail || e.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <>
        <AppToolbar />
        <div className="panel" style={{ margin: 16, padding: 24, textAlign: 'center' }}>
          Cargando...
        </div>
      </>
    )
  }

  return (
    <>
      <AppToolbar />
      <div style={{ margin: 16, display: 'grid', gridTemplateColumns: '1fr 400px', gap: 16 }}>
        {/* Panel principal - Formulario */}
        <div className="panel" style={{ padding: 20 }}>
          <h2 style={{ marginTop: 0, marginBottom: 20 }}>Nueva Venta</h2>

          {/* Sección Cliente y Canal */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
            <CustomerSelector
              customers={customers}
              selectedId={customerId}
              onSelect={setCustomerId}
              newCustomerName={newCustomerName}
              onNewCustomerNameChange={setNewCustomerName}
            />
            <SalesChannelSelector
              value={channelId}
              onChange={(id) => setChannelId(id)}
            />
          </div>

          {/* Selector de productos */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ fontWeight: 600, marginBottom: 8, display: 'block' }}>
              Agregar Productos
            </label>
            <ProductSelector
              products={products}
              onSelect={handleProductSelect}
            />
          </div>

          {/* Items agregados */}
          {items.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <label style={{ fontWeight: 600, marginBottom: 8, display: 'block' }}>
                Productos en la venta ({items.length})
              </label>
              <div style={{ 
                background: 'var(--input-bg)', 
                border: '1px solid var(--input-border)', 
                borderRadius: 8,
                overflow: 'hidden'
              }}>
                {items.map((it, idx) => (
                  <div 
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '12px 14px',
                      borderBottom: idx < items.length - 1 ? '1px solid var(--border)' : 'none',
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 500 }}>{it.title}</div>
                      <div style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>
                        ${(it.unit_price || it.price || 0).toFixed(2)} c/u
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <button 
                        type="button"
                        onClick={() => updateItemQty(idx, it.qty - 1)}
                        className="btn"
                        style={{ padding: '4px 10px', minWidth: 32 }}
                      >
                        −
                      </button>
                      <input
                        type="number"
                        value={it.qty}
                        onChange={(e) => updateItemQty(idx, parseInt(e.target.value) || 0)}
                        className="input"
                        style={{ width: 60, textAlign: 'center' }}
                        min={1}
                        max={it.stock}
                      />
                      <button 
                        type="button"
                        onClick={() => updateItemQty(idx, it.qty + 1)}
                        className="btn"
                        style={{ padding: '4px 10px', minWidth: 32 }}
                        disabled={it.qty >= it.stock}
                      >
                        +
                      </button>
                    </div>
                    <div style={{ 
                      width: 100, 
                      textAlign: 'right', 
                      fontWeight: 600,
                      color: 'var(--success)' 
                    }}>
                      ${((it.unit_price || it.price || 0) * it.qty).toFixed(2)}
                    </div>
                    <button
                      type="button"
                      onClick={() => removeItem(idx)}
                      className="btn btn-danger"
                      style={{ padding: '4px 8px' }}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Costos Adicionales */}
          <AdditionalCostsEditor
            costs={additionalCosts}
            onChange={setAdditionalCosts}
          />

          {/* Documentos Adjuntos */}
          <SaleDocumentDropzone
            files={documents}
            onFilesChange={setDocuments}
          />

          {/* Nota */}
          <div style={{ marginTop: 16 }}>
            <label style={{ fontWeight: 600, marginBottom: 8, display: 'block' }}>
              Nota (opcional)
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Observaciones sobre la venta..."
              className="input"
              style={{ width: '100%', minHeight: 80, resize: 'vertical' }}
            />
          </div>

          {/* Resumen y botón guardar */}
          <div style={{ 
            marginTop: 24, 
            padding: 16, 
            background: 'var(--table-header)', 
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>
                Subtotal: ${subtotal.toFixed(2)}
                {costsTotal > 0 && ` + Extras: $${costsTotal.toFixed(2)}`}
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--success)' }}>
                Total: ${total.toFixed(2)}
              </div>
            </div>
            <button
              type="button"
              disabled={saving || !items.length}
              onClick={onSave}
              className="btn-primary btn-lg"
              style={{ minWidth: 160, padding: '14px 28px', fontSize: '1.1rem' }}
            >
              {saving ? 'Guardando...' : 'Guardar Venta'}
            </button>
          </div>
        </div>

        {/* Panel lateral - Últimas ventas */}
        <div className="panel" style={{ padding: 16, height: 'fit-content' }}>
          <h3 style={{ marginTop: 0, marginBottom: 16 }}>Últimas Ventas</h3>
          
          {recentSales.length === 0 ? (
            <div style={{ color: 'var(--muted)', textAlign: 'center', padding: 20 }}>
              No hay ventas recientes
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {recentSales.map(s => (
                <div 
                  key={s.id}
                  style={{
                    padding: 12,
                    background: 'var(--input-bg)',
                    borderRadius: 8,
                    border: '1px solid var(--input-border)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontWeight: 600 }}>Venta #{s.id}</span>
                    <span style={{ 
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: '0.8rem',
                      background: s.status === 'CONFIRMADA' ? 'rgba(34, 197, 94, 0.2)' :
                                  s.status === 'ENTREGADA' ? 'rgba(59, 130, 246, 0.2)' :
                                  s.status === 'ANULADA' ? 'rgba(239, 68, 68, 0.2)' :
                                  'rgba(255, 193, 7, 0.2)',
                      color: s.status === 'CONFIRMADA' ? 'var(--success)' :
                             s.status === 'ENTREGADA' ? '#60a5fa' :
                             s.status === 'ANULADA' ? '#f87171' :
                             '#fbbf24',
                    }}>
                      {s.status}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--muted)', marginBottom: 8 }}>
                    {new Date(s.sale_date).toLocaleString()}
                  </div>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center' 
                  }}>
                    <span style={{ fontWeight: 600, color: 'var(--success)' }}>
                      ${s.total?.toFixed?.(2) ?? s.total}
                    </span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {s.status === 'BORRADOR' && (
                        <button
                          className="btn btn-primary"
                          style={{ padding: '4px 10px', fontSize: '0.8rem' }}
                          onClick={async () => {
                            try {
                              await confirmSale(s.id)
                              const ns = await listSales({ page: 1, page_size: 10 })
                              setRecentSales(ns.items)
                            } catch (e: any) {
                              alert(e?.response?.data?.detail || e.message)
                            }
                          }}
                        >
                          Confirmar
                        </button>
                      )}
                      {s.status === 'CONFIRMADA' && (
                        <button
                          className="btn"
                          style={{ padding: '4px 10px', fontSize: '0.8rem' }}
                          onClick={async () => {
                            try {
                              await deliverSale(s.id)
                              const ns = await listSales({ page: 1, page_size: 10 })
                              setRecentSales(ns.items)
                            } catch (e: any) {
                              alert(e?.response?.data?.detail || e.message)
                            }
                          }}
                        >
                          Entregar
                        </button>
                      )}
                      {(s.status === 'CONFIRMADA' || s.status === 'ENTREGADA') && (
                        <button
                          className="btn btn-danger"
                          style={{ padding: '4px 10px', fontSize: '0.8rem' }}
                          onClick={async () => {
                            const reason = prompt('Motivo de anulación:')
                            if (!reason) return
                            try {
                              await annulSale(s.id, reason)
                              const ns = await listSales({ page: 1, page_size: 10 })
                              setRecentSales(ns.items)
                            } catch (e: any) {
                              alert(e?.response?.data?.detail || e.message)
                            }
                          }}
                        >
                          Anular
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
