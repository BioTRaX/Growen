// NG-HEADER: Nombre de archivo: SupplierAutocomplete.tsx
// NG-HEADER: Ubicacion: frontend/src/components/supplier/SupplierAutocomplete.tsx
// NG-HEADER: Descripcion: Autocompletado de proveedores con estilos tema y carga inmediata
// NG-HEADER: Lineamientos: Ver AGENTS.md
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { searchSuppliers, SupplierSearchItem } from '../../services/suppliers'
import { useTheme } from '../../theme/ThemeProvider'

export type SupplierAutocompleteProps = {
  value?: SupplierSearchItem | null
  onChange: (item: SupplierSearchItem | null) => void
  placeholder?: string
  disabled?: boolean
  autoFocus?: boolean
  debounceMs?: number
  className?: string
}

export function SupplierAutocomplete({
  value,
  onChange,
  placeholder = 'Buscar proveedor...',
  disabled,
  autoFocus,
  debounceMs = 250,
  className,
}: SupplierAutocompleteProps) {
  const theme = useTheme()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const timerRef = useRef<number | null>(null)
  const lastQuery = useRef<string>('')

  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<SupplierSearchItem[]>([])
  const [highlight, setHighlight] = useState(0)

  const fetchSuppliers = useCallback(async (term: string) => {
    setLoading(true)
    try {
      const results = await searchSuppliers(term, 20)
      setItems(results)
      setHighlight(0)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!open || disabled) return undefined

    const trimmed = query.trim()
    if (timerRef.current) window.clearTimeout(timerRef.current)

    if (!trimmed) {
      if (lastQuery.current !== '' || items.length === 0) {
        lastQuery.current = ''
        fetchSuppliers('')
      }
      return undefined
    }

    timerRef.current = window.setTimeout(() => {
      if (lastQuery.current === trimmed) return
      lastQuery.current = trimmed
      fetchSuppliers(trimmed)
    }, debounceMs)

    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [open, query, debounceMs, disabled, fetchSuppliers, items.length])

  useEffect(() => {
    if (!open) return undefined
    const handleClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  useEffect(() => {
    if (autoFocus && inputRef.current) inputRef.current.focus()
  }, [autoFocus])

  useEffect(() => {
    if (!open) return
    setHighlight(0)
  }, [open])

  useEffect(() => {
    if (value) setQuery('')
  }, [value])

  const handleKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (event) => {
    if (!open) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlight((prev) => Math.min(prev + 1, Math.max(items.length - 1, 0)))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlight((prev) => Math.max(prev - 1, 0))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      const selected = items[highlight]
      if (selected) {
        onChange(selected)
        setOpen(false)
      }
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  const describe = (supplier: SupplierSearchItem) => `${supplier.name} (${supplier.slug})`

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ position: 'relative', width: '100%' }}
    >
      <input
        ref={inputRef}
        type='text'
        value={value ? describe(value) : query}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(event) => {
          setQuery(event.target.value)
          setOpen(true)
          onChange(null)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onKeyDown={handleKeyDown}
        aria-autocomplete='list'
        aria-expanded={open}
        aria-controls='supplier-ac-list'
        className='input w-full'
        style={{
          background: 'var(--input-bg)',
          color: 'var(--text)',
          border: '1px solid var(--input-border)',
        }}
      />
      {open && (
        <div
          id='supplier-ac-list'
          role='listbox'
          style={{
            position: 'absolute',
            zIndex: 24,
            width: '100%',
            background: 'var(--panel-bg)',
            border: '1px solid var(--border)',
            maxHeight: 240,
            overflowY: 'auto',
            borderRadius: 10,
            marginTop: 4,
            boxShadow: '0 16px 32px rgba(0,0,0,0.35)',
          }}
        >
          {loading && (
            <div style={{ padding: 10, color: 'var(--muted)' }}>Cargando proveedores...</div>
          )}
          {!loading && items.length === 0 && (
            <div style={{ padding: 10, color: 'var(--muted)' }}>
              {query.trim() ? 'Sin resultados para tu busqueda.' : 'No hay proveedores disponibles todavia.'}
            </div>
          )}
          {!loading && items.map((item, idx) => {
            const active = idx === highlight
            return (
              <div
                key={item.id}
                role='option'
                aria-selected={active}
                onMouseEnter={() => setHighlight(idx)}
                onMouseDown={(event) => {
                  event.preventDefault()
                  onChange(item)
                  setOpen(false)
                }}
                style={{
                  padding: '10px 12px',
                  cursor: 'pointer',
                  background: active ? 'var(--table-row-hover)' : 'var(--panel-bg)',
                }}
              >
                <div style={{ fontWeight: 600, color: theme.text }}>{item.name}</div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>{item.slug}</div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default SupplierAutocomplete
