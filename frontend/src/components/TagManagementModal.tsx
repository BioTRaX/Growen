// NG-HEADER: Nombre de archivo: TagManagementModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/TagManagementModal.tsx
// NG-HEADER: Descripción: Modal para gestionar tags de productos (búsqueda, creación y asignación)
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState, useMemo } from 'react'
import { listTags, createTag, Tag, assignTagsToProduct, removeTagFromProduct, bulkAssignTags } from '../services/tags'
import { showToast } from './Toast'

interface Props {
  open: boolean
  onClose: () => void
  productIds: number[] // Si es un solo producto, mostrar tags actuales; si son varios, modo bulk
  currentTags?: Array<{ id: number; name: string }> // Tags actuales del producto (solo para modo single)
  onSuccess?: () => void
  theme?: {
    bg: string
    card: string
    border: string
    title: string
    text: string
    accentGreen: string
    radius: number
  }
}

export default function TagManagementModal({ open, onClose, productIds, currentTags: initialCurrentTags, onSuccess, theme }: Props) {
  const isSingleProduct = productIds.length === 1
  const [searchQuery, setSearchQuery] = useState('')
  const [availableTags, setAvailableTags] = useState<Tag[]>([])
  const [currentTags, setCurrentTags] = useState<Tag[]>(initialCurrentTags || [])
  const [selectedTags, setSelectedTags] = useState<Tag[]>([])
  const [newTagName, setNewTagName] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [creatingTag, setCreatingTag] = useState(false)

  // Actualizar currentTags cuando cambian las props
  useEffect(() => {
    if (initialCurrentTags) {
      setCurrentTags(initialCurrentTags)
      // Inicializar selectedTags con los tags actuales para modo edición
      setSelectedTags(initialCurrentTags)
    } else {
      setCurrentTags([])
      setSelectedTags([])
    }
  }, [initialCurrentTags])

  const defaultTheme = {
    bg: '#0d1117',
    card: '#111827',
    border: '#1f2937',
    title: '#f8fafc',
    text: '#e5e7eb',
    accentGreen: '#22c55e',
    radius: 8,
  }
  const finalTheme = theme || defaultTheme

  // Cargar tags disponibles
  useEffect(() => {
    if (!open) return
    let mounted = true
    ;(async () => {
      try {
        setLoading(true)
        const tags = await listTags()
        if (mounted) setAvailableTags(tags)
      } catch (e: any) {
        if (mounted) showToast('error', e?.message || 'Error al cargar tags')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [open])

  // Si es un solo producto, cargar sus tags actuales
  useEffect(() => {
    if (!open || !isSingleProduct) {
      setCurrentTags([])
      return
    }
    // Los tags actuales se obtendrán del producto cuando se pase como prop
    // Por ahora, los tags se cargan desde el producto padre
  }, [open, isSingleProduct])

  // Filtrar tags disponibles según búsqueda
  const filteredTags = useMemo(() => {
    if (!searchQuery.trim()) return availableTags
    const q = searchQuery.toLowerCase()
    return availableTags.filter(t => t.name.toLowerCase().includes(q))
  }, [availableTags, searchQuery])

  // Tags que no están seleccionados ni en los actuales
  const availableToSelect = useMemo(() => {
    const selectedIds = new Set(selectedTags.map(t => t.id))
    const currentIds = new Set(currentTags.map(t => t.id))
    return filteredTags.filter(t => !selectedIds.has(t.id) && !currentIds.has(t.id))
  }, [filteredTags, selectedTags, currentTags])

  const handleCreateTag = async () => {
    const name = newTagName.trim()
    if (!name) {
      showToast('error', 'El nombre del tag no puede estar vacío')
      return
    }
    try {
      setCreatingTag(true)
      const tag = await createTag(name)
      setAvailableTags(prev => [...prev, tag].sort((a, b) => a.name.localeCompare(b.name)))
      setSelectedTags(prev => [...prev, tag])
      setNewTagName('')
      showToast('success', `Tag "${tag.name}" creado`)
    } catch (e: any) {
      showToast('error', e?.message || 'Error al crear tag')
    } finally {
      setCreatingTag(false)
    }
  }

  const handleAddTag = (tag: Tag) => {
    if (!selectedTags.find(t => t.id === tag.id)) {
      setSelectedTags(prev => [...prev, tag])
    }
  }

  const handleRemoveSelected = (tagId: number) => {
    setSelectedTags(prev => prev.filter(t => t.id !== tagId))
  }

  const handleRemoveCurrent = (tagId: number) => {
    setCurrentTags(prev => prev.filter(t => t.id !== tagId))
  }

  const handleSave = async () => {
    if (selectedTags.length === 0 && (!isSingleProduct || currentTags.length === 0)) {
      showToast('info', 'No hay cambios para guardar')
      return
    }

    try {
      setSaving(true)
      const tagNames = selectedTags.map(t => t.name)

      if (isSingleProduct) {
        // Modo single: asignar tags seleccionados y remover los que se quitaron de currentTags
        const productId = productIds[0]
        
        // Primero asignar los nuevos tags
        if (tagNames.length > 0) {
          await assignTagsToProduct(productId, tagNames)
        }

        // Luego remover los tags que estaban en currentTags pero no en selectedTags
        const tagsToRemove = currentTags.filter(ct => !selectedTags.find(st => st.id === ct.id))
        for (const tag of tagsToRemove) {
          try {
            await removeTagFromProduct(productId, tag.id)
          } catch (e) {
            // Continuar aunque falle alguno
            console.error('Error al remover tag', e)
          }
        }

        showToast('success', 'Tags actualizados')
      } else {
        // Modo bulk: asignar tags a todos los productos
        await bulkAssignTags(productIds, tagNames)
        showToast('success', `Tags asignados a ${productIds.length} productos`)
      }

      if (onSuccess) onSuccess()
      onClose()
    } catch (e: any) {
      showToast('error', e?.message || 'Error al guardar tags')
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className="panel"
        style={{
          padding: 24,
          minWidth: 520,
          maxWidth: '90vw',
          background: finalTheme.card,
          border: `1px solid ${finalTheme.border}`,
          borderRadius: finalTheme.radius,
          color: finalTheme.text,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ marginTop: 0, color: finalTheme.title }}>
          {isSingleProduct ? 'Gestionar Tags' : `Gestionar Tags (${productIds.length} productos)`}
        </h3>

        {/* Tags actuales (solo para un solo producto) */}
        {isSingleProduct && currentTags.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: finalTheme.title }}>
              Tags actuales
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {currentTags.map(tag => (
                <div
                  key={tag.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 12px',
                    background: finalTheme.bg,
                    border: `1px solid ${finalTheme.border}`,
                    borderRadius: 6,
                    fontSize: 13,
                  }}
                >
                  <span>{tag.name}</span>
                  <button
                    className="btn-secondary"
                    onClick={() => handleRemoveCurrent(tag.id)}
                    style={{
                      padding: '2px 6px',
                      fontSize: 12,
                      minWidth: 'auto',
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tags seleccionados */}
        {selectedTags.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: finalTheme.title }}>
              Tags a {isSingleProduct ? 'asignar' : 'asignar a todos'}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {selectedTags.map(tag => (
                <div
                  key={tag.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 12px',
                    background: finalTheme.accentGreen + '20',
                    border: `1px solid ${finalTheme.accentGreen}`,
                    borderRadius: 6,
                    fontSize: 13,
                  }}
                >
                  <span>{tag.name}</span>
                  <button
                    className="btn-secondary"
                    onClick={() => handleRemoveSelected(tag.id)}
                    style={{
                      padding: '2px 6px',
                      fontSize: 12,
                      minWidth: 'auto',
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Búsqueda de tags */}
        <div style={{ marginBottom: 16 }}>
          <label className="label" style={{ marginBottom: 8, display: 'block' }}>
            Buscar tags
          </label>
          <input
            className="input"
            type="text"
            placeholder="Buscar tags existentes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: '100%' }}
          />
        </div>

        {/* Lista de tags disponibles */}
        {loading ? (
          <div style={{ padding: 16, textAlign: 'center', opacity: 0.7 }}>Cargando tags...</div>
        ) : (
          <div style={{ marginBottom: 16, maxHeight: 200, overflowY: 'auto' }}>
            {availableToSelect.length === 0 ? (
              <div style={{ padding: 16, textAlign: 'center', opacity: 0.7 }}>
                {searchQuery ? 'No se encontraron tags' : 'No hay tags disponibles'}
              </div>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {availableToSelect.map(tag => (
                  <button
                    key={tag.id}
                    className="btn-secondary"
                    onClick={() => handleAddTag(tag)}
                    style={{ fontSize: 13 }}
                  >
                    + {tag.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Crear nuevo tag */}
        <div style={{ marginBottom: 16, padding: 12, background: finalTheme.bg, borderRadius: 6 }}>
          <label className="label" style={{ marginBottom: 8, display: 'block' }}>
            Crear nuevo tag
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              className="input"
              type="text"
              placeholder="Nombre del tag..."
              value={newTagName}
              onChange={(e) => setNewTagName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreateTag()
              }}
              style={{ flex: 1 }}
            />
            <button
              className="btn-primary"
              onClick={handleCreateTag}
              disabled={creatingTag || !newTagName.trim()}
            >
              {creatingTag ? 'Creando...' : 'Crear'}
            </button>
          </div>
        </div>

        {/* Botones de acción */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 24 }}>
          <button className="btn-secondary" onClick={onClose} disabled={saving}>
            Cancelar
          </button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  )
}

