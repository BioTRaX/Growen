// NG-HEADER: Nombre de archivo: MarketDetailModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/MarketDetailModal.tsx
// NG-HEADER: Descripción: Modal de detalle de producto en sección Mercado con gestión de fuentes
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useEffect, useState } from 'react'
import { useToast } from './ToastProvider'
import { usePermissions } from '../hooks/usePermissions'
import {
  getProductSources,
  updateProductMarketPrices,
  deleteProductSource,
  updateProductSalePrice,
  updateMarketReference,
  type MarketSource,
  type ProductSourcesResponse,
} from '../services/market'
import AddSourceModal from './AddSourceModal'
import EditablePriceField from './EditablePriceField'
import SuggestedSourcesSection from './SuggestedSourcesSection'
import EditSourceModal from './EditSourceModal'

interface MarketDetailModalProps {
  productId: number | null
  productName?: string
  open: boolean
  onClose: () => void
  onPricesUpdated?: () => void
}

export default function MarketDetailModal({
  productId,
  productName,
  open,
  onClose,
  onPricesUpdated,
}: MarketDetailModalProps) {
  const { push } = useToast()
  const permissions = usePermissions()
  
  // Estados principales
  const [loading, setLoading] = useState(false)
  const [sources, setSources] = useState<ProductSourcesResponse | null>(null)
  const [updating, setUpdating] = useState(false)
  const [showAddSource, setShowAddSource] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [editingSource, setEditingSource] = useState<MarketSource | null>(null)

  // Cargar fuentes cuando se abre el modal
  useEffect(() => {
    if (open && productId) {
      loadSources()
    }
  }, [open, productId])

  async function loadSources() {
    if (!productId) return
    
    setLoading(true)
    try {
      const data = await getProductSources(productId)
      setSources(data)
    } catch (error: any) {
      push({
        kind: 'error',
        message: error?.message || 'Error cargando fuentes de precio',
      })
    } finally {
      setLoading(false)
    }
  }

  async function handleUpdatePrices() {
    if (!productId) return
    
    setUpdating(true)
    try {
      const result = await updateProductMarketPrices(productId, {
        force: true,
        include_web: true,
      })
      
      // Backend procesa asíncronamente, mostrar confirmación de inicio
      push({
        kind: 'info',
        message: result.message || 'Actualización de precios iniciada. Puede demorar varios segundos.',
      })
      
      // Esperar 3 segundos antes de recargar (dar tiempo al worker)
      await new Promise(resolve => setTimeout(resolve, 3000))
      
      // Recargar fuentes para mostrar nuevos precios
      await loadSources()
      
      // Notificar al componente padre para refrescar la tabla
      onPricesUpdated?.()
      
      push({
        kind: 'success',
        message: 'Precios actualizados. Revisa la lista de fuentes.',
      })
      
    } catch (error: any) {
      push({
        kind: 'error',
        message: error?.message || 'Error actualizando precios',
      })
    } finally {
      setUpdating(false)
    }
  }

  async function handleDeleteSource(sourceId: number, sourceName: string) {
    if (!productId) return
    
    if (!confirm(`¿Eliminar fuente "${sourceName}"?`)) return
    
    setDeletingId(sourceId)
    try {
      await deleteProductSource(productId, sourceId)
      push({
        kind: 'success',
        message: `Fuente "${sourceName}" eliminada`,
      })
      await loadSources()
    } catch (error: any) {
      push({
        kind: 'error',
        message: error?.message || 'Error eliminando fuente',
      })
    } finally {
      setDeletingId(null)
    }
  }

  function handleAddSourceSuccess() {
    setShowAddSource(false)
    loadSources()
    push({
      kind: 'success',
      message: 'Fuente agregada correctamente',
    })
  }

  async function handleSaveSalePrice(newPrice: number) {
    if (!productId) return
    
    try {
      await updateProductSalePrice(productId, newPrice)
      
      // Actualizar el estado local
      if (sources) {
        setSources({
          ...sources,
          sale_price: newPrice,
        })
      }
      
      push({
        kind: 'success',
        message: 'Precio de venta actualizado correctamente',
      })
      
      // Notificar al padre para refrescar la tabla
      onPricesUpdated?.()
    } catch (error: any) {
      push({
        kind: 'error',
        message: error?.message || 'Error actualizando precio de venta',
      })
      throw error // Re-lanzar para que el componente maneje el estado
    }
  }

  async function handleSaveMarketReference(newPrice: number) {
    if (!productId) return
    
    try {
      await updateMarketReference(productId, newPrice)
      
      // Actualizar el estado local
      if (sources) {
        setSources({
          ...sources,
          market_price_reference: newPrice,
        })
      }
      
      push({
        kind: 'success',
        message: 'Valor de mercado de referencia actualizado',
      })
      
      // Notificar al padre
      onPricesUpdated?.()
    } catch (error: any) {
      push({
        kind: 'error',
        message: error?.message || 'Error actualizando valor de mercado',
      })
      throw error
    }
  }

  function formatPrice(price: number | null): string {
    if (price == null) return '-'
    return `$ ${price.toFixed(2)}`
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return 'Nunca'
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    
    if (diffHours < 1) return 'Hace menos de 1 hora'
    if (diffHours === 1) return 'Hace 1 hora'
    if (diffHours < 24) return `Hace ${diffHours} horas`
    
    const diffDays = Math.floor(diffHours / 24)
    if (diffDays === 1) return 'Hace 1 día'
    if (diffDays < 7) return `Hace ${diffDays} días`
    
    return date.toLocaleDateString()
  }

  function getSourceFreshness(dateStr: string | null): 'fresh' | 'stale' | 'never' {
    if (!dateStr) return 'never'
    const diffMs = Date.now() - new Date(dateStr).getTime()
    const diffDays = diffMs / (1000 * 60 * 60 * 24)
    
    if (diffDays < 1) return 'fresh'
    if (diffDays < 7) return 'stale'
    return 'never'
  }

  if (!open) return null

  return (
    <>
      <div className="modal-backdrop" onClick={onClose}>
        <div 
          className="modal" 
          style={{ maxWidth: 800, maxHeight: '90vh', overflow: 'auto' }} 
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <div style={{ flex: 1 }}>
              <h3 style={{ margin: 0, marginBottom: 4 }}>Detalles de Mercado</h3>
              <p style={{ margin: 0, fontSize: 14, color: 'var(--text-secondary)' }}>
                {sources?.product_name || productName || 'Cargando...'}
              </p>
            </div>
            <button 
              className="btn-secondary" 
              onClick={onClose}
              style={{ padding: '4px 12px' }}
            >
              ✕
            </button>
          </div>

          {loading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <p>Cargando fuentes de precio...</p>
            </div>
          ) : !sources ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <p style={{ color: 'var(--text-secondary)' }}>No se pudieron cargar las fuentes</p>
            </div>
          ) : (
            <>
              {/* Sección de precios editables */}
              <div 
                style={{ 
                  padding: 20, 
                  background: 'var(--panel-bg)', 
                  borderRadius: 8, 
                  marginBottom: 16,
                  border: '1px solid var(--border-color)',
                }}
              >
                <h4 style={{ margin: 0, marginBottom: 16, fontSize: 16, fontWeight: 600 }}>
                  Gestión de Precios
                </h4>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20 }}>
                  {/* Precio de venta */}
                  <EditablePriceField
                    label="Precio de Venta"
                    value={sources.sale_price}
                    onSave={handleSaveSalePrice}
                    placeholder="Sin precio"
                    disabled={!permissions.canEditMarketPrices()}
                  />
                  
                  {/* Valor de mercado de referencia */}
                  <EditablePriceField
                    label="Valor Mercado (Referencia)"
                    value={sources.market_price_reference}
                    onSave={handleSaveMarketReference}
                    placeholder="Sin valor"
                    disabled={!permissions.canEditMarketPrices()}
                  />
                  
                  {/* Rango de mercado (solo lectura) */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>
                      Rango de Mercado
                    </label>
                    <div 
                      style={{ 
                        padding: '6px 8px',
                        borderRadius: 4,
                        backgroundColor: 'rgba(0,0,0,0.05)',
                      }}
                    >
                      <span style={{ fontSize: 16, fontWeight: 600 }}>
                        {sources.market_price_min != null && sources.market_price_max != null
                          ? `$ ${sources.market_price_min.toFixed(2)} - $ ${sources.market_price_max.toFixed(2)}`
                          : 'Sin datos'}
                      </span>
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                      Calculado automáticamente
                    </span>
                  </div>
                </div>
                
                <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-secondary)' }}>
                  💡 <strong>Tip:</strong> Haz clic en los campos con ✏️ para editar. El rango se calcula automáticamente desde las fuentes.
                </div>
              </div>

              {/* Resumen */}
              {sources.mandatory.length === 0 && sources.additional.length === 0 ? (
                <div 
                  style={{ 
                    padding: 24, 
                    background: 'var(--panel-bg)', 
                    borderRadius: 8, 
                    marginBottom: 16,
                    textAlign: 'center',
                  }}
                >
                  <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                    Este producto aún no tiene fuentes de precio configuradas.
                  </p>
                  <p style={{ margin: 0, marginTop: 8, fontSize: 14 }}>
                    Agregá fuentes para empezar a comparar precios de mercado.
                  </p>
                </div>
              ) : (
                <div 
                  style={{ 
                    padding: 16, 
                    background: 'var(--panel-bg)', 
                    borderRadius: 8, 
                    marginBottom: 16,
                  }}
                >
                  <div style={{ display: 'flex', gap: 24, justifyContent: 'space-around' }}>
                    <div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Fuentes obligatorias</div>
                      <div style={{ fontSize: 24, fontWeight: 'bold' }}>{sources.mandatory.length}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Fuentes adicionales</div>
                      <div style={{ fontSize: 24, fontWeight: 'bold' }}>{sources.additional.length}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Total fuentes</div>
                      <div style={{ fontSize: 24, fontWeight: 'bold' }}>
                        {sources.mandatory.length + sources.additional.length}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Fuentes Obligatorias */}
              {sources.mandatory.length > 0 && (
                <div style={{ marginBottom: 24 }}>
                  <h4 style={{ marginTop: 0, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span>🔒 Fuentes Obligatorias</span>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 'normal' }}>
                      ({sources.mandatory.length})
                    </span>
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {sources.mandatory.map((source) => (
                      <SourceCard
                        key={source.id}
                        source={source}
                        onDelete={handleDeleteSource}
                        onEdit={setEditingSource}
                        deleting={deletingId === source.id}
                        formatPrice={formatPrice}
                        formatDate={formatDate}
                        getFreshness={getSourceFreshness}
                        canDelete={permissions.canManageMarketSources()}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Fuentes Adicionales */}
              {sources.additional.length > 0 && (
                <div style={{ marginBottom: 24 }}>
                  <h4 style={{ marginTop: 0, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span>📝 Fuentes Adicionales</span>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 'normal' }}>
                      ({sources.additional.length})
                    </span>
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {sources.additional.map((source) => (
                      <SourceCard
                        key={source.id}
                        source={source}
                        onDelete={handleDeleteSource}
                        onEdit={setEditingSource}
                        deleting={deletingId === source.id}
                        formatPrice={formatPrice}
                        formatDate={formatDate}
                        getFreshness={getSourceFreshness}
                        canDelete={permissions.canManageMarketSources()}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Sección de fuentes sugeridas automáticamente */}
              {permissions.canDiscoverMarketSources() && productId && productName && (
                <SuggestedSourcesSection
                  productId={productId}
                  productName={productName}
                  onSourcesAdded={loadSources}
                />
              )}

              {/* Acciones */}
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--border-color)' }}>
                {permissions.canManageMarketSources() && (
                  <button 
                    className="btn" 
                    onClick={() => setShowAddSource(true)}
                    disabled={updating}
                  >
                    ➕ Agregar Fuente
                  </button>
                )}
                {permissions.canRefreshMarketPrices() && (
                  <button 
                    className="btn-primary" 
                    onClick={handleUpdatePrices}
                    disabled={updating || (sources.mandatory.length === 0 && sources.additional.length === 0)}
                  >
                    {updating ? '⏳ Actualizando...' : '🔄 Actualizar Precios'}
                  </button>
                )}
                <button className="btn-dark" onClick={onClose}>
                  Cerrar
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Modal de agregar fuente */}
      {showAddSource && productId && (
        <AddSourceModal
          productId={productId}
          open={showAddSource}
          onClose={() => setShowAddSource(false)}
          onSuccess={handleAddSourceSuccess}
        />
      )}

      {/* Modal de editar fuente */}
      {editingSource && (
        <EditSourceModal
          sourceId={editingSource.id}
          currentData={{
            source_name: editingSource.source_name,
            url: editingSource.url,
            last_price: editingSource.last_price,
            is_mandatory: editingSource.is_mandatory,
          }}
          open={!!editingSource}
          onClose={() => setEditingSource(null)}
          onSuccess={() => {
            loadSources()
            push({ 
              kind: 'success', 
              message: 'Fuente actualizada correctamente' 
            })
          }}
        />
      )}
    </>
  )
}

// Componente auxiliar para cada fuente
interface SourceCardProps {
  source: MarketSource
  onDelete: (id: number, name: string) => void
  onEdit: (source: MarketSource) => void
  deleting: boolean
  formatPrice: (price: number | null) => string
  formatDate: (date: string | null) => string
  getFreshness: (date: string | null) => 'fresh' | 'stale' | 'never'
  canDelete: boolean
}

function SourceCard({ source, onDelete, onEdit, deleting, formatPrice, formatDate, getFreshness, canDelete }: SourceCardProps) {
  const freshness = getFreshness(source.last_checked_at)
  
  return (
    <div 
      className="source-card"
      style={{
        padding: 16,
        border: '1px solid var(--border-color)',
        borderRadius: 8,
        background: 'var(--panel-bg)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
            <strong style={{ fontSize: 16 }}>{source.source_name}</strong>
            {source.source_type === 'dynamic' && (
              <span 
                style={{ 
                  fontSize: 11, 
                  padding: '2px 6px', 
                  background: '#3b82f6', 
                  color: 'white', 
                  borderRadius: 4,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4
                }}
                title="Esta fuente usa scraping dinámico (JavaScript requerido)"
              >
                ⚡ Dynamic
              </span>
            )}
            {freshness === 'fresh' && (
              <span style={{ fontSize: 11, padding: '2px 6px', background: '#22c55e', color: 'white', borderRadius: 4 }}>
                Actualizado
              </span>
            )}
            {freshness === 'stale' && (
              <span style={{ fontSize: 11, padding: '2px 6px', background: '#f59e0b', color: 'white', borderRadius: 4 }}>
                Desactualizado
              </span>
            )}
            {freshness === 'never' && (
              <span style={{ fontSize: 11, padding: '2px 6px', background: '#6b7280', color: 'white', borderRadius: 4 }}>
                Sin datos
              </span>
            )}
          </div>
          <a 
            href={source.url} 
            target="_blank" 
            rel="noopener noreferrer"
            style={{ fontSize: 12, color: 'var(--primary)', textDecoration: 'none', wordBreak: 'break-all' }}
          >
            {source.url} ↗
          </a>
        </div>
        {canDelete && (
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              className="btn-secondary"
              onClick={() => onEdit(source)}
              disabled={deleting}
              style={{ padding: '4px 8px', fontSize: 12 }}
              title="Editar fuente"
            >
              ✏️
            </button>
            <button
              className="btn-secondary"
              onClick={() => onDelete(source.id, source.source_name)}
              disabled={deleting}
              style={{ padding: '4px 8px', fontSize: 12 }}
              title="Eliminar fuente"
            >
              🗑️
            </button>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 24, marginTop: 12 }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 2 }}>Último precio</div>
          <div style={{ fontSize: 18, fontWeight: 'bold', color: source.last_price ? 'var(--primary)' : 'var(--text-secondary)' }}>
            {formatPrice(source.last_price)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 2 }}>Última actualización</div>
          <div style={{ fontSize: 14 }}>
            {formatDate(source.last_checked_at)}
          </div>
        </div>
      </div>
    </div>
  )
}
