// NG-HEADER: Nombre de archivo: Market.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Market.tsx
// NG-HEADER: Descripción: Página de Mercado - Comparación de precios con el mercado
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useToast } from '../components/ToastProvider'
import { PATHS } from '../routes/paths'
import { listCategories, Category } from '../services/categories'
import { listMarketProducts, updateProductSalePrice, batchUpdateMarketPrices, type MarketProductItem } from '../services/market'
import { deleteCanonicalProduct } from '../services/canonical'
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
  
  // Estado para confirmación de eliminación
  const [deletingProductId, setDeletingProductId] = useState<number | null>(null)

  // Estado para selección múltiple
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [updating, setUpdating] = useState(false)

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

  async function handleDeleteProduct(productId: number, productName: string) {
    if (!confirm(`¿Estás seguro de eliminar el producto "${productName}" (ID: ${productId})?\n\nEsta acción es permanente y eliminará el producto canónico y todas sus fuentes de mercado asociadas.`)) {
      return
    }
    
    try {
      setDeletingProductId(productId)
      await deleteCanonicalProduct(productId)
      push({
        kind: 'success',
        message: `Producto "${productName}" eliminado correctamente`,
      })
      // Recargar la lista
      await loadProducts()
    } catch (error: any) {
      push({
        kind: 'error',
        message: error?.response?.data?.detail || error?.message || 'Error al eliminar el producto',
      })
    } finally {
      setDeletingProductId(null)
    }
  }

  // Funciones de selección múltiple
  function toggleSelect(id: number) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  function clearSelection() {
    setSelected(new Set())
  }

  function selectAllOnPage() {
    setSelected(new Set(items.map((item) => item.product_id)))
  }

  function toggleSelectAllOnPage() {
    if (selected.size === items.length && items.length > 0) {
      clearSelection()
    } else {
      selectAllOnPage()
    }
  }

  async function handleBatchUpdate() {
    if (selected.size === 0) {
      push({ kind: 'error', message: 'Debe seleccionar al menos un producto' })
      return
    }

    const productIds = Array.from(selected)
    
    // Validar límite del backend
    if (productIds.length > 100) {
      push({ kind: 'error', message: 'Máximo 100 productos por actualización' })
      return
    }

    setUpdating(true)
    try {
      const response = await batchUpdateMarketPrices(productIds)
      
      // Construir mensaje de resumen
      const parts: string[] = []
      parts.push(`${response.enqueued} producto${response.enqueued !== 1 ? 's' : ''} encolado${response.enqueued !== 1 ? 's' : ''}`)
      if (response.not_found > 0) {
        parts.push(`${response.not_found} no encontrado${response.not_found !== 1 ? 's' : ''}`)
      }
      if (response.errors > 0) {
        parts.push(`${response.errors} con error${response.errors !== 1 ? 'es' : ''}`)
      }
      
      push({
        kind: 'success',
        message: parts.join(', ')
      })
      
      // Limpiar selección después de éxito
      clearSelection()
      
      // Opcional: recargar productos después de un delay para ver actualizaciones
      // (las tareas se procesan en background, puede tomar varios segundos)
      setTimeout(() => {
        loadProducts()
      }, 2000)
      
    } catch (error: any) {
      push({
        kind: 'error',
        message: error?.message || 'Error al iniciar actualización masiva'
      })
    } finally {
      setUpdating(false)
    }
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

  /**
   * Convierte texto en mayúsculas o con formato técnico a Title Case legible
   * Ejemplos:
   * - "PAR_0017_BAN" -> "Par 0017 Ban"
   * - "FER_0025_ORG" -> "Fer 0025 Org"
   * - "PRODUCTO NORMAL" -> "Producto Normal"
   * - "producto normal" -> "Producto Normal"
   */
  function formatToTitleCase(text: string | null | undefined): string {
    if (!text) return ''
    
    // Dividir por espacios o guiones bajos y convertir cada palabra a Title Case
    return text
      .split(/\s+|_+/)
      .map(word => {
        if (word.length === 0) return word
        // Si la palabra es solo números, mantenerla tal cual
        if (/^\d+$/.test(word)) return word
        // Convertir a Title Case: primera letra mayúscula, resto minúsculas
        return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
      })
      .join(' ')
  }

  return (
    <div className="panel p-4" style={{ margin: 16 }}>
      {/* Encabezado */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <h2 style={{ marginTop: 0, marginBottom: 0, flex: 1 }}>Mercado</h2>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button 
            className="btn" 
            onClick={handleBatchUpdate}
            disabled={selected.size === 0 || updating}
            title={selected.size === 0 ? 'Seleccione productos para actualizar' : `Actualizar ${selected.size} producto${selected.size !== 1 ? 's' : ''}`}
          >
            {updating ? 'Actualizando...' : `Actualizar ${selected.size > 0 ? `(${selected.size})` : ''}`}
          </button>
          {selected.size > 0 && (
            <button className="btn-secondary" onClick={clearSelection}>
              Limpiar selección
            </button>
          )}
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
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 16, marginBottom: 8, alignItems: 'flex-end' }}>
          {/* Filtro por nombre/SKU - Izquierda */}
          <div style={{ minWidth: 200, justifySelf: 'flex-start' }}>
            <label style={{ display: 'block', fontSize: 12, marginBottom: 4, color: 'var(--text-secondary)' }}>
              Buscar producto
            </label>
            <input
              className="input"
              style={{ width: 'fit-content', minWidth: 'auto' }}
              placeholder="Nombre o SKU..."
              value={q}
              onChange={(e) => { setQ(e.target.value); resetAndSearch() }}
              title="Buscar por nombre de producto o SKU"
            />
          </div>
          
          {/* Filtro por proveedor - Centro */}
          <div style={{ minWidth: 200, justifySelf: 'center' }}>
            <label style={{ display: 'block', fontSize: 12, marginBottom: 4, color: 'var(--text-secondary)' }}>
              Proveedor
            </label>
            <SupplierAutocomplete
              value={supplierSel}
              onChange={(item) => { 
                setSupplierSel(item)
                setSupplierId(item ? String(item.id) : '')
                resetAndSearch()
              }}
              placeholder="Todos los proveedores"
            />
          </div>
          
          {/* Filtro por categoría - Derecha */}
          <div style={{ minWidth: 150, justifySelf: 'flex-end' }}>
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
        </div>

        {/* Botón limpiar filtros - Debajo de los filtros */}
        {hasActiveFilters() && (
          <div style={{ marginTop: 8 }}>
            <button 
              className="btn-secondary" 
              onClick={clearAllFilters}
              title="Limpiar todos los filtros"
            >
              🗑️ Limpiar filtros
            </button>
          </div>
        )}

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
              <th style={{ textAlign: 'center', width: 40 }}>
                <input
                  type="checkbox"
                  checked={items.length > 0 && selected.size === items.length}
                  onChange={toggleSelectAllOnPage}
                  title={items.length > 0 && selected.size === items.length ? 'Deseleccionar todos' : 'Seleccionar todos'}
                />
              </th>
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
                <td colSpan={8} style={{ textAlign: 'center', padding: 24, color: 'var(--text-secondary)' }}>
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
                    'No hay productos disponibles'
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
                    {/* Checkbox de selección */}
                    <td style={{ textAlign: 'center', width: 40 }}>
                      <input
                        type="checkbox"
                        checked={selected.has(product.product_id)}
                        onChange={() => toggleSelect(product.product_id)}
                        title={selected.has(product.product_id) ? 'Deseleccionar' : 'Seleccionar'}
                      />
                    </td>
                    {/* Nombre del producto */}
                    <td style={{ textAlign: 'left' }}>
                      {product.internal_product_id ? (
                        <Link 
                          className="truncate product-title" 
                          to={`/productos/${product.internal_product_id}`}
                          state={{ from: '/mercado' }}
                          title={product.preferred_name}
                        >
                          {formatToTitleCase(product.preferred_name)}
                        </Link>
                      ) : (
                        <span 
                          className="truncate" 
                          style={{ color: 'var(--text-secondary)', cursor: 'not-allowed' }}
                          title="No hay Product interno asociado - No se puede ver el detalle"
                        >
                          {formatToTitleCase(product.preferred_name)}
                        </span>
                      )}
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
                      <div style={{ display: 'flex', gap: 4, justifyContent: 'center', alignItems: 'center' }}>
                        <button
                          className="btn-secondary"
                          onClick={() => handleOpenDetail(product.product_id, product.preferred_name)}
                          title="Ver detalles del mercado"
                          style={{ padding: '4px 8px', fontSize: 14 }}
                        >
                          👁️ Ver
                        </button>
                        {canEdit && product.internal_product_id === null && (
                          <button
                            className="btn-secondary"
                            onClick={() => handleDeleteProduct(product.product_id, product.preferred_name)}
                            disabled={deletingProductId === product.product_id}
                            title="Eliminar producto canónico (sin Product interno asociado)"
                            style={{ 
                              padding: '4px 8px', 
                              fontSize: 14,
                              color: '#ef4444',
                              borderColor: '#ef4444'
                            }}
                          >
                            {deletingProductId === product.product_id ? '⏳' : '🗑️'}
                          </button>
                        )}
                      </div>
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
        .row-selected {
          background-color: var(--primary-light, rgba(59, 130, 246, 0.1));
        }
      `}</style>
    </div>
  )
}
