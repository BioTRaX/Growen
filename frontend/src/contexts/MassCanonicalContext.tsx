// NG-HEADER: Nombre de archivo: MassCanonicalContext.tsx
// NG-HEADER: Ubicación: frontend/src/contexts/MassCanonicalContext.tsx
// NG-HEADER: Descripción: Contexto para flujo de Alta Masiva de Productos Canónicos con persistencia
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react'

// ============================================================================
// TIPOS
// ============================================================================

/**
 * Producto del Mercado (origen) - datos mínimos necesarios
 */
export interface MarketProductSource {
    product_id: number
    preferred_name: string
    product_sku: string
    category_id: number | null
    category_name: string | null
    supplier_id: number | null
    supplier_name: string | null
}

/**
 * Borrador configurado por el usuario para cada producto
 */
export interface MarketProductDraft {
    sourceProductId: number           // ID del producto origen del mercado
    name: string                      // Nombre configurado
    brand: string | null              // Marca
    categoryId: number | null         // Categoría seleccionada
    subcategoryId: number | null      // Subcategoría (categoría relacionada)
    specsJson: Record<string, any>    // Especificaciones adicionales
    isComplete: boolean               // Si está listo para enviar
}

/**
 * Estado global de la sesión de alta masiva
 */
export interface MassCanonicalState {
    sourceProducts: MarketProductSource[]   // Productos seleccionados del Mercado
    processedDrafts: MarketProductDraft[]   // Borradores configurados
    currentIndex: number                    // Índice actual (0-based)
    isActive: boolean                       // Si el flujo está activo
}

/**
 * Interfaz del contexto expuesto a los consumidores
 */
export interface MassCanonicalContextShape {
    state: MassCanonicalState

    // Acciones principales
    startSession: (products: MarketProductSource[]) => void
    updateCurrentDraft: (data: Partial<MarketProductDraft>) => void
    nextStep: () => boolean    // Retorna true si avanzó, false si es el último
    prevStep: () => boolean    // Retorna true si retrocedió, false si es el primero
    clearSession: () => void

    // Recuperación de sesión
    checkRecoverSession: () => boolean
    recoverSession: () => void

    // Helpers
    getCurrentProduct: () => MarketProductSource | null
    getCurrentDraft: () => MarketProductDraft | null
    getProgress: () => { current: number; total: number; percentage: number }
    isLastProduct: () => boolean
    isFirstProduct: () => boolean
}

// ============================================================================
// CONSTANTES
// ============================================================================

export const STORAGE_KEY = 'mass_cannon_session'

const INITIAL_STATE: MassCanonicalState = {
    sourceProducts: [],
    processedDrafts: [],
    currentIndex: 0,
    isActive: false,
}

// ============================================================================
// CONTEXTO
// ============================================================================

const MassCanonicalContext = createContext<MassCanonicalContextShape | undefined>(undefined)

// ============================================================================
// FUNCIONES DE PERSISTENCIA
// ============================================================================

function saveToStorage(state: MassCanonicalState): void {
    try {
        const serialized = JSON.stringify({
            ...state,
            savedAt: Date.now(),
        })
        localStorage.setItem(STORAGE_KEY, serialized)
    } catch (error) {
        // eslint-disable-next-line no-console
        console.warn('[MassCanonical] Error guardando sesión:', error)
    }
}

function loadFromStorage(): MassCanonicalState | null {
    try {
        const raw = localStorage.getItem(STORAGE_KEY)
        if (!raw) return null

        const parsed = JSON.parse(raw)

        // Validar estructura mínima
        if (
            !parsed ||
            !Array.isArray(parsed.sourceProducts) ||
            !Array.isArray(parsed.processedDrafts) ||
            typeof parsed.currentIndex !== 'number' ||
            typeof parsed.isActive !== 'boolean'
        ) {
            // eslint-disable-next-line no-console
            console.warn('[MassCanonical] Sesión inválida en storage, descartando')
            clearStorage()
            return null
        }

        // Reconstruir sin el campo savedAt
        return {
            sourceProducts: parsed.sourceProducts,
            processedDrafts: parsed.processedDrafts,
            currentIndex: parsed.currentIndex,
            isActive: parsed.isActive,
        }
    } catch (error) {
        // eslint-disable-next-line no-console
        console.warn('[MassCanonical] Error leyendo sesión:', error)
        return null
    }
}

function clearStorage(): void {
    try {
        localStorage.removeItem(STORAGE_KEY)
    } catch {
        // Silenciar errores de storage
    }
}

// ============================================================================
// PROVIDER
// ============================================================================

