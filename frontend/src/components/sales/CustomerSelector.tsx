// NG-HEADER: Nombre de archivo: CustomerSelector.tsx
// NG-HEADER: Ubicación: frontend/src/components/sales/CustomerSelector.tsx
// NG-HEADER: Descripción: Selector de clientes con búsqueda y opción de crear nuevo
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState, useEffect, useRef } from 'react'
import type { Customer } from '../../services/customers'

type Props = {
  customers: Customer[]
  selectedId: number | 'new'
  onSelect: (id: number | 'new') => void
  newCustomerName: string
  onNewCustomerNameChange: (name: string) => void
}

export default function CustomerSelector({ 
  customers, 
  selectedId, 
  onSelect, 
  newCustomerName, 
  onNewCustomerNameChange 
}: Props) {
  const [search, setSearch] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selectedCustomer = selectedId !== 'new' 
    ? customers.find(c => c.id === selectedId) 
    : null

  const filteredCustomers = customers.filter(c => 
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    (c.email && c.email.toLowerCase().includes(search.toLowerCase())) ||
    (c.phone && c.phone.includes(search))
  )

  return (
    <div style={{ flex: 1 }}>
      <label style={{ fontWeight: 600, marginBottom: 8, display: 'block' }}>
        Cliente
      </label>

      <div ref={containerRef} style={{ position: 'relative' }}>
        <div
          onClick={() => setIsOpen(!isOpen)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 14px',
            background: 'var(--input-bg)',
            border: '1px solid var(--input-border)',
            borderRadius: 6,
            cursor: 'pointer',
            minHeight: 48,
          }}
        >
          <span style={{ color: selectedCustomer ? 'var(--text)' : 'var(--muted)' }}>
            {selectedId === 'new' 
              ? (newCustomerName || 'Nuevo cliente') 
              : (selectedCustomer?.name || 'Seleccionar cliente...')}
          </span>
          <span style={{ color: 'var(--muted)' }}>▼</span>
        </div>

        {isOpen && (
          <div
            className="dropdown-panel"
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              marginTop: 4,
              zIndex: 100,
              maxHeight: 350,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <div style={{ padding: 10, borderBottom: '1px solid var(--border)' }}>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar por nombre, email o teléfono..."
                className="input"
                style={{ width: '100%' }}
                autoFocus
                onClick={(e) => e.stopPropagation()}
              />
            </div>

            <div style={{ flex: 1, overflow: 'auto', maxHeight: 250 }}>
              {/* Opción Nuevo Cliente */}
              <div
                onClick={() => {
                  onSelect('new')
                  setIsOpen(false)
                  setSearch('')
                }}
                style={{
                  padding: '12px 14px',
                  cursor: 'pointer',
                  background: selectedId === 'new' ? 'rgba(124, 77, 255, 0.2)' : 'transparent',
                  borderBottom: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                }}
                onMouseEnter={(e) => {
                  if (selectedId !== 'new') e.currentTarget.style.background = 'var(--table-row-hover)'
                }}
                onMouseLeave={(e) => {
                  if (selectedId !== 'new') e.currentTarget.style.background = 'transparent'
                }}
              >
                <span style={{ 
                  width: 32, 
                  height: 32, 
                  borderRadius: '50%', 
                  background: 'var(--primary)', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  fontSize: 18,
                }}>
                  +
                </span>
                <span style={{ fontWeight: 500 }}>Nuevo Cliente</span>
              </div>

              {filteredCustomers.map((c) => (
                <div
                  key={c.id}
                  onClick={() => {
                    if (c.id !== undefined) onSelect(c.id)
                    setIsOpen(false)
                    setSearch('')
                  }}
                  style={{
                    padding: '12px 14px',
                    cursor: 'pointer',
                    background: c.id === selectedId ? 'rgba(124, 77, 255, 0.2)' : 'transparent',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                  }}
                  onMouseEnter={(e) => {
                    if (c.id !== selectedId) e.currentTarget.style.background = 'var(--table-row-hover)'
                  }}
                  onMouseLeave={(e) => {
                    if (c.id !== selectedId) e.currentTarget.style.background = 'transparent'
                  }}
                >
                  <span style={{ 
                    width: 32, 
                    height: 32, 
                    borderRadius: '50%', 
                    background: 'var(--table-header)', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    fontSize: 14,
                    fontWeight: 600,
                    color: 'var(--muted)',
                  }}>
                    {c.name.charAt(0).toUpperCase()}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500 }}>{c.name}</div>
                    {(c.email || c.phone) && (
                      <div style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>
                        {c.email || c.phone}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {filteredCustomers.length === 0 && search && (
                <div style={{ padding: '14px', color: 'var(--muted)', textAlign: 'center' }}>
                  No se encontraron clientes
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {selectedId === 'new' && (
        <input
          type="text"
          value={newCustomerName}
          onChange={(e) => onNewCustomerNameChange(e.target.value)}
          placeholder="Nombre del nuevo cliente"
          className="input"
          style={{ width: '100%', marginTop: 8, padding: '10px 14px' }}
        />
      )}
    </div>
  )
}

