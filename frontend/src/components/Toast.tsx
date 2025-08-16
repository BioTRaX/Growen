import { useEffect, useState } from 'react'

type Toast = { type: 'success' | 'error'; text: string }

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
  return (
    <div
      style={{
        position: 'fixed',
        bottom: 20,
        right: 20,
        background: toast.type === 'success' ? '#4caf50' : '#f44336',
        color: '#fff',
        padding: '8px 12px',
        borderRadius: 4,
      }}
    >
      {toast.text}
    </div>
  )
}
