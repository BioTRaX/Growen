import { useEffect, useState } from 'react'

type Toast = { type: 'success' | 'error' | 'warning'; text: string }

let push: ((t: Toast | null) => void) | null = null

export function showToast(type: Toast['type'], text: string) {
  push?.({ type, text })
}

export default function ToastContainer() {
  const [toast, setToast] = useState<Toast | null>(null)
  useEffect(() => {
    push = setToast
  }, [])
  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(id)
  }, [toast])
  if (!toast) return null

  const colors = {
    success: '#4caf50',
    error: '#f44336',
    warning: '#ff9800',
  }

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 20,
        right: 20,
        background: colors[toast.type],
        color: '#fff',
        padding: '8px 12px',
        borderRadius: 4,
        zIndex: 100,
      }}
    >
      {toast.text}
    </div>
  )
}
