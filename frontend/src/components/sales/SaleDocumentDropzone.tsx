// NG-HEADER: Nombre de archivo: SaleDocumentDropzone.tsx
// NG-HEADER: Ubicación: frontend/src/components/sales/SaleDocumentDropzone.tsx
// NG-HEADER: Descripción: Dropzone para adjuntar documentos a ventas
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState, useRef } from 'react'

type FilePreview = {
  file: File
  id: string
}

type Props = {
  files: FilePreview[]
  onFilesChange: (files: FilePreview[]) => void
  maxFiles?: number
}

export default function SaleDocumentDropzone({ files, onFilesChange, maxFiles = 5 }: Props) {
  const [isDragOver, setIsDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function generateId() {
    return Math.random().toString(36).substring(2, 9)
  }

  function handleFiles(fileList: FileList | null) {
    if (!fileList) return
    const newFiles: FilePreview[] = []
    for (let i = 0; i < fileList.length && files.length + newFiles.length < maxFiles; i++) {
      const file = fileList[i]
      // Validar tipos de archivo permitidos
      const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'image/gif']
      if (allowedTypes.includes(file.type) || file.name.endsWith('.pdf')) {
        newFiles.push({ file, id: generateId() })
      }
    }
    if (newFiles.length > 0) {
      onFilesChange([...files, ...newFiles])
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragOver(false)
    handleFiles(e.dataTransfer.files)
  }

  function onDragOver(e: React.DragEvent) {
    e.preventDefault()
    setIsDragOver(true)
  }

  function onDragLeave() {
    setIsDragOver(false)
  }

  function removeFile(id: string) {
    onFilesChange(files.filter(f => f.id !== id))
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
  }

  return (
    <div style={{ marginTop: 16 }}>
      <label style={{ fontWeight: 600, marginBottom: 8, display: 'block' }}>
        Documentos Adjuntos
      </label>

      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${isDragOver ? 'var(--primary)' : 'var(--input-border)'}`,
          borderRadius: 8,
          padding: 24,
          textAlign: 'center',
          cursor: 'pointer',
          background: isDragOver ? 'rgba(124, 77, 255, 0.1)' : 'var(--input-bg)',
          transition: 'all 0.2s ease',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png,.webp,.gif"
          onChange={(e) => handleFiles(e.target.files)}
          style={{ display: 'none' }}
        />
        <div style={{ color: 'var(--muted)', marginBottom: 8 }}>
          <span style={{ fontSize: 32 }}>📎</span>
        </div>
        <div style={{ fontWeight: 500 }}>
          Arrastrá archivos aquí o hacé clic para seleccionar
        </div>
        <div style={{ fontSize: '0.85rem', color: 'var(--muted)', marginTop: 4 }}>
          PDF, JPG, PNG (máx. {maxFiles} archivos)
        </div>
      </div>

      {files.length > 0 && (
        <div style={{ marginTop: 12 }}>
          {files.map((fp) => (
            <div
              key={fp.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '8px 12px',
                background: 'var(--input-bg)',
                border: '1px solid var(--input-border)',
                borderRadius: 6,
                marginBottom: 6,
              }}
            >
              <span style={{ fontSize: 20 }}>
                {fp.file.type.includes('pdf') ? '📄' : '🖼️'}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ 
                  fontWeight: 500, 
                  overflow: 'hidden', 
                  textOverflow: 'ellipsis', 
                  whiteSpace: 'nowrap' 
                }}>
                  {fp.file.name}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                  {formatFileSize(fp.file.size)}
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  removeFile(fp.id)
                }}
                className="btn btn-danger"
                style={{ padding: '4px 8px', fontSize: '0.85rem' }}
                title="Eliminar"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

