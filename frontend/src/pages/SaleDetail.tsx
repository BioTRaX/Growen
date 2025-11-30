// NG-HEADER: Nombre de archivo: SaleDetail.tsx
// NG-HEADER: Ubicación: frontend/src/pages/SaleDetail.tsx
// NG-HEADER: Descripción: Página de detalle de una venta específica
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AppToolbar from '../components/AppToolbar'
import { getSale, type SaleDetail as SaleDetailType } from '../services/sales'
import http from '../services/http'

type ProductInfo = { id: number; title: string }

export default function SaleDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [sale, setSale] = useState<SaleDetailType | null>(null)
  const [products, setProducts] = useState<Record<number, ProductInfo>>({})
  const [customerName, setCustomerName] = useState<string>('')
  const [channelName, setChannelName] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      if (!id) return
      setLoading(true)
      setError(null)
      try {
        const saleData = await getSale(Number(id))
        setSale(saleData)

        // Obtener nombres de productos
        const productIds = saleData.lines.map(l => l.product_id)
        if (productIds.length > 0) {
          const productsMap: Record<number, ProductInfo> = {}
          for (const pid of productIds) {
            try {
              const r = await http.get(`/products/${pid}`)
              productsMap[pid] = { id: pid, title: r.data.title || `Producto #${pid}` }
            } catch {
              productsMap[pid] = { id: pid, title: `Producto #${pid}` }
            }
          }
          setProducts(productsMap)
        }

        // Obtener nombre del cliente
        if (saleData.customer_id) {
          try {
            const custR = await http.get(`/customers/${saleData.customer_id}`)
            setCustomerName(custR.data.name || `Cliente #${saleData.customer_id}`)
          } catch {
            setCustomerName(`Cliente #${saleData.customer_id}`)
          }
        }

        // Obtener nombre del canal
        if (saleData.channel_id) {
          try {
            const channelsR = await http.get('/sales/channels')
            const channel = channelsR.data.items.find((c: any) => c.id === saleData.channel_id)
            setChannelName(channel?.name || `Canal #${saleData.channel_id}`)
          } catch {
            setChannelName(`Canal #${saleData.channel_id}`)
          }
        }
      } catch (err: any) {
        setError(err?.response?.data?.detail || 'Error al cargar la venta')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  const statusColors: Record<string, { bg: string; color: string }> = {
    'BORRADOR': { bg: 'rgba(255, 193, 7, 0.2)', color: '#fbbf24' },
    'CONFIRMADA': { bg: 'rgba(34, 197, 94, 0.2)', color: 'var(--success)' },
    'ENTREGADA': { bg: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa' },
    'ANULADA': { bg: 'rgba(239, 68, 68, 0.2)', color: '#f87171' },
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

  if (error || !sale) {
    return (
      <>
        <AppToolbar />
        <div className="panel" style={{ margin: 16, padding: 24 }}>
          <div style={{ color: 'var(--danger)', marginBottom: 16 }}>{error || 'Venta no encontrada'}</div>
          <button className="btn" onClick={() => navigate('/ventas')}>← Volver a Ventas</button>
        </div>
      </>
    )
  }

  const statusStyle = statusColors[sale.status] || statusColors['BORRADOR']
  const subtotal = sale.lines.reduce((sum, l) => sum + l.unit_price * l.qty * (1 - (l.line_discount || 0) / 100), 0)
  const costsTotal = sale.additional_costs?.reduce((sum, c) => sum + c.amount, 0) || 0

  return (
    <>
      <AppToolbar />
      <div style={{ margin: 16 }}>
        <button className="btn" onClick={() => navigate('/ventas')} style={{ marginBottom: 16 }}>
          ← Volver a Ventas
        </button>

        <div className="panel" style={{ padding: 24 }}>
          {/* Encabezado */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <h2 style={{ margin: 0 }}>Venta #{sale.id}</h2>
            <span style={{
              padding: '6px 16px',
              borderRadius: 6,
              fontSize: '0.9rem',
              fontWeight: 600,
              background: statusStyle.bg,
              color: statusStyle.color,
            }}>
              {sale.status}
            </span>
          </div>

          {/* Información general */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 20, marginBottom: 24 }}>
            <div>
              <div style={{ color: 'var(--muted)', fontSize: '0.85rem', marginBottom: 4 }}>Fecha</div>
              <div style={{ fontWeight: 500 }}>{new Date(sale.sale_date).toLocaleString()}</div>
            </div>
            <div>
              <div style={{ color: 'var(--muted)', fontSize: '0.85rem', marginBottom: 4 }}>Cliente</div>
              <div style={{ fontWeight: 500 }}>
                {sale.customer_id ? (
                  <span 
                    style={{ cursor: 'pointer', color: 'var(--primary)' }}
                    onClick={() => navigate(`/clientes/${sale.customer_id}`)}
                  >
                    {customerName}
                  </span>
                ) : 'Consumidor Final'}
              </div>
            </div>
            {channelName && (
              <div>
                <div style={{ color: 'var(--muted)', fontSize: '0.85rem', marginBottom: 4 }}>Canal</div>
                <div style={{ fontWeight: 500 }}>{channelName}</div>
              </div>
            )}
            <div>
              <div style={{ color: 'var(--muted)', fontSize: '0.85rem', marginBottom: 4 }}>Estado de Pago</div>
              <div style={{ fontWeight: 500 }}>{sale.payment_status || '-'}</div>
            </div>
          </div>

          {/* Líneas de productos */}
          <div style={{ marginBottom: 24 }}>
            <h3 style={{ marginBottom: 12 }}>Productos</h3>
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Producto</th>
                  <th style={{ textAlign: 'right' }}>Cantidad</th>
                  <th style={{ textAlign: 'right' }}>Precio Unit.</th>
                  <th style={{ textAlign: 'right' }}>Descuento</th>
                  <th style={{ textAlign: 'right' }}>Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {sale.lines.map(line => {
                  const lineTotal = line.unit_price * line.qty * (1 - (line.line_discount || 0) / 100)
                  return (
                    <tr key={line.id}>
                      <td>{products[line.product_id]?.title || `Producto #${line.product_id}`}</td>
                      <td style={{ textAlign: 'right' }}>{line.qty}</td>
                      <td style={{ textAlign: 'right' }}>${line.unit_price.toFixed(2)}</td>
                      <td style={{ textAlign: 'right' }}>{line.line_discount > 0 ? `${line.line_discount}%` : '-'}</td>
                      <td style={{ textAlign: 'right', fontWeight: 500 }}>${lineTotal.toFixed(2)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Costos adicionales */}
          {sale.additional_costs && sale.additional_costs.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 12 }}>Costos Adicionales</h3>
              <table className="table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left' }}>Concepto</th>
                    <th style={{ textAlign: 'right' }}>Monto</th>
                  </tr>
                </thead>
                <tbody>
                  {sale.additional_costs.map((cost, idx) => (
                    <tr key={idx}>
                      <td>{cost.concept}</td>
                      <td style={{ textAlign: 'right' }}>${cost.amount.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagos */}
          {sale.payments.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 12 }}>Pagos</h3>
              <table className="table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left' }}>Método</th>
                    <th style={{ textAlign: 'right' }}>Monto</th>
                    <th style={{ textAlign: 'left' }}>Referencia</th>
                    <th style={{ textAlign: 'left' }}>Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {sale.payments.map(pay => (
                    <tr key={pay.id}>
                      <td style={{ textTransform: 'capitalize' }}>{pay.method}</td>
                      <td style={{ textAlign: 'right' }}>${pay.amount.toFixed(2)}</td>
                      <td>{pay.reference || '-'}</td>
                      <td>{pay.paid_at ? new Date(pay.paid_at).toLocaleString() : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Totales */}
          <div style={{ 
            borderTop: '1px solid var(--border)', 
            paddingTop: 16,
            display: 'flex',
            justifyContent: 'flex-end'
          }}>
            <div style={{ minWidth: 250 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span>Subtotal productos:</span>
                <span>${subtotal.toFixed(2)}</span>
              </div>
              {costsTotal > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span>Costos adicionales:</span>
                  <span>${costsTotal.toFixed(2)}</span>
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontWeight: 600, fontSize: '1.1rem' }}>
                <span>Total:</span>
                <span style={{ color: 'var(--success)' }}>${sale.total.toFixed(2)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--muted)' }}>
                <span>Pagado:</span>
                <span>${sale.paid_total.toFixed(2)}</span>
              </div>
              {sale.total > sale.paid_total && (
                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--warning)', marginTop: 4 }}>
                  <span>Pendiente:</span>
                  <span>${(sale.total - sale.paid_total).toFixed(2)}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