export function MassCanonicalProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<MassCanonicalState>(INITIAL_STATE)

    // Persistir cada vez que cambie el estado (solo si está activo)
    useEffect(() => {
        if (state.isActive) {
            saveToStorage(state)
        }
    }, [state])

    // --------------------------------------------------------------------------
    // Acciones principales
    // --------------------------------------------------------------------------

    /**
     * Inicia una nueva sesión de alta masiva con los productos seleccionados.
     * Crea borradores vacíos para cada producto.
     */
    const startSession = useCallback((products: MarketProductSource[]) => {
        if (products.length === 0) return

        // Crear borradores iniciales para cada producto
        const drafts: MarketProductDraft[] = products.map(p => ({
            sourceProductId: p.product_id,
            name: p.preferred_name,  // Usar nombre por defecto
            brand: null,
            categoryId: p.category_id,
            subcategoryId: null,
            specsJson: {},
            isComplete: false,
        }))

        setState({
            sourceProducts: products,
            processedDrafts: drafts,
            currentIndex: 0,
            isActive: true,
        })
    }, [])

    /**
     * Actualiza el borrador del producto actual con datos parciales.
     */
    const updateCurrentDraft = useCallback((data: Partial<MarketProductDraft>) => {
        setState(prev => {
            if (!prev.isActive || prev.currentIndex >= prev.processedDrafts.length) {
                return prev
            }

            const newDrafts = [...prev.processedDrafts]
            newDrafts[prev.currentIndex] = {
                ...newDrafts[prev.currentIndex],
                ...data,
            }

            return {
                ...prev,
                processedDrafts: newDrafts,
            }
        })
    }, [])

    /**
     * Avanza al siguiente producto. Retorna true si avanzó, false si ya era el último.
     */
    const nextStep = useCallback((): boolean => {
        let advanced = false

        setState(prev => {
            if (!prev.isActive) return prev

            const nextIndex = prev.currentIndex + 1
            if (nextIndex >= prev.sourceProducts.length) {
                // Ya estamos en el último
                return prev
            }

            advanced = true
            return {
                ...prev,
                currentIndex: nextIndex,
            }
        })

        return advanced
    }, [])

    /**
     * Retrocede al producto anterior. Retorna true si retrocedió, false si ya era el primero.
     */
    const prevStep = useCallback((): boolean => {
        let retreated = false

        setState(prev => {
            if (!prev.isActive) return prev

            if (prev.currentIndex <= 0) {
                // Ya estamos en el primero
                return prev
            }

            retreated = true
            return {
                ...prev,
                currentIndex: prev.currentIndex - 1,
            }
        })

        return retreated
    }, [])

    /**
     * Limpia la sesión actual y el storage.
     */
    const clearSession = useCallback(() => {
        setState(INITIAL_STATE)
        clearStorage()
    }, [])

    // --------------------------------------------------------------------------
    // Recuperación de sesión
    // --------------------------------------------------------------------------

    /**
     * Verifica si existe una sesión recuperable en localStorage.
     * No carga la sesión, solo verifica su existencia.
     */
    const checkRecoverSession = useCallback((): boolean => {
        const saved = loadFromStorage()
        return saved !== null && saved.isActive && saved.sourceProducts.length > 0
    }, [])

    /**
     * Recupera la sesión guardada en localStorage.
     */
    const recoverSession = useCallback(() => {
        const saved = loadFromStorage()
        if (saved && saved.isActive) {
            setState(saved)
        }
    }, [])

    // --------------------------------------------------------------------------
    // Helpers
    // --------------------------------------------------------------------------

    /**
     * Obtiene el producto origen actual.
     */
    const getCurrentProduct = useCallback((): MarketProductSource | null => {
        if (!state.isActive || state.currentIndex >= state.sourceProducts.length) {
            return null
        }
        return state.sourceProducts[state.currentIndex]
    }, [state])

    /**
     * Obtiene el borrador actual.
     */
    const getCurrentDraft = useCallback((): MarketProductDraft | null => {
        if (!state.isActive || state.currentIndex >= state.processedDrafts.length) {
            return null
        }
        return state.processedDrafts[state.currentIndex]
    }, [state])

    /**
     * Obtiene el progreso actual del flujo.
     */
    const getProgress = useCallback((): { current: number; total: number; percentage: number } => {
        const total = state.sourceProducts.length
        const current = state.currentIndex + 1
        const percentage = total > 0 ? Math.round((current / total) * 100) : 0

        return { current, total, percentage }
    }, [state])

    /**
     * Verifica si estamos en el último producto.
     */
    const isLastProduct = useCallback((): boolean => {
        return state.currentIndex >= state.sourceProducts.length - 1
    }, [state])

    /**
     * Verifica si estamos en el primer producto.
     */
    const isFirstProduct = useCallback((): boolean => {
        return state.currentIndex === 0
    }, [state])

    // --------------------------------------------------------------------------
    // Render
    // --------------------------------------------------------------------------

    const value: MassCanonicalContextShape = {
        state,
        startSession,
        updateCurrentDraft,
        nextStep,
        prevStep,
        clearSession,
        checkRecoverSession,
        recoverSession,
        getCurrentProduct,
        getCurrentDraft,
        getProgress,
        isLastProduct,
        isFirstProduct,
    }

    return (
        <MassCanonicalContext.Provider value={value}>
            {children}
        </MassCanonicalContext.Provider>
    )
}

// ============================================================================
// HOOK
// ============================================================================

/**
 * Hook para acceder al contexto de Alta Masiva.
 * Debe usarse dentro de MassCanonicalProvider.
 */
export function useMassCanonical(): MassCanonicalContextShape {
    const ctx = useContext(MassCanonicalContext)
    if (!ctx) {
        throw new Error('useMassCanonical debe usarse dentro de MassCanonicalProvider')
    }
    return ctx
}
