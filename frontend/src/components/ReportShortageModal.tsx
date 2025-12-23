// NG-HEADER: Nombre de archivo: ReportShortageModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/ReportShortageModal.tsx
// NG-HEADER: Descripción: Modal para reportar un faltante de stock
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState, useEffect } from 'react'
import { createShortage, ShortageReason, REASON_LABELS } from '../services/shortages'
import { searchProducts, ProductItem } from '../services/products'
import { useToast } from './ToastProvider'

interface Props {
    open: boolean
    onClose: () => void
    onSuccess?: () => void
}

export default function ReportShortageModal({ open, onClose, onSuccess }: Props) {
    const { push } = useToast()
    const [products, setProducts] = useState<ProductItem[]>([])
    const [loading, setLoading] = useState(false)
    const [submitting, setSubmitting] = useState(false)
    const [search, setSearch] = useState('')
    const [selectedProduct, setSelectedProduct] = useState<ProductItem | null>(null)
    const [quantity, setQuantity] = useState('')
    const [reason, setReason] = useState<ShortageReason>('UNKNOWN')
    const [observation, setObservation] = useState('')
    const [showDropdown, setShowDropdown] = useState(false)

    // Cargar productos disponibles
    useEffect(() => {
        if (!open) return
        setLoading(true)
        searchProducts({ page: 1, page_size: 500 })
            .then((r) => setProducts(r.items))
            .catch(() => push({ kind: 'error', message: 'Error cargando productos' }))
            .finally(() => setLoading(false))
    }, [open])

    // Filtrar productos por búsqueda
    const filteredProducts = products.filter(
        (p) =>
            p.name.toLowerCase().includes(search.toLowerCase()) ||
            (p.canonical_sku && p.canonical_sku.toLowerCase().includes(search.toLowerCase())) ||
            (p.first_variant_sku && p.first_variant_sku.toLowerCase().includes(search.toLowerCase()))
    )

    const handleSelectProduct = (product: ProductItem) => {
        setSelectedProduct(product)
        setSearch(product.name || '')
        setShowDropdown(false)
    }

    const handleSubmit = async () => {
        if (!selectedProduct) {
            push({ kind: 'error', message: 'Debes seleccionar un producto' })
            return
        }
        const qty = parseInt(quantity)
        if (isNaN(qty) || qty <= 0) {
            push({ kind: 'error', message: 'La cantidad debe ser mayor a 0' })
            return
        }

        // Warning si el stock quedará negativo
        const newStock = (selectedProduct.stock ?? 0) - qty
        if (newStock < 0) {
            const confirm = window.confirm(
                `El stock quedará negativo (${newStock}). ¿Deseas continuar?`
            )
            if (!confirm) return
        }

        setSubmitting(true)
        try {
            const result = await createShortage({
                product_id: selectedProduct.product_id,
                quantity: qty,
                reason,
                observation: observation || undefined,
            })

            let msg = 'Faltante registrado correctamente'
            if (result.warning) {
                msg += ` (${result.warning})`
            }
            push({ kind: 'success', message: msg })

            // Resetear formulario
            setSelectedProduct(null)
            setSearch('')
            setQuantity('')
            setReason('UNKNOWN')
            setObservation('')

            onSuccess?.()
            onClose()
        } catch (e: any) {
            push({ kind: 'error', message: e?.response?.data?.detail || 'Error al registrar faltante' })
        } finally {
            setSubmitting(false)
        }
    }

    if (!open) return null

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div
                className="modal"
                style={{ maxWidth: 520, maxHeight: '90vh', overflow: 'auto' }}
                onClick={(e) => e.stopPropagation()}
            >
                <h3 style={{ marginTop: 0 }}>Reportar Faltante de Stock</h3>

                {/* Selector de producto */}
                <div style={{ marginBottom: 16 }}>
                    <label style={{ fontWeight: 500, display: 'block', marginBottom: 6 }}>
                        Producto *
                    </label>
                    <div style={{ position: 'relative' }}>
                        <input
                            className="input w-full"
                            placeholder="Buscar producto por nombre o SKU..."
                            value={search}
                            onChange={(e) => {
                                setSearch(e.target.value)
                                setShowDropdown(true)
                                if (!e.target.value) setSelectedProduct(null)
                            }}
                            onFocus={() => setShowDropdown(true)}
                        />
                        {showDropdown && search && (
                            <div
                                className="dropdown-panel"
                                style={{
                                    position: 'absolute',
                                    top: '100%',
                                    left: 0,
                                    right: 0,
                                    maxHeight: 200,
                                    overflow: 'auto',
                                    zIndex: 100,
                                    marginTop: 4,
                                }}
                            >
                                {loading ? (
                                    <div style={{ padding: 12, color: 'var(--muted)' }}>Cargando...</div>
                                ) : filteredProducts.length === 0 ? (
                                    <div style={{ padding: 12, color: 'var(--muted)' }}>No se encontraron productos</div>
                                ) : (
                                    filteredProducts.slice(0, 20).map((p) => (
                                        <div
                                            key={p.product_id}
                                            onClick={() => handleSelectProduct(p)}
                                            style={{
                                                padding: '10px 12px',
                                                cursor: 'pointer',
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                borderBottom: '1px solid var(--border)',
                                            }}
                                            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--table-row-hover)')}
                                            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                                        >
                                            <span style={{ flex: 1 }}>{p.name}</span>
                                            <span
                                                style={{
                                                    padding: '2px 8px',
                                                    borderRadius: 8,
                                                    fontSize: '0.85rem',
                                                    background: (p.stock ?? 0) <= 5 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(34, 197, 94, 0.2)',
                                                    color: (p.stock ?? 0) <= 5 ? '#f87171' : 'var(--success)',
                                                }}
                                            >
                                                Stock: {p.stock ?? 0}
                                            </span>
                                        </div>
                                    ))
                                )}
                            </div>
                        )}
                    </div>
                    {selectedProduct && (
                        <div style={{ marginTop: 8, fontSize: '0.9rem', color: 'var(--muted)' }}>
                            Producto seleccionado: <strong>{selectedProduct.name}</strong> (Stock actual: {selectedProduct.stock ?? 0})
                        </div>
                    )}
                </div>

                {/* Cantidad */}
                <div style={{ marginBottom: 16 }}>
                    <label style={{ fontWeight: 500, display: 'block', marginBottom: 6 }}>
                        Cantidad a descontar *
                    </label>
                    <input
                        type="number"
                        className="input"
                        style={{ width: 120 }}
                        placeholder="0"
                        min="1"
                        value={quantity}
                        onChange={(e) => setQuantity(e.target.value)}
                    />
                </div>

                {/* Motivo */}
                <div style={{ marginBottom: 16 }}>
                    <label style={{ fontWeight: 500, display: 'block', marginBottom: 6 }}>
                        Motivo *
                    </label>
                    <select
                        className="select"
                        value={reason}
                        onChange={(e) => setReason(e.target.value as ShortageReason)}
                    >
                        {Object.entries(REASON_LABELS).map(([key, label]) => (
                            <option key={key} value={key}>
                                {label}
                            </option>
                        ))}
                    </select>
                </div>

                {/* Observación */}
                <div style={{ marginBottom: 16 }}>
                    <label style={{ fontWeight: 500, display: 'block', marginBottom: 6 }}>
                        Observación (opcional)
                    </label>
                    <textarea
                        className="input"
                        style={{ width: '100%', minHeight: 80, resize: 'vertical' }}
                        placeholder="Detalles adicionales..."
                        value={observation}
                        onChange={(e) => setObservation(e.target.value)}
                    />
                </div>

                {/* Warning si stock negativo */}
                {selectedProduct && quantity && parseInt(quantity) > (selectedProduct.stock ?? 0) && (
                    <div
                        style={{
                            padding: '10px 12px',
                            marginBottom: 16,
                            background: 'rgba(234, 179, 8, 0.15)',
                            border: '1px solid rgba(234, 179, 8, 0.4)',
                            borderRadius: 8,
                            color: '#fbbf24',
                            fontSize: '0.9rem',
                        }}
                    >
                        ⚠️ El stock quedará negativo: {(selectedProduct.stock ?? 0) - parseInt(quantity)}
                    </div>
                )}

                {/* Botones */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
                    <button className="btn" onClick={onClose} disabled={submitting}>
                        Cancelar
                    </button>
                    <button className="btn-dark" onClick={handleSubmit} disabled={submitting || !selectedProduct}>
                        {submitting ? 'Guardando...' : 'Registrar Faltante'}
                    </button>
                </div>
            </div>
        </div>
    )
}
