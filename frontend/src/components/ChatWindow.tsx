// NG-HEADER: Nombre de archivo: ChatWindow.tsx
// NG-HEADER: Ubicación: frontend/src/components/ChatWindow.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useRef, useState, ReactNode } from 'react'
import { createWS, WSMessage } from '../lib/ws'
import { chatHttp } from '../lib/http'
import { formatARS } from '../lib/format'
import UploadModal from './UploadModal'
import ImportViewer from './ImportViewer'
import SuppliersModal from './SuppliersModal'
import ProductsDrawer from './ProductsDrawer'
import DragDropZone from './DragDropZone'
import { useAuth } from '../auth/AuthContext'

type Msg = { role: 'user' | 'assistant' | 'system'; text: string; type?: string; data?: any; stream?: string }

export default function ChatWindow() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [droppedFile, setDroppedFile] = useState<File | null>(null)
  const [importInfo, setImportInfo] = useState<
    | { jobId: number; summary: any }
    | null
  >(null)
  const [suppliersOpen, setSuppliersOpen] = useState(false)
  const [productsOpen, setProductsOpen] = useState(false)
  const { state } = useAuth()
  const canUpload = ['proveedor', 'colaborador', 'admin'].includes(state.role)

  useEffect(() => {
    try {
      const ws = createWS((m: WSMessage) => {
        setMessages((prev) => [...prev, m as Msg])
      })
      wsRef.current = ws
      ws.onopen = () => console.log('WS connected')
      ws.onerror = () => console.log('WS error')
      ws.onclose = () => console.log('WS closed')
      return () => ws.close()
    } catch (e) {
      console.warn('WS not available', e)
    }
  }, [])

  useEffect(() => {
    const openUpload = () => {
      if (!canUpload) {
        setMessages((p) => [
          ...p,
          { role: 'system', text: 'Acción no permitida para invitado.' },
        ])
        return
      }
      setDroppedFile(null)
      setUploadOpen(true)
    }
    const openSuppliers = () => setSuppliersOpen(true)
    const openProducts = () => setProductsOpen(true)
    window.addEventListener('open-upload', openUpload)
    window.addEventListener('open-suppliers', openSuppliers)
    window.addEventListener('open-products', openProducts)
    return () => {
      window.removeEventListener('open-upload', openUpload)
      window.removeEventListener('open-suppliers', openSuppliers)
      window.removeEventListener('open-products', openProducts)
    }
  }, [canUpload])

  // Si el rol cambia a invitado mientras el modal está abierto, ciérralo
  useEffect(() => {
    if (!canUpload && uploadOpen) setUploadOpen(false)
  }, [canUpload, uploadOpen])

  async function send() {
    const text = input.trim()
    if (!text) return
    setMessages((p) => [...p, { role: 'user', text }])
    setInput('')

    try {
      const ws = wsRef.current
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(text)
      } else {
        const r = await chatHttp(text)
        setMessages((p) => [...p, r as Msg])
      }
    } catch (err: any) {
      setMessages((p) => [
        ...p,
        { role: 'system', text: `Error: ${err.message}` },
      ])
    }
  }


  const formatCurrency = (currency: string, value: number): string => {
    if (currency === 'ARS') return formatARS(value)
    try {
      return new Intl.NumberFormat('es-AR', { style: 'currency', currency, minimumFractionDigits: 2 }).format(value)
    } catch {
      return `${currency} ${value.toFixed(2)}`
    }
  }

  const renderMessageContent = (m: Msg): ReactNode => {
    if (m.type === 'price_answer' && m.data) {
      const entries = Array.isArray(m.data.entries) ? m.data.entries : []
      return (
        <div data-testid="price-answer">
          <div>{m.text}</div>
          {entries.length > 0 && (
            <ul style={{ margin: '4px 0 0 16px' }}>
              {entries.slice(0, 5).map((entry: any, idx: number) => {
                const key = entry.canonical_id ?? entry.supplier_item_id ?? idx
                const amount = typeof entry.price === 'number' ? entry.price : null
                const price = amount != null
                  ? formatCurrency(entry.currency ?? 'ARS', amount)
                  : (typeof entry.formatted_price === 'string' ? entry.formatted_price : '')
                return (
                  <li key={key}>
                    <strong>{entry.name}</strong>
                    {price ? <span> — {price}</span> : null}
                    {entry.supplier_name ? <span> · {entry.supplier_name}</span> : null}
                    {entry.sku ? <span> (SKU {entry.sku})</span> : null}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )
    }
    return m.text
  }

  function handleUploaded(info: { jobId: number; summary: any }) {
    setImportInfo(info)
    setMessages((p) => [
      ...p,
      {
        role: 'system',
        text: `✅ Archivo recibido. Inicié dry-run (job ${info.jobId}). Abro visor.`,
      },
    ])
  }

  return (
    <div style={{ maxWidth: 800, margin: '40px auto', padding: 16 }}>
      <h1>Growen</h1>
      <p style={{ color: '#555', marginBottom: 16 }}><strong>Tip:</strong> podés chatear con Growen para consultar precios de productos, pedir diagnósticos rápidos o lanzar acciones con comandos.</p>
      {canUpload && (
        <DragDropZone
          onFileDropped={(f) => {
            if (!canUpload) {
              setMessages((p) => [
                ...p,
                { role: 'system', text: 'No tenés permisos para subir archivos.' },
              ])
              return
            }
            setDroppedFile(f)
            setUploadOpen(true)
          }}
        />
      )}
      <div
        style={{
          border: '1px solid #ddd',
          borderRadius: 8,
          padding: 12,
          minHeight: 300,
        }}
      >
        {messages.map((m, i) => {
          const label = m.role === 'assistant' ? 'Growen' : m.role === 'user' ? 'Tú' : m.role
          return (
            <div key={i} style={{ margin: '6px 0' }}>
              <strong>{label}:</strong>{' '}
              {renderMessageContent(m)}
            </div>
          )
        })}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <input
          style={{ flex: 1, padding: 8 }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Escribe un mensaje o /help"
          onKeyDown={(e) => e.key === 'Enter' && send()}
        />
        {canUpload && (
          <button
            onClick={() => {
              if (!canUpload) {
                setMessages((p) => [
                  ...p,
                  { role: 'system', text: 'No tenés permisos para subir archivos.' },
                ])
                return
              }
              setDroppedFile(null)
              setUploadOpen(true)
            }}
          >
            +
          </button>
        )}
        <button onClick={send}>Enviar</button>
      </div>
      <UploadModal
        open={canUpload && uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={handleUploaded}
        preselectedFile={droppedFile}
      />
      <SuppliersModal
        open={suppliersOpen}
        onClose={() => setSuppliersOpen(false)}
      />
      <ProductsDrawer
        open={productsOpen}
        onClose={() => setProductsOpen(false)}
      />
      {importInfo && (
        <ImportViewer
          open={true}
          jobId={importInfo.jobId}
          summary={importInfo.summary}
          onClose={() => setImportInfo(null)}
        />
      )}
    </div>
  )
}
