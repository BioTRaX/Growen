// NG-HEADER: Nombre de archivo: MassCanonicalWizard.tsx
// NG-HEADER: Ubicación: frontend/src/components/MassCanonicalWizard.tsx
// NG-HEADER: Descripción: Wizard para alta masiva de productos canónicos paso a paso
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useEffect, useState, useMemo } from 'react'
import { useMassCanonical } from '../contexts/MassCanonicalContext'
import { listCategories, Category } from '../services/categories'
import { getNextSeq } from '../services/canonical'
import { useToast } from './ToastProvider'

// ============================================================================
// TIPOS
// ============================================================================

type WizardStep = 'initial' | 'editing' | 'final'

interface Props {
    open: boolean
    onClose: () => void
    onComplete: () => void
}

// ============================================================================
// COMPONENTE PRINCIPAL
// ============================================================================

export default function MassCanonicalWizard({ open, onClose, onComplete }: Props) {
    const { push } = useToast()
    const massCanonical = useMassCanonical()
    const { state, updateCurrentDraft, nextStep, prevStep, getCurrentProduct, getCurrentDraft, getProgress, isFirstProduct, isLastProduct } = massCanonical

    // Estado local del wizard
    const [step, setStep] = useState<WizardStep>('initial')
    const [categories, setCategories] = useState<Category[]>([])
    const [loadingCategories, setLoadingCategories] = useState(false)

    // Campos del formulario (sincronizados con el draft actual)
    const [name, setName] = useState('')
    const [categoryId, setCategoryId] = useState<number | ''>('')
    const [subcategoryId, setSubcategoryId] = useState<number | ''>('')

    // SKUs generados en esta sesión para evitar duplicados
    const [generatedSkus, setGeneratedSkus] = useState<Set<string>>(new Set())

    // Cargar categorías al abrir
    useEffect(() => {
        if (open && categories.length === 0) {
            setLoadingCategories(true)
            listCategories()
                .then(setCategories)
                .catch(() => push({ kind: 'error', message: 'Error cargando categorías' }))
                .finally(() => setLoadingCategories(false))
        }
    }, [open])

    // Sincronizar campos con el draft actual cuando cambia el índice
    useEffect(() => {
        if (step === 'editing') {
            const draft = getCurrentDraft()
            const product = getCurrentProduct()
            if (draft) {
                setName(draft.name || product?.preferred_name || '')
                setCategoryId(draft.categoryId ?? '')
                setSubcategoryId(draft.subcategoryId ?? '')
            }
        }
    }, [step, state.currentIndex])

    // Reset al cerrar
    useEffect(() => {
        if (!open) {
            setStep('initial')
        }
    }, [open])

    // Categorías principales (sin parent_id) - Hook debe estar antes de cualquier return condicional
    const mainCategories = useMemo(() => categories.filter(c => !c.parent_id), [categories])

    // ============================================================================
    // HELPERS
    // ============================================================================

    /**
     * Genera un SKU automático basado en categoría y subcategoría.
     * Evita duplicados dentro de la sesión actual.
     */
    async function generateSku(catId: number | null, subId: number | null): Promise<string> {
        try {
            let seq = await getNextSeq(catId)

            // Ajustar secuencia si ya hay SKUs generados con el mismo prefijo
            const catName = categories.find(c => c.id === catId)?.name || ''
            const subName = categories.find(c => c.id === subId)?.name || 'GEN'

            const seg = (s: string) => s.normalize('NFD').replace(/[^A-Za-z]/g, '').toUpperCase().slice(0, 3).padEnd(3, 'X')
            const catSeg = seg(catName)
            const subSeg = seg(subName)

            // Buscar un número de secuencia que no esté ya usado en la sesión
            let sku = `${catSeg}_${String(seq).padStart(4, '0')}_${subSeg}`
            while (generatedSkus.has(sku)) {
                seq++
                sku = `${catSeg}_${String(seq).padStart(4, '0')}_${subSeg}`
            }

            return sku
        } catch (error) {
            // Fallback: generar SKU con timestamp
            const ts = Date.now().toString(36).toUpperCase()
            return `TMP_${ts}`
        }
    }

    /**
     * Guarda el borrador actual con SKU generado y avanza al siguiente
     */
    async function handleNextProduct() {
        // Generar SKU automáticamente
        const catId = typeof categoryId === 'number' ? categoryId : null
        const subId = typeof subcategoryId === 'number' ? subcategoryId : null
        const sku = await generateSku(catId, subId)

        // Registrar SKU como usado en esta sesión
        setGeneratedSkus(prev => new Set(prev).add(sku))

        // Actualizar el draft con los datos actuales
        updateCurrentDraft({
            name: name.trim(),
            categoryId: catId,
            subcategoryId: subId,
            specsJson: { generatedSku: sku },
            isComplete: true,
        })

        // Si es el último, ir al paso final
        if (isLastProduct()) {
            setStep('final')
        } else {
            // Avanzar al siguiente y cargar sus datos
            nextStep()
            const nextDraft = getCurrentDraft()
            const nextProduct = getCurrentProduct()
            if (nextDraft) {
                setName(nextDraft.name || nextProduct?.preferred_name || '')
                setCategoryId(nextDraft.categoryId ?? '')
                setSubcategoryId(nextDraft.subcategoryId ?? '')
            }
        }
    }

    /**
     * Retrocede al producto anterior
     */
    function handlePrevProduct() {
        // Guardar estado actual antes de retroceder
        updateCurrentDraft({
            name: name.trim(),
            categoryId: typeof categoryId === 'number' ? categoryId : null,
            subcategoryId: typeof subcategoryId === 'number' ? subcategoryId : null,
        })

        prevStep()
    }

    /**
     * Cancela la sesión (cierra modal pero mantiene estado en localStorage)
     */
    function handleCancelSession() {
        // Guardar estado actual antes de cerrar
        updateCurrentDraft({
            name: name.trim(),
            categoryId: typeof categoryId === 'number' ? categoryId : null,
            subcategoryId: typeof subcategoryId === 'number' ? subcategoryId : null,
        })

        push({ kind: 'info', message: 'Sesión guardada. Podrás continuar después.' })
        onClose()
    }

    /**
     * Inicia el wizard desde el paso inicial
     */
    function handleStart() {
        setStep('editing')
        const draft = getCurrentDraft()
        const product = getCurrentProduct()
        if (draft) {
            setName(draft.name || product?.preferred_name || '')
            setCategoryId(draft.categoryId ?? '')
            setSubcategoryId(draft.subcategoryId ?? '')
        }
    }

    /**
     * Confirma y procesa todos los productos
     */
    function handleConfirmAndProcess() {
        onComplete()
    }

    // ============================================================================
    // RENDER
    // ============================================================================

    if (!open || !state.isActive) return null

    const progress = getProgress()
    const currentProduct = getCurrentProduct()

    // Subcategorías (para el dropdown de relacionadas mostramos todas)
    const allCategories = categories

    return (
        <div
            className="modal-backdrop"
            style={{
                background: 'rgba(0, 0, 0, 0.8)',
            }}
        // No cerrar al hacer clic en backdrop
        >
            <div
                className="modal"
                style={{
                    maxWidth: step === 'editing' ? 600 : 480,
                    background: 'var(--panel-bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    padding: 0,
                    overflow: 'hidden',
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* ================================================================ */}
                {/* PASO INICIAL */}
                {/* ================================================================ */}
                {step === 'initial' && (
                    <div style={{ padding: 32, textAlign: 'center' }}>
                        <div style={{ fontSize: 56, marginBottom: 16 }}>📦</div>
                        <h2 style={{ margin: 0, marginBottom: 8, color: 'var(--text-color)' }}>
                            Alta Masiva de Productos
                        </h2>
                        <p style={{
                            margin: 0,
                            marginBottom: 24,
                            color: 'var(--text-secondary)',
                            fontSize: 16,
                        }}>
                            Vas a dar de alta <strong style={{ color: 'var(--primary)', fontSize: 20 }}>{progress.total}</strong> producto{progress.total !== 1 ? 's' : ''} canónico{progress.total !== 1 ? 's' : ''}
                        </p>
                        <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
                            <button
                                className="btn-secondary"
                                onClick={onClose}
                                style={{ padding: '12px 24px', borderRadius: 8 }}
                            >
                                Cancelar
                            </button>
                            <button
                                className="btn-dark"
                                onClick={handleStart}
                                style={{
                                    padding: '12px 32px',
                                    borderRadius: 8,
                                    background: 'var(--success)',
                                    color: 'white',
                                    fontWeight: 600,
                                }}
                            >
                                Comenzar
                            </button>
                        </div>
                    </div>
                )}

                {/* ================================================================ */}
                {/* PASO DE EDICIÓN */}
                {/* ================================================================ */}
                {step === 'editing' && currentProduct && (
                    <>
                        {/* Header con progreso */}
                        <div style={{
                            padding: '16px 24px',
                            borderBottom: '1px solid var(--border)',
                            background: 'var(--table-header-bg)',
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <h3 style={{ margin: 0, fontSize: 16, color: 'var(--text-color)' }}>
                                    Producto {progress.current} de {progress.total}
                                </h3>
                                <span style={{
                                    fontSize: 14,
                                    background: 'var(--primary)',
                                    padding: '4px 12px',
                                    borderRadius: 20,
                                    color: 'white',
                                }}>
                                    {progress.percentage}%
                                </span>
                            </div>
                            {/* Barra de progreso */}
                            <div style={{
                                marginTop: 12,
                                height: 4,
                                background: 'var(--border)',
                                borderRadius: 2,
                                overflow: 'hidden',
                            }}>
                                <div style={{
                                    width: `${progress.percentage}%`,
                                    height: '100%',
                                    background: 'var(--primary)',
                                    transition: 'width 0.3s ease',
                                }} />
                            </div>
                        </div>

                        {/* Contenido */}
                        <div style={{ padding: 24 }}>
                            {/* Referencia del producto original */}
                            <div style={{
                                marginBottom: 20,
                                padding: 12,
                                background: 'rgba(59, 130, 246, 0.1)',
                                borderRadius: 8,
                                border: '1px solid rgba(59, 130, 246, 0.2)',
                            }}>
                                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
                                    Producto original Proveedor:
                                </div>
                                <div style={{ fontWeight: 500, color: 'var(--text-color)' }}>
                                    {currentProduct.preferred_name}
                                </div>
                                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                                    SKU: {currentProduct.product_sku}
                                </div>
                            </div>

                            {/* Formulario */}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                                {/* Nombre */}
                                <div>
                                    <label style={{
                                        display: 'block',
                                        marginBottom: 6,
                                        fontWeight: 500,
                                        color: 'var(--text-color)',
                                        fontSize: 14,
                                    }}>
                                        Nombre del producto canónico *
                                    </label>
                                    <input
                                        className="input w-full"
                                        placeholder="Nombre del producto"
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        style={{ fontSize: 15 }}
                                    />
                                </div>

                                {/* Categoría y Subcategoría en grid */}
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                                    {/* Categoría */}
                                    <div>
                                        <label style={{
                                            display: 'block',
                                            marginBottom: 6,
                                            fontWeight: 500,
                                            color: 'var(--text-color)',
                                            fontSize: 14,
                                        }}>
                                            Categoría
                                        </label>
                                        <select
                                            className="select w-full"
                                            value={categoryId === '' ? '' : String(categoryId)}
                                            onChange={(e) => {
                                                const val = e.target.value ? Number(e.target.value) : ''
                                                setCategoryId(val)
                                                // Limpiar subcategoría al cambiar categoría
                                                setSubcategoryId('')
                                            }}
                                            disabled={loadingCategories}
                                        >
                                            <option value="">Sin categoría</option>
                                            {mainCategories.map(c => (
                                                <option key={c.id} value={c.id}>{c.name}</option>
                                            ))}
                                        </select>
                                    </div>

                                    {/* Subcategoría / Categoría relacionada */}
                                    <div>
                                        <label style={{
                                            display: 'block',
                                            marginBottom: 6,
                                            fontWeight: 500,
                                            color: 'var(--text-color)',
                                            fontSize: 14,
                                        }}>
                                            Categoría relacionada
                                        </label>
                                        <select
                                            className="select w-full"
                                            value={subcategoryId === '' ? '' : String(subcategoryId)}
                                            onChange={(e) => setSubcategoryId(e.target.value ? Number(e.target.value) : '')}
                                            disabled={loadingCategories}
                                        >
                                            <option value="">(ninguna)</option>
                                            {allCategories.map(c => (
                                                <option key={c.id} value={c.id}>{c.name}</option>
                                            ))}
                                        </select>
                                    </div>
                                </div>

                                {/* Info: SKU se genera automáticamente */}
                                <div style={{
                                    fontSize: 12,
                                    color: 'var(--text-secondary)',
                                    fontStyle: 'italic',
                                }}>
                                    💡 El SKU se generará automáticamente al avanzar
                                </div>
                            </div>
                        </div>

                        {/* Footer con botones */}
                        <div style={{
                            padding: '16px 24px',
                            borderTop: '1px solid var(--border)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            background: 'var(--table-header-bg)',
                        }}>
                            <div style={{ display: 'flex', gap: 8 }}>
                                {!isFirstProduct() && (
                                    <button
                                        className="btn-secondary"
                                        onClick={handlePrevProduct}
                                        style={{ padding: '10px 16px' }}
                                    >
                                        ← Anterior
                                    </button>
                                )}
                                <button
                                    className="btn"
                                    onClick={handleCancelSession}
                                    style={{
                                        padding: '10px 16px',
                                        color: '#ef4444',
                                        borderColor: '#ef4444',
                                    }}
                                >
                                    Cancelar Sesión
                                </button>
                            </div>
                            <button
                                className="btn-dark"
                                onClick={handleNextProduct}
                                disabled={!name.trim()}
                                style={{
                                    padding: '10px 24px',
                                    background: 'var(--success)',
                                    color: 'white',
                                    fontWeight: 600,
                                }}
                            >
                                {isLastProduct() ? 'Finalizar ✓' : 'Siguiente →'}
                            </button>
                        </div>
                    </>
                )}

                {/* ================================================================ */}
                {/* PASO FINAL */}
                {/* ================================================================ */}
                {step === 'final' && (
                    <div style={{ padding: 32, textAlign: 'center' }}>
                        <div style={{ fontSize: 56, marginBottom: 16 }}>✅</div>
                        <h2 style={{ margin: 0, marginBottom: 8, color: 'var(--text-color)' }}>
                            ¡Listos para crear!
                        </h2>
                        <p style={{
                            margin: 0,
                            marginBottom: 24,
                            color: 'var(--text-secondary)',
                            fontSize: 16,
                        }}>
                            Se crearán <strong style={{ color: 'var(--success)', fontSize: 20 }}>{progress.total}</strong> producto{progress.total !== 1 ? 's' : ''} canónico{progress.total !== 1 ? 's' : ''}
                        </p>

                        {/* Resumen de productos */}
                        <div style={{
                            maxHeight: 200,
                            overflow: 'auto',
                            marginBottom: 24,
                            border: '1px solid var(--border)',
                            borderRadius: 8,
                            textAlign: 'left',
                        }}>
                            {state.processedDrafts.map((draft, idx) => (
                                <div
                                    key={draft.sourceProductId}
                                    style={{
                                        padding: '8px 12px',
                                        borderBottom: idx < state.processedDrafts.length - 1 ? '1px solid var(--border)' : 'none',
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center',
                                    }}
                                >
                                    <span style={{ fontSize: 14 }}>{draft.name}</span>
                                    <span style={{
                                        fontSize: 11,
                                        color: 'var(--text-secondary)',
                                        fontFamily: 'monospace',
                                    }}>
                                        {(draft.specsJson as any)?.generatedSku || '—'}
                                    </span>
                                </div>
                            ))}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
                            <button
                                className="btn-secondary"
                                onClick={() => {
                                    // Volver al último producto para corregir
                                    setStep('editing')
                                }}
                                style={{ padding: '12px 24px', borderRadius: 8 }}
                            >
                                ← Volver a revisar
                            </button>
                            <button
                                className="btn-dark"
                                onClick={handleConfirmAndProcess}
                                style={{
                                    padding: '12px 32px',
                                    borderRadius: 8,
                                    background: 'var(--success)',
                                    color: 'white',
                                    fontWeight: 600,
                                }}
                            >
                                Confirmar y Procesar
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
