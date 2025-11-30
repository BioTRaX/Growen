// NG-HEADER: Nombre de archivo: ProductSelector.tsx
// NG-HEADER: Ubicación: frontend/src/components/sales/ProductSelector.tsx
// NG-HEADER: Descripción: Selector de productos con búsqueda y visualización de stock
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState, useEffect, useRef } from 'react'

export type ProductLite = { 
  id: number
  title: string
  stock: number
  sku?: string
  price?: number 
}

type Props = {
  products: ProductLite[]
  onSelect: (product: ProductLite) => void
}

export default function ProductSelector({ products, onSelect }: Props) {
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

  // Filtrar solo productos con stock > 0
  const availableProducts = products.filter(p => p.stock > 0)
  
  const filteredProducts = availableProducts.filter(p => 
    p.title.toLowerCase().includes(search.toLowerCase()) ||
    (p.sku && p.sku.toLowerCase().includes(search.toLowerCase()))
  )

  function handleSelect(product: ProductLite) {
    onSelect(product)
    setIsOpen(false)
    setSearch('')
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', flex: 1 }}>
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
        <span style={{ color: 'var(--muted)' }}>
          Seleccionar producto...
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
            maxHeight: 400,
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
              placeholder="Buscar producto por nombre o SKU..."
              className="input"
              style={{ width: '100%' }}
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
          </div>

          <div style={{ flex: 1, overflow: 'auto' }}>
            {filteredProducts.length === 0 && (
              <div style={{ padding: '20px', color: 'var(--muted)', textAlign: 'center' }}>
                {search 
                  ? 'No se encontraron productos' 
                  : 'No hay productos con stock disponible'}
              </div>
            )}

            {filteredProducts.map((p) => (
              <div
                key={p.id}
                onClick={() => handleSelect(p)}
                style={{
                  padding: '12px 14px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                  borderBottom: '1px solid var(--border)',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--table-row-hover)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ 
                    fontWeight: 500, 
                    overflow: 'hidden', 
                    textOverflow: 'ellipsis', 
                    whiteSpace: 'nowrap' 
                  }}>
                    {p.title}
                  </div>
                  {p.sku && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                      SKU: {p.sku}
                    </div>
                  )}
                </div>

                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 16,
                  flexShrink: 0,
                }}>
                  {p.price && (
                    <span style={{ color: 'var(--text)', fontWeight: 500 }}>
                      ${p.price.toFixed(2)}
                    </span>
                  )}
                  <span style={{ 
                    padding: '4px 10px', 
                    borderRadius: 12,
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    background: p.stock <= 5 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(34, 197, 94, 0.2)',
                    color: p.stock <= 5 ? '#f87171' : 'var(--success)',
                  }}>
                    Stock: {p.stock}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {availableProducts.length > 0 && (
            <div style={{ 
              padding: '8px 14px', 
              borderTop: '1px solid var(--border)',
              color: 'var(--muted)',
              fontSize: '0.85rem',
              textAlign: 'center',
            }}>
              {filteredProducts.length} de {availableProducts.length} productos con stock
            </div>
          )}
        </div>
      )}
    </div>
  )
}

