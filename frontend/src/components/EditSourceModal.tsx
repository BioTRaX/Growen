import { useState, useEffect } from 'react'
import { updateMarketSource, type UpdateMarketSourceRequest } from '../services/market'

interface EditSourceModalProps {
  sourceId: number
  currentData: {
    source_name: string
    url: string
    last_price: number | null
    is_mandatory: boolean
  }
  open: boolean
  onClose: () => void
  onSuccess: () => void
}

export default function EditSourceModal({
  sourceId,
  currentData,
  open,
  onClose,
  onSuccess,
}: EditSourceModalProps) {
  const [sourceName, setSourceName] = useState(currentData.source_name)
  const [url, setUrl] = useState(currentData.url)
  const [lastPrice, setLastPrice] = useState(currentData.last_price?.toString() || '')
  const [isMandatory, setIsMandatory] = useState(currentData.is_mandatory)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset form when modal opens with new data
  useEffect(() => {
    if (open) {
      setSourceName(currentData.source_name)
      setUrl(currentData.url)
      setLastPrice(currentData.last_price?.toString() || '')
      setIsMandatory(currentData.is_mandatory)
      setError(null)
    }
  }, [open, currentData])

  const handleSave = async () => {
    setError(null)

    // Validation
    if (!sourceName.trim()) {
      setError('El nombre de la fuente es obligatorio')
      return
    }
    if (!url.trim()) {
      setError('La URL es obligatoria')
      return
    }
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      setError('La URL debe comenzar con http:// o https://')
      return
    }
    if (lastPrice && isNaN(parseFloat(lastPrice))) {
      setError('El precio debe ser un número válido')
      return
    }

    setSaving(true)

    try {
      const payload: UpdateMarketSourceRequest = {}
      
      // Only send changed fields
      if (sourceName !== currentData.source_name) {
        payload.source_name = sourceName.trim()
      }
      if (url !== currentData.url) {
        payload.url = url.trim()
      }
      if (lastPrice !== currentData.last_price?.toString()) {
        payload.last_price = lastPrice ? parseFloat(lastPrice) : undefined
      }
      if (isMandatory !== currentData.is_mandatory) {
        payload.is_mandatory = isMandatory
      }

      await updateMarketSource(sourceId, payload)
      onSuccess()
      onClose()
    } catch (err: any) {
      console.error('Error al actualizar fuente:', err)
      setError(err.response?.data?.detail || 'Error al actualizar la fuente')
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    if (!saving) {
      onClose()
    }
  }

  if (!open) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) handleCancel()
      }}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 8,
          padding: 24,
          width: '90%',
          maxWidth: 500,
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
        }}
      >
        <h3 style={{ margin: '0 0 20px 0', fontSize: 18, fontWeight: 600 }}>
          Editar Fuente
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Source Name */}
          <div>
            <label
              htmlFor="edit-source-name"
              style={{ display: 'block', marginBottom: 6, fontWeight: 500, fontSize: 14 }}
            >
              Nombre de la Fuente *
            </label>
            <input
              id="edit-source-name"
              type="text"
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
              disabled={saving}
              placeholder="ej: Mercado Libre, Tienda XYZ"
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid #ddd',
                borderRadius: 4,
                fontSize: 14,
              }}
            />
          </div>

          {/* URL */}
          <div>
            <label
              htmlFor="edit-url"
              style={{ display: 'block', marginBottom: 6, fontWeight: 500, fontSize: 14 }}
            >
              URL *
            </label>
            <input
              id="edit-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={saving}
              placeholder="https://..."
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid #ddd',
                borderRadius: 4,
                fontSize: 14,
                fontFamily: 'monospace',
              }}
            />
          </div>

          {/* Last Price */}
          <div>
            <label
              htmlFor="edit-last-price"
              style={{ display: 'block', marginBottom: 6, fontWeight: 500, fontSize: 14 }}
            >
              Último Precio
            </label>
            <input
              id="edit-last-price"
              type="text"
              value={lastPrice}
              onChange={(e) => setLastPrice(e.target.value)}
              disabled={saving}
              placeholder="ej: 1234.56"
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid #ddd',
                borderRadius: 4,
                fontSize: 14,
              }}
            />
            <small style={{ color: '#666', fontSize: 12 }}>
              Opcional. Usar punto como separador decimal.
            </small>
          </div>

          {/* Is Mandatory */}
          <div>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: saving ? 'not-allowed' : 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={isMandatory}
                onChange={(e) => setIsMandatory(e.target.checked)}
                disabled={saving}
                style={{ cursor: saving ? 'not-allowed' : 'pointer' }}
              />
              <span style={{ fontWeight: isMandatory ? 600 : 400, fontSize: 14 }}>
                Fuente obligatoria
              </span>
            </label>
            <small style={{ color: '#666', fontSize: 12, marginLeft: 28, display: 'block' }}>
              Las fuentes obligatorias deben tener precio para validar el producto.
            </small>
          </div>

          {/* Error Message */}
          {error && (
            <div
              style={{
                padding: 12,
                background: '#fee',
                border: '1px solid #fcc',
                borderRadius: 4,
                color: '#c33',
                fontSize: 14,
              }}
            >
              {error}
            </div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 8 }}>
            <button
              onClick={handleCancel}
              disabled={saving}
              style={{
                padding: '8px 16px',
                border: '1px solid #ddd',
                borderRadius: 4,
                background: '#fff',
                cursor: saving ? 'not-allowed' : 'pointer',
                fontSize: 14,
                fontWeight: 500,
              }}
            >
              Cancelar
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                padding: '8px 16px',
                border: 'none',
                borderRadius: 4,
                background: saving ? '#ccc' : 'var(--primary, #007bff)',
                color: '#fff',
                cursor: saving ? 'not-allowed' : 'pointer',
                fontSize: 14,
                fontWeight: 500,
              }}
            >
              {saving ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
