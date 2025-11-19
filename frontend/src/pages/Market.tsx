// NG-HEADER: Nombre de archivo: Market.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Market.tsx
// NG-HEADER: Descripción: Página de Mercado - Comparación de precios con el mercado
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useToast } from '../components/ToastProvider'
import { PATHS } from '../routes/paths'
import { listCategories, Category } from '../services/categories'
import { listMarketProducts, updateProductSalePrice, type MarketProductItem } from '../services/market'
import SupplierAutocomplete from '../components/supplier/SupplierAutocomplete'
import MarketDetailModal from '../components/MarketDetailModal'
import EditablePriceField from '../components/EditablePriceField'
import type { SupplierSearchItem } from '../services/suppliers'

export default function Market() {
  const { push } = useToast()
  const { state } = useAuth()
  const navigate = useNavigate()
  const canEdit = state.role === 'admin' || state.role === 'colaborador'

  // Estados de filtros
  const [categories, setCategories] = useState<Category[]>([])
  const [categoryId, setCategoryId] = useState('') // Filtro por categoría (vacío = todas)
  const [supplierId, setSupplierId] = useState('') // Filtro por proveedor (vacío = todos)
  const [supplierSel, setSupplierSel] = useState<SupplierSearchItem | null>(null)
  const [q, setQ] = useState('') // Filtro por búsqueda de texto (nombre/SKU)

  // Estados de datos
  const [items, setItems] = useState<MarketProductItem[]>([])
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [loading, setLoading] = useState(false)

  // Estado para modal de detalles
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null)
  const [selectedProductName, setSelectedProductName] = useState<string>('')

  // Cargar categorías al montar
  useEffect(() => {
    listCategories().then(setCategories).catch(() => {})
  }, [])

  // Cargar productos con filtros
  // Los filtros se aplican con debounce de 300ms para evitar llamadas excesivas
  useEffect(() => {
    const t = setTimeout(() => {
      loadProducts()
    }, 300)
    return () => clearTimeout(t)
  }, [q, supplierId, categoryId, page])

  async function loadProducts() {
    setLoading(true)
    try {
      const response = await listMarketProducts({
        q: q || undefined,
        category_id: categoryId ? parseInt(categoryId) : undefined,
        supplier_id: supplierId ? parseInt(supplierId) : undefined,
        page,
        page_size: pageSize,
      })
      
      setItems(response.items)
      setTotal(response.total)
      setTotalPages(response.pages)
    } catch (error: any) {
      push({ 
        kind: 'error', 
        message: error?.message || 'Error cargando productos del mercado' 
      })
      setItems([])
      setTotal(0)
      setTotalPages(0)
    } finally {
      setLoading(false)
    }
  }

  function resetAndSearch() {
    // Reinicia la paginación al cambiar filtros
    setPage(1)
    setItems([])
  }

  function clearAllFilters() {
    // Limpia todos los filtros activos y reinicia la búsqueda
    setQ('')
    setCategoryId('')
    setSupplierId('')
    setSupplierSel(null)
    resetAndSearch()
  }

  function hasActiveFilters(): boolean {
    // Verifica si hay algún filtro activo
    return !!(q || categoryId || supplierId)
  }

  function handleOpenDetail(productId: number, productName: string) {
    setSelectedProductId(productId)
    setSelectedProductName(productName)
  }

  function handleCloseDetail() {
    setSelectedProductId(null)
    setSelectedProductName('')
  }

  function handlePricesUpdated() {
    // Recargar la lista de productos para reflejar nuevos precios
    loadProducts()
  }

  async function handleUpdateSalePrice(productId: number, newPrice: number) {
    try {
      await updateProductSalePrice(productId, newPrice)
      push({
        kind: 'success',
        message: 'Precio de venta actualizado correctamente',
      })
      // Actualizar el item en el estado local sin recargar toda la lista
      setItems(prevItems =>
        prevItems.map(item =>
          item.product_id === productId
            ? { ...item, sale_price: newPrice }
            : item
        )
      )
    } catch (error: any) {
      push({
        kind: 'error',
        message: error?.message || 'Error actualizando precio de venta',
      })
      throw error
    }
  }

  function formatPrice(price: number | null): string {
    if (price == null) return '-'
    return `$ ${price.toFixed(2)}`
  }

  function formatMarketRange(min: number | null, max: number | null): string {
    if (min == null && max == null) return 'Sin datos'
    if (min == null) return `Hasta ${formatPrice(max)}`
    if (max == null) return `Desde ${formatPrice(min)}`
    if (min === max) return formatPrice(min)
    return `${formatPrice(min)} - ${formatPrice(max)}`
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return 'Nunca'
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    
    if (diffDays === 0) return 'Hoy'
    if (diffDays === 1) return 'Ayer'
    if (diffDays < 7) return `Hace ${diffDays} días`
    if (diffDays < 30) return `Hace ${Math.floor(diffDays / 7)} semanas`
    return date.toLocaleDateString()
  }

  function getPriceComparisonClass(salePrice: number | null, marketMin: number | null, marketMax: number | null): string {
    if (!salePrice || !marketMin || !marketMax) return ''
    
    // Si nuestro precio está por debajo del mínimo del mercado
    if (salePrice < marketMin) return 'price-below-market'
    
    // Si nuestro precio está por encima del máximo del mercado
    if (salePrice > marketMax) return 'price-above-market'
    
    // Si está dentro del rango
    return 'price-in-market'
  }

  return (
    <div className="panel p-4" style={{ margin: 16 }}>
      {/* Encabezado */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <h2 style={{ marginTop: 0, marginBottom: 0, flex: 1 }}>Mercado</h2>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn" onClick={() => push({ kind: 'info', message: 'Función de actualización masiva pendiente (Etapa 3)' })}>
            Actualizar todos
          </button>
          <button className="btn-dark btn-lg" onClick={() => navigate(PATHS.products)}>
            Ir a Productos
          </button>
          <button className="btn-dark btn-lg" onClick={() => navigate(PATHS.stock)}>
            Ir a Stock
          </button>
          <button className="btn-dark btn-lg" onClick={() => navigate(PATHS.home)}>
            Volver
          </button>
        </div>
      </div>

      {/* Descripción */}
      <p style={{ fontSize: 14, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Compará rápidamente tus precios de venta con los rangos actuales del mercado para tomar decisiones informadas.
      </p>

      {/* Filtros */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {/* Filtro por nombre/SKU */}
          <div style={{ flex: 1, minWidth: 200 }}>
            <label style={{ display: 'block', fontSize: 12, marginBottom: 4, color: 'var(--text-secondary)' }}>
              Buscar producto
            </label>
            <input
              className="input w-full"
              placeholder="Nombre o SKU..."
              value={q}
              onChange={(e) => { setQ(e.target.value); resetAndSearch() }}
              title="Buscar por nombre de producto o SKU"
            />
          </div>
          
          {/* Filtro por proveedor */}
          <div style={{ minWidth: 200 }}>
            <label style={{ display: 'block', fontSize: 12, marginBottom: 4, color: 'var(--text-secondary)' }}>
              Proveedor
            </label>
            <SupplierAutocomplete
              className="input"
              value={supplierSel}
              onChange={(item) => { 
                setSupplierSel(item)
                setSupplierId(item ? String(item.id) : '')
                resetAndSearch()
              }}
              placeholder="Todos los proveedores"
            />
          </div>
          
          {/* Filtro por categoría */}
          <div style={{ minWidth: 150 }}>
            <label style={{ display: 'block', fontSize: 12, marginBottom: 4, color: 'var(--text-secondary)' }}>
              Categoría
            </label>
            <select 
              className="select" 
              value={categoryId} 
              onChange={(e) => { setCategoryId(e.target.value); resetAndSearch() }}
              title="Filtrar por categoría de producto"
            >
              <option value="">Todas</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* Botón limpiar filtros */}
          {hasActiveFilters() && (
            <button 
              className="btn-secondary" 
              onClick={clearAllFilters}
              title="Limpiar todos los filtros"
              style={{ alignSelf: 'flex-end' }}
            >
              🗑️ Limpiar filtros
            </button>
          )}
        </div>

        {/* Indicador de filtros activos */}
        {hasActiveFilters() && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 12 }}>
            {q && (
              <span className="filter-badge">
                Búsqueda: "{q}"
                <button 
                  onClick={() => { setQ(''); resetAndSearch() }}
                  style={{ marginLeft: 6, cursor: 'pointer', border: 'none', background: 'transparent', fontSize: 14 }}
                  title="Quitar filtro"
                >
                  ✕
                </button>
              </span>
            )}
            {supplierSel && (
              <span className="filter-badge">
                Proveedor: {supplierSel.name}
                <button 
                  onClick={() => { setSupplierSel(null); setSupplierId(''); resetAndSearch() }}
                  style={{ marginLeft: 6, cursor: 'pointer', border: 'none', background: 'transparent', fontSize: 14 }}
                  title="Quitar filtro"
                >
                  ✕
                </button>
              </span>
            )}
            {categoryId && (
              <span className="filter-badge">
                Categoría: {categories.find(c => c.id === Number(categoryId))?.name}
                <button 
                  onClick={() => { setCategoryId(''); resetAndSearch() }}
                  style={{ marginLeft: 6, cursor: 'pointer', border: 'none', background: 'transparent', fontSize: 14 }}
                  title="Quitar filtro"
                >
                  ✕
                </button>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Contador de resultados */}
      <div style={{ fontSize: 12, marginBottom: 8, color: 'var(--text-secondary)' }}>
        {loading ? 'Cargando...' : `${total} producto${total !== 1 ? 's' : ''} encontrado${total !== 1 ? 's' : ''}`}
      </div>

      {/* Tabla de productos */}
      <div style={{ overflowX: 'auto' }}>
        <table className="table w-full">
          <thead>
            <tr>
              <th style={{ textAlign: 'left', minWidth: 250 }}>Nombre</th>
              <th style={{ textAlign: 'left', minWidth: 150 }}>SKU</th>
              <th style={{ textAlign: 'center', minWidth: 120 }}>Precio Venta (ARS)</th>
              <th style={{ textAlign: 'center', minWidth: 180 }}>Precio Mercado (ARS)</th>
              <th style={{ textAlign: 'center', minWidth: 140 }}>Última Actualización</th>
              <th style={{ textAlign: 'center', minWidth: 100 }}>Categoría</th>
              <th style={{ textAlign: 'center', minWidth: 100 }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: 24, color: 'var(--text-secondary)' }}>
                  {hasActiveFilters() ? (
                    <div>
                      <p style={{ marginBottom: 8 }}>
                        No se encontraron productos que coincidan con los filtros aplicados
                      </p>
                      <button className="btn" onClick={clearAllFilters}>
                        Limpiar filtros
                      </button>
                    </div>
                  ) : (
                    'Endpoint /market/products pendiente de implementación (ver docs/MERCADO.md Etapa 2)'
                  )}
                </td>
              </tr>
            ) : (
              items.map((product) => {
                const comparisonClass = getPriceComparisonClass(
                  product.sale_price,
                  product.market_price_min,
                  product.market_price_max
                )
                
                return (
                  <tr key={product.product_id}>
                    {/* Nombre del producto */}
                    <td style={{ textAlign: 'left' }}>
                      <a 
                        className="truncate product-title" 
                        href={`/productos/${product.product_id}`}
                        title={product.preferred_name}
                      >
                        {product.preferred_name}
                      </a>
                    </td>

                    {/* SKU del producto */}
                    <td style={{ textAlign: 'left', fontSize: 13, color: 'var(--text-secondary)' }}>
                      {product.product_sku}
                    </td>

                    {/* Precio de venta actual - Editable */}
                    <td className={`text-center ${comparisonClass}`}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <EditablePriceField
                          label=""
                          value={product.sale_price}
                          onSave={(newPrice) => handleUpdateSalePrice(product.product_id, newPrice)}
                          disabled={!canEdit}
                          placeholder="Sin precio"
                          formatPrefix="$"
                        />
                      </div>
                    </td>

                    {/* Rango de precio del mercado */}
                    <td className="text-center">
                      <div style={{ fontSize: 14 }}>
                        {formatMarketRange(product.market_price_min, product.market_price_max)}
                      </div>
                      {product.market_price_reference && (
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                          Ref: {formatPrice(product.market_price_reference)}
                        </div>
                      )}
                    </td>

                    {/* Última actualización */}
                    <td className="text-center" style={{ fontSize: 13 }}>
                      {formatDate(product.last_market_update)}
                    </td>

                    {/* Categoría */}
                    <td className="text-center" style={{ fontSize: 13 }}>
                      {product.category_name || '-'}
                    </td>

                    {/* Acciones */}
                    <td className="text-center">
                      <button
                        className="btn-secondary"
                        onClick={() => handleOpenDetail(product.product_id, product.preferred_name)}
                        title="Ver detalles del mercado"
                        style={{ padding: '4px 8px', fontSize: 14 }}
                      >
                        👁️ Ver
                      </button>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Paginación */}
      {total > pageSize && (
        <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'center', alignItems: 'center' }}>
          <button 
            className="btn-dark btn-lg" 
            disabled={page === 1 || loading} 
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Anterior
          </button>
          <span style={{ display: 'flex', alignItems: 'center', padding: '0 12px' }}>
            Página {page} de {totalPages} ({total} productos)
          </span>
          <button 
            className="btn-dark btn-lg" 
            disabled={page >= totalPages || loading} 
            onClick={() => setPage((p) => p + 1)}
          >
            Siguiente
          </button>
        </div>
      )}

      {/* Modal de detalles de mercado */}
      <MarketDetailModal
        productId={selectedProductId}
        productName={selectedProductName}
        open={!!selectedProductId}
        onClose={handleCloseDetail}
        onPricesUpdated={handlePricesUpdated}
      />

      {/* Estilos adicionales para comparación de precios */}
      <style>{`
        .price-below-market {
          color: #22c55e;
          font-weight: 600;
        }
        .price-above-market {
          color: #ef4444;
          font-weight: 600;
        }
        .price-in-market {
          color: var(--primary);
          font-weight: 500;
        }
        .product-title {
          color: var(--primary);
          text-decoration: none;
          font-weight: 500;
        }
        .product-title:hover {
          text-decoration: underline;
        }
        .filter-badge {
          display: inline-flex;
          align-items: center;
          padding: 4px 8px;
          background: var(--primary);
          color: white;
          border-radius: 4px;
          font-size: 12px;
        }
        .filter-badge button {
          color: white;
          opacity: 0.8;
        }
        .filter-badge button:hover {
          opacity: 1;
        }
      `}</style>
    </div>
  )
}
