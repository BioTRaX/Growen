// NG-HEADER: Nombre de archivo: CustomerDetail.tsx
// NG-HEADER: Ubicación: frontend/src/pages/CustomerDetail.tsx
// NG-HEADER: Descripción: Página de detalle de cliente con edición y histórico de ventas
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AppToolbar from '../components/AppToolbar'
import { getCustomer, updateCustomer, listCustomerSales, type Customer } from '../services/customers'

type CustomerWithTotal = Customer & { total_compras_bruto: number }
type SaleItem = { id: number; status: string; sale_date: string; total: number; paid_total: number }

export default function CustomerDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  
  const [customer, setCustomer] = useState<CustomerWithTotal | null>(null)
  const [sales, setSales] = useState<SaleItem[]>([])
  const [salesTotal, setSalesTotal] = useState(0)
  const [salesPage, setSalesPage] = useState(1)
  const [salesPages, setSalesPages] = useState(1)
  
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Campos editables
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')

  useEffect(() => {
    loadCustomer()
  }, [id])

  useEffect(() => {
    if (id) {
      loadSales()
    }
  }, [id, salesPage])

  async function loadCustomer() {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const data = await getCustomer(Number(id))
      setCustomer(data)
      setName(data.name || '')
      setAddress(data.address || '')
      setEmail(data.email || '')
      setPhone(data.phone || '')
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al cargar el cliente')
    } finally {
      setLoading(false)
    }
  }

  async function loadSales() {
    if (!id) return
    try {
      const r = await listCustomerSales(Number(id), { page: salesPage, page_size: 10 })
      setSales(r.items)
      setSalesTotal(r.total)
      setSalesPages(r.pages)
    } catch {
      // Silenciar errores de ventas
    }
  }

  async function handleSave() {
    if (!id || !name.trim()) {
      setError('El nombre es obligatorio')
      return
    }
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      await updateCustomer(Number(id), {
        name: name.trim(),
        address: address.trim() || null,
        email: email.trim() || null,
        phone: phone.trim() || null,
      })
      setSuccess('Cliente actualizado correctamente')
      // Recargar datos
      loadCustomer()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

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

  if (!customer) {
    return (
      <>
        <AppToolbar />
        <div className="panel" style={{ margin: 16, padding: 24 }}>
          <div style={{ color: 'var(--danger)', marginBottom: 16 }}>{error || 'Cliente no encontrado'}</div>
          <button className="btn" onClick={() => navigate('/clientes')}>← Volver a Clientes</button>
        </div>
      </>
    )
  }

  return (
    <>
      <AppToolbar />
      <div style={{ margin: 16 }}>
        <button className="btn" onClick={() => navigate('/clientes')} style={{ marginBottom: 16 }}>
          ← Volver a Clientes
        </button>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Panel de datos del cliente */}
          <div className="panel" style={{ padding: 24 }}>
            <h2 style={{ marginTop: 0, marginBottom: 24 }}>Datos del Cliente</h2>

            {error && (
              <div style={{ 
                padding: 12, 
                marginBottom: 16, 
                background: 'rgba(239, 68, 68, 0.1)', 
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: 6,
                color: '#f87171'
              }}>
                {error}
              </div>
            )}

            {success && (
              <div style={{ 
                padding: 12, 
                marginBottom: 16, 
                background: 'rgba(34, 197, 94, 0.1)', 
                border: '1px solid rgba(34, 197, 94, 0.3)',
                borderRadius: 6,
                color: 'var(--success)'
              }}>
                {success}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label style={{ display: 'block', marginBottom: 6, fontWeight: 500 }}>
                  Nombre <span style={{ color: 'var(--danger)' }}>*</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  className="input"
                  style={{ width: '100%' }}
                  placeholder="Nombre del cliente"
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: 6, fontWeight: 500 }}>
                  Domicilio
                </label>
                <input
                  type="text"
                  value={address}
                  onChange={e => setAddress(e.target.value)}
                  className="input"
                  style={{ width: '100%' }}
                  placeholder="Dirección"
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: 6, fontWeight: 500 }}>
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="input"
                  style={{ width: '100%' }}
                  placeholder="correo@ejemplo.com"
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: 6, fontWeight: 500 }}>
                  Teléfono
                </label>
                <input
                  type="tel"
                  value={phone}
                  onChange={e => setPhone(e.target.value)}
                  className="input"
                  style={{ width: '100%' }}
                  placeholder="+54 11 1234-5678"
                />
              </div>

              <button 
                className="btn-dark" 
                onClick={handleSave}
                disabled={saving}
                style={{ marginTop: 8 }}
              >
                {saving ? 'Guardando...' : 'Guardar Cambios'}
              </button>
            </div>

            {/* Total en compras */}
            <div style={{ 
              marginTop: 24, 
              paddingTop: 24, 
              borderTop: '1px solid var(--border)'
            }}>
              <div style={{ color: 'var(--muted)', fontSize: '0.85rem', marginBottom: 4 }}>
                Total en Compras (Bruto)
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--success)' }}>
                ${customer.total_compras_bruto.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
              </div>
            </div>
          </div>

          {/* Panel de histórico de ventas */}
          <div className="panel" style={{ padding: 24 }}>
            <h2 style={{ marginTop: 0, marginBottom: 24 }}>
              Histórico de Ventas 
              <span style={{ fontWeight: 400, fontSize: '0.9rem', marginLeft: 8, color: 'var(--muted)' }}>
                ({salesTotal} ventas)
              </span>
            </h2>

            {sales.length === 0 ? (
              <div style={{ color: 'var(--muted)', textAlign: 'center', padding: 40 }}>
                No hay ventas registradas
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {sales.map(s => {
                    const statusStyle = statusColors[s.status] || statusColors['BORRADOR']
                    return (
                      <div 
                        key={s.id}
                        onClick={() => navigate(`/ventas/${s.id}`)}
                        style={{
                          padding: 12,
                          background: 'var(--input-bg)',
                          borderRadius: 8,
                          border: '1px solid var(--input-border)',
                          cursor: 'pointer',
                          transition: 'background 0.2s',
                        }}
                        onMouseOver={e => (e.currentTarget.style.background = 'var(--bg-secondary)')}
                        onMouseOut={e => (e.currentTarget.style.background = 'var(--input-bg)')}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                          <span style={{ fontWeight: 600 }}>Venta #{s.id}</span>
                          <span style={{
                            padding: '2px 8px',
                            borderRadius: 4,
                            fontSize: '0.8rem',
                            background: statusStyle.bg,
                            color: statusStyle.color,
                          }}>
                            {s.status}
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>
                            {new Date(s.sale_date).toLocaleDateString()}
                          </span>
                          <span style={{ fontWeight: 600, color: 'var(--success)' }}>
                            ${s.total.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>

                {/* Paginación */}
                {salesPages > 1 && (
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
                    <button 
                      className="btn" 
                      onClick={() => setSalesPage(p => Math.max(1, p - 1))}
                      disabled={salesPage <= 1}
                    >
                      ← Anterior
                    </button>
                    <span style={{ padding: '8px 16px', color: 'var(--muted)' }}>
                      Página {salesPage} de {salesPages}
                    </span>
                    <button 
                      className="btn" 
                      onClick={() => setSalesPage(p => Math.min(salesPages, p + 1))}
                      disabled={salesPage >= salesPages}
                    >
                      Siguiente →
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

