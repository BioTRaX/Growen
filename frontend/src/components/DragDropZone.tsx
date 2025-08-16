import { useState } from 'react'

type Props = { onFileDropped: (file: File) => void }

export default function DragDropZone({ onFileDropped }: Props) {
  const [over, setOver] = useState(false)
  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setOver(true)
  }
  const onDragLeave = () => setOver(false)
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setOver(false)
    const f = e.dataTransfer.files?.[0]
    if (!f) return
    const name = f.name.toLowerCase()
    if (!name.endsWith('.xlsx') && !name.endsWith('.csv')) return
    onFileDropped(f)
  }

  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={`panel p-4 mb-3 border-dashed ${over ? 'ring-2' : ''}`}
      role="region"
      aria-label="Zona para arrastrar y soltar archivos"
    >
      <strong>Arrastrá y soltá aquí tu lista de precios (.xlsx/.csv)</strong>
      <div className="text-sm" style={{ color: 'var(--muted)' }}>
        También podés usar “Adjuntar Excel”.
      </div>
    </div>
  )
}
