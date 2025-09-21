// NG-HEADER: Nombre de archivo: SupplierAutocomplete.tsx
// NG-HEADER: Ubicación: frontend/src/components/supplier/SupplierAutocomplete.tsx
// NG-HEADER: Descripción: Componente de autocompletado de proveedor con debounce y estados
// NG-HEADER: Lineamientos: Ver AGENTS.md
import React, { useEffect, useMemo, useRef, useState } from 'react'
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

export function SupplierAutocomplete({ value, onChange, placeholder = 'Buscar proveedor...', disabled, autoFocus, debounceMs = 250, className }: SupplierAutocompleteProps) {
  const theme = useTheme()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<SupplierSearchItem[]>([])
  const [highlight, setHighlight] = useState(0)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const timer = useRef<number | null>(null)

  useEffect(() => {
    if (!open) return
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(async () => {
      if (!q.trim()) { setItems([]); setLoading(false); return }
      setLoading(true)
      try {
        const results = await searchSuppliers(q, 20)
        setItems(results)
      } catch {
        setItems([])
      } finally {
        setLoading(false)
      }
    }, debounceMs)
    return () => { if (timer.current) window.clearTimeout(timer.current) }
  }, [q, open, debounceMs])

  useEffect(() => {
    if (autoFocus && inputRef.current) inputRef.current.focus()
  }, [autoFocus])

  const onKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (e) => {
    if (!open) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight(h => Math.min(h + 1, items.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight(h => Math.max(h - 1, 0)) }
    else if (e.key === 'Enter') {
      e.preventDefault()
      const sel = items[highlight]
      if (sel) { onChange(sel); setOpen(false) }
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className={className} style={{ position: 'relative' }}>
      <input
        ref={inputRef}
        type="text"
        value={value ? `${value.name} (${value.slug})` : q}
        placeholder={placeholder}
        disabled={disabled}
        onChange={e => { setQ(e.target.value); setOpen(true); onChange(null) }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls="supplier-ac-list"
        style={{
          width: '100%',
          background: theme.name === 'dark' ? '#111' : '#fff',
          color: theme.text,
          border: `1px solid ${theme.border}`,
          borderRadius: 6,
          padding: '6px 8px',
        }}
      />
      {open && (
        <div id="supplier-ac-list" role="listbox" style={{ position: 'absolute', zIndex: 20, width: '100%', background: theme.card, border: `1px solid ${theme.border}`, maxHeight: 240, overflowY: 'auto', borderRadius: 6, marginTop: 4 }}>
          {loading && <div style={{ padding: 8, color: theme.name === 'dark' ? '#bbb' : '#666' }}>Cargando…</div>}
          {!loading && items.length === 0 && q.trim() && (
            <div style={{ padding: 8, color: theme.name === 'dark' ? '#bbb' : '#666' }}>Sin resultados</div>
          )}
          {!loading && items.map((it, idx) => (
            <div
              key={it.id}
              role="option"
              aria-selected={idx === highlight}
              onMouseEnter={() => setHighlight(idx)}
              onMouseDown={(e) => { e.preventDefault(); onChange(it); setOpen(false) }}
              style={{ padding: 8, background: idx === highlight ? (theme.name === 'dark' ? '#2a2a2a' : '#f0f0f0') : theme.card, cursor: 'pointer', color: theme.text }}
            >
              <div style={{ fontWeight: 600 }}>{it.name}</div>
              <div style={{ fontSize: 12, color: theme.name === 'dark' ? '#aaa' : '#888' }}>{it.slug}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default SupplierAutocomplete
