// NG-HEADER: Nombre de archivo: EditablePriceField.tsx
// NG-HEADER: Ubicación: frontend/src/components/EditablePriceField.tsx
// NG-HEADER: Descripción: Campo editable para precios con validación
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useState, useRef, useEffect } from 'react'
import { validatePrice } from '../services/market'

interface EditablePriceFieldProps {
  label: string
  value: number | null
  onSave: (newValue: number) => Promise<void>
  disabled?: boolean
  placeholder?: string
  formatPrefix?: string
}

export default function EditablePriceField({
  label,
  value,
  onSave,
  disabled = false,
  placeholder = '-',
  formatPrefix = '$',
}: EditablePriceFieldProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // Formatear valor para mostrar
  function formatValue(val: number | null): string {
    if (val == null) return placeholder
    return `${formatPrefix} ${val.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  // Al entrar en modo edición
  function handleStartEdit() {
    if (disabled || saving) return
    setIsEditing(true)
    setInputValue(value?.toString() || '')
    setError(null)
  }

  // Al cancelar edición
  function handleCancel() {
    setIsEditing(false)
    setInputValue('')
    setError(null)
  }

  // Al confirmar cambio
  async function handleSave() {
    const validation = validatePrice(inputValue)
    
    if (!validation.valid) {
      setError(validation.error || 'Valor inválido')
      return
    }

    const numValue = parseFloat(inputValue)
    
    // No guardar si el valor no cambió
    if (value !== null && Math.abs(numValue - value) < 0.01) {
      handleCancel()
      return
    }

    setSaving(true)
    setError(null)

    try {
      await onSave(numValue)
      setIsEditing(false)
      setInputValue('')
    } catch (err: any) {
      setError(err?.message || 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  // Focus automático al entrar en edición
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isEditing])

  // Manejo de teclas
  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSave()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      handleCancel()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>
        {label}
      </label>
      
      {!isEditing ? (
        // Modo lectura
        <div 
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 8,
            padding: '6px 8px',
            borderRadius: 4,
            border: '1px solid transparent',
            cursor: disabled ? 'not-allowed' : 'pointer',
            backgroundColor: disabled ? 'transparent' : 'var(--panel-bg)',
            opacity: disabled ? 0.6 : 1,
          }}
          onClick={handleStartEdit}
          title={disabled ? 'No editable' : 'Clic para editar'}
        >
          <span style={{ 
            fontSize: 16, 
            fontWeight: 600,
            color: value == null ? 'var(--text-secondary)' : 'var(--text-primary)',
          }}>
            {formatValue(value)}
          </span>
          {!disabled && (
            <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>✏️</span>
          )}
        </div>
      ) : (
        // Modo edición
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <input
              ref={inputRef}
              type="number"
              step="0.01"
              min="0"
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value)
                setError(null)
              }}
              onKeyDown={handleKeyDown}
              disabled={saving}
              placeholder="0.00"
              style={{
                flex: 1,
                padding: '6px 8px',
                fontSize: 14,
                border: error ? '1px solid var(--error-color, #e53935)' : '1px solid var(--border-color)',
                borderRadius: 4,
                backgroundColor: 'var(--input-bg)',
                color: 'var(--text-primary)',
              }}
            />
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                padding: '6px 12px',
                fontSize: 14,
                backgroundColor: 'var(--primary)',
                color: 'white',
                border: 'none',
                borderRadius: 4,
                cursor: saving ? 'wait' : 'pointer',
                opacity: saving ? 0.6 : 1,
              }}
              title="Guardar (Enter)"
            >
              {saving ? '⏳' : '✓'}
            </button>
            <button
              onClick={handleCancel}
              disabled={saving}
              style={{
                padding: '6px 12px',
                fontSize: 14,
                backgroundColor: 'var(--panel-bg)',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-color)',
                borderRadius: 4,
                cursor: saving ? 'not-allowed' : 'pointer',
                opacity: saving ? 0.6 : 1,
              }}
              title="Cancelar (Esc)"
            >
              ✕
            </button>
          </div>
          
          {error && (
            <span style={{ 
              fontSize: 12, 
              color: 'var(--error-color, #e53935)',
              fontWeight: 500,
            }}>
              {error}
            </span>
          )}
          
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
            Enter para guardar, Esc para cancelar
          </span>
        </div>
      )}
    </div>
  )
}
