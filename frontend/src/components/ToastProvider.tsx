// NG-HEADER: Nombre de archivo: ToastProvider.tsx
// NG-HEADER: Ubicación: frontend/src/components/ToastProvider.tsx
// NG-HEADER: Descripción: Proveedor de toasts globales
// NG-HEADER: Lineamientos: Ver AGENTS.md
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'

export interface Toast {
  id: string
  kind: 'success' | 'error' | 'info'
  title?: string
  message: string
  ttl?: number
}

interface ToastContextValue {
  push(t: Omit<Toast, 'id'>): void
  remove(id: string): void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])

  const remove = useCallback((id: string) => {
    setItems(prev => prev.filter(t => t.id !== id))
  }, [])

  const push = useCallback((t: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).slice(2)
    const ttl = t.ttl ?? 4000
    const toast: Toast = { id, ...t, ttl }
    setItems(prev => [...prev, toast])
    if (ttl > 0) {
      setTimeout(() => remove(id), ttl)
    }
  }, [remove])

  return (
    <ToastContext.Provider value={{ push, remove }}>
      {children}
      <div className="toast-container">
        {items.map(t => (
          <div key={t.id} className={`toast toast-${t.kind}`}> 
            <div className="toast-body">
              {t.title && <div className="toast-title">{t.title}</div>}
              <div className="toast-msg">{t.message}</div>
            </div>
            <button className="toast-close" onClick={() => remove(t.id)}>×</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast debe usarse dentro de <ToastProvider/>')
  return ctx
}

// Estilos básicos (podría moverse a CSS global)
export const toastStyles = `
.toast-container { position: fixed; top: 12px; right: 12px; display: flex; flex-direction: column; gap: 8px; z-index: 9999; }
.toast { backdrop-filter: blur(4px); background: rgba(30,30,30,0.9); border:1px solid #333; padding:10px 14px; border-radius:8px; color:#eee; min-width:220px; max-width:320px; display:flex; gap:12px; animation:toast-in .25s ease; box-shadow:0 4px 16px -4px rgba(0,0,0,0.5); }
.toast-success { border-color:#22c55e; }
.toast-error { border-color:#f43f5e; }
.toast-info { border-color:#7c4dff; }
.toast-title { font-weight:600; margin-bottom:2px; font-size:14px; }
.toast-msg { font-size:13px; line-height:1.3; }
.toast-close { background:none; border:none; color:#aaa; font-size:16px; cursor:pointer; padding:0 4px; }
.toast-close:hover { color:#fff; }
@keyframes toast-in { from { opacity:0; transform:translateY(-6px);} to { opacity:1; transform:translateY(0);} }
`

export function InjectToastStyles() {
  useEffect(() => {
    if (document.getElementById('toast-styles')) return
    const style = document.createElement('style')
    style.id = 'toast-styles'
    style.innerHTML = toastStyles
    document.head.appendChild(style)
  }, [])
  return null
}
