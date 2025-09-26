// NG-HEADER: Nombre de archivo: Toast.tsx
// NG-HEADER: Ubicación: frontend/src/components/Toast.tsx
// NG-HEADER: Descripción: Contenedor de notificaciones tipo toast.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'

type Toast = { id: number; type: 'success' | 'error' | 'warning' | 'info'; text: string }

let push: ((t: Omit<Toast, 'id'>) => void) | null = null
let counter = 0

export function showToast(type: Toast['type'], text: string) {
  push?.({ type, text })
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([])
  useEffect(() => {
    push = ({ type, text }) => {
      setToasts((prev) => [...prev, { id: ++counter, type, text }])
    }
  }, [])
  useEffect(() => {
    if (toasts.length === 0) return
    const timers = toasts.map(t => setTimeout(() => {
      setToasts(prev => prev.filter(p => p.id !== t.id))
    }, 4000))
    return () => timers.forEach(clearTimeout)
  }, [toasts])
  if (!toasts.length) return null

  const styles: Record<Toast['type'], { bg: string; border: string }> = {
    success: { bg: '#1b5e20', border: '#43a047' },
    error: { bg: '#7f1d1d', border: '#ef5350' },
    warning: { bg: '#4e342e', border: '#ffb74d' },
    info: { bg: '#1e3a5f', border: '#64b5f6' },
  }

  return (
    <div style={{ position: 'fixed', bottom: 16, right: 16, display: 'flex', flexDirection: 'column', gap: 8, zIndex: 120 }}>
      {toasts.map(t => (
        <div
          key={t.id}
          style={{
            background: styles[t.type].bg,
            color: '#f1f5f9',
            border: `1px solid ${styles[t.type].border}`,
            padding: '10px 14px',
            borderRadius: 6,
            fontSize: 14,
            minWidth: 240,
            maxWidth: 420,
            boxShadow: '0 4px 18px -4px rgba(0,0,0,0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            animation: 'toast-fade-in 160ms ease-out'
          }}
        >
          <span style={{ lineHeight: 1.3 }}>{t.text}</span>
          <button
            onClick={() => setToasts(prev => prev.filter(p => p.id !== t.id))}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#e2e8f0',
              cursor: 'pointer',
              fontSize: 16,
              lineHeight: 1,
              padding: 0,
            }}
            title="Cerrar"
          >×</button>
        </div>
      ))}
      <style>{`@keyframes toast-fade-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0);} }`}</style>
    </div>
  )
}
