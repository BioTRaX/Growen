// NG-HEADER: Nombre de archivo: ChatWindow.tsx
// NG-HEADER: Ubicacion: frontend/src/components/ChatWindow.tsx
// NG-HEADER: Descripcion: Ventana de chat asistido dentro de la SPA.
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

interface ProductEntryPayload {
  name: string
  price?: number | null
  currency: string
  formatted_price?: string | null
  stock_qty?: number | null
  stock_status?: string | null
  sku?: string | null
  supplier_name?: string | null
  source_detail?: string | null
  variant_skus?: string[]
  match_reason?: string | null
}

interface ProductPayload {
  status: string
  query: string
  intent: string
  normalized_query: string
  terms: string[]
  sku_candidates: string[]
  results: ProductEntryPayload[]
  missing: string[]
  took_ms?: number | null
  errors?: string[]
}

type Msg = {
  role: 'user' | 'assistant' | 'system'
  text: string
  type?: string
  data?: ProductPayload | null
  stream?: string
}

const STOCK_BADGE: Record<string, { label: string; bg: string; color: string }> = {
  ok: { label: 'En stock', bg: 'rgba(76, 175, 80, 0.16)', color: '#43a047' },
  low: { label: 'Pocas unidades', bg: 'rgba(255, 193, 7, 0.18)', color: '#f9a825' },
  out: { label: 'Sin stock', bg: 'rgba(244, 67, 54, 0.16)', color: '#e53935' },
}

const CONFIRM_PLACEHOLDER = '/stock '

export default function ChatWindow() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [droppedFile, setDroppedFile] = useState<File | null>(null)
  const [importInfo, setImportInfo] = useState<{ jobId: number; summary: any } | null>(null)
  const [suppliersOpen, setSuppliersOpen] = useState(false)
  const [productsOpen, setProductsOpen] = useState(false)
  const [expandedResults, setExpandedResults] = useState<Record<number, boolean>>({})
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
    } catch (err) {
      console.warn('WS not available', err)
    }
  }, [])

  useEffect(() => {
    const openUpload = () => {
      if (!canUpload) {
        setMessages((prev) => [...prev, { role: 'system', text: 'Accion no permitida para invitado.' }])
        return
      }
      setDroppedFile(null)
      setUploadOpen(true)
    }
    const openSuppliers = () => setSuppliersOpen(true)
    const openProductsList = () => setProductsOpen(true)

    window.addEventListener('open-upload', openUpload)
    window.addEventListener('open-suppliers', openSuppliers)
    window.addEventListener('open-products', openProductsList)
    return () => {
      window.removeEventListener('open-upload', openUpload)
      window.removeEventListener('open-suppliers', openSuppliers)
      window.removeEventListener('open-products', openProductsList)
    }
  }, [canUpload])

  useEffect(() => {
    if (!canUpload && uploadOpen) setUploadOpen(false)
  }, [canUpload, uploadOpen])

  const send = async () => {
    const text = input.trim()
    if (!text) return
    setMessages((prev) => [...prev, { role: 'user', text }])
    setInput('')

    try {
      const ws = wsRef.current
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(text)
      } else {
        const response = await chatHttp(text)
        setMessages((prev) => [...prev, response as Msg])
      }
    } catch (error: any) {
      setMessages((prev) => [...prev, { role: 'system', text: `Error: ${error.message}` }])
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

  const renderStockBadge = (entry: ProductEntryPayload) => {
    const status = entry.stock_status ?? ''
    const config = STOCK_BADGE[status]
    if (!config) return null
    const qty = typeof entry.stock_qty === 'number' ? entry.stock_qty : undefined
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          background: config.bg,
          color: config.color,
          fontSize: 12,
          borderRadius: 999,
          padding: '2px 10px',
        }}
      >
        <span>{config.label}</span>
        {typeof qty === 'number' ? <strong style={{ fontSize: 13 }}>{qty}</strong> : null}
      </span>
    )
  }

  const renderProductCard = (entry: ProductEntryPayload, index: number) => {
    return (
      <div
        key={`${entry.sku ?? entry.name}-${index}`}
        style={{
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 10,
          padding: 12,
          background: 'rgba(15, 23, 42, 0.35)',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <div style={{ fontWeight: 600 }}>{entry.name}</div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {typeof entry.price === 'number' ? (
            <span style={{ fontSize: 14, fontWeight: 600 }}>{entry.formatted_price ?? formatCurrency(entry.currency, entry.price)}</span>
          ) : (
            <span style={{ fontSize: 14, fontWeight: 500, color: '#ffb74d' }}>Sin precio cargado</span>
          )}
          {renderStockBadge(entry)}
        </div>
        <div style={{ fontSize: 12, color: '#b0bec5', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {entry.sku ? <span>SKU: {entry.sku}</span> : null}
          {entry.supplier_name ? <span>Proveedor: {entry.supplier_name}</span> : null}
          {entry.source_detail ? <span>Fuente: {entry.source_detail}</span> : null}
        </div>
        {entry.variant_skus && entry.variant_skus.length > 0 ? (
          <div style={{ fontSize: 12, color: '#90a4ae' }}>Variantes: {entry.variant_skus.join(', ')}</div>
        ) : null}
        {entry.match_reason ? (
          <div style={{ fontSize: 11, color: '#78909c' }}>Coincidencia: {entry.match_reason}</div>
        ) : null}
      </div>
    )
  }

  const renderSuggestions = (payload: ProductPayload) => {
    if (!Array.isArray(payload.sku_candidates) && !Array.isArray(payload.missing)) return null
    const suggestions: string[] = []
    if (payload.sku_candidates && payload.sku_candidates.length > 0) {
      suggestions.push(`Probar con SKU ${payload.sku_candidates[0]}`)
    }
    if (payload.missing && payload.missing.length > 0) {
      suggestions.push(`Sin precio: ${payload.missing.slice(0, 2).join(', ')}`)
    }
    if (suggestions.length === 0) return null
    return (
      <div style={{ marginTop: 10, fontSize: 12, color: '#90a4ae' }}>
        {suggestions.join('  ')}
      </div>
    )
  }

  const renderProductAnswer = (payload: ProductPayload, messageIndex: number, assistantText: string) => {
    const results = Array.isArray(payload.results) ? payload.results : []
    const showAll = expandedResults[messageIndex] ?? false
    const visible = showAll ? results : results.slice(0, 3)

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: 14 }}>{assistantText}</div>
        {payload.took_ms ? (
          <div style={{ fontSize: 11, color: '#90a4ae' }}>Tiempo de respuesta: {payload.took_ms} ms</div>
        ) : null}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {visible.map(renderProductCard)}
        </div>
        {results.length > 3 && !showAll ? (
          <button
            type="button"
            onClick={() => setExpandedResults((prev) => ({ ...prev, [messageIndex]: true }))}
            style={{
              alignSelf: 'flex-start',
              border: '1px solid #4f5b62',
              background: 'transparent',
              color: '#e0e6ed',
              padding: '6px 12px',
              borderRadius: 8,
              cursor: 'pointer',
            }}
          >
            Ver mas opciones
          </button>
        ) : null}
        {payload.status === 'no_match' ? (
          <div style={{ fontSize: 13, color: '#b0bec5' }}>
            No encontre coincidencias directas. Proba buscar por SKU o abri el catalogo de productos.
          </div>
        ) : null}
        {renderSuggestions(payload)}
      </div>
    )
  }

  const renderClarifyPrompt = (text: string) => (
    <div
      style={{
        background: 'rgba(255, 193, 7, 0.12)',
        border: '1px solid rgba(255, 193, 7, 0.35)',
        borderRadius: 10,
        padding: 10,
        fontSize: 13,
        color: '#ffca28',
      }}
    >
      {text}
    </div>
  )

  const renderMessageContent = (m: Msg, index: number): ReactNode => {
    if ((m.type === 'product_answer' || m.type === 'price_answer') && m.data) {
      return renderProductAnswer(m.data, index, m.text)
    }
    if (m.type === 'clarify_prompt') {
      return renderClarifyPrompt(m.text)
    }
    return m.text
  }

  const handleUploaded = (info: { jobId: number; summary: any }) => {
    setImportInfo(info)
    setMessages((prev) => [
      ...prev,
      {
        role: 'system',
        text: `Listo. Archivo recibido. Inicio dry-run (job ${info.jobId}). Abro visor.`,
      },
    ])
  }

  return (
    <div style={{ maxWidth: 820, margin: '40px auto', padding: 16 }}>
      <h1>Growen</h1>
      <p style={{ color: '#555', marginBottom: 16 }}>
        <strong>Tip:</strong> podes chatear con Growen para consultar precios y stock, pedir diagnosticos rapidos o lanzar comandos.
      </p>
      {canUpload && (
        <DragDropZone
          onFileDropped={(file) => {
            if (!canUpload) {
              setMessages((prev) => [...prev, { role: 'system', text: 'No tenes permisos para subir archivos.' }])
              return
            }
            setDroppedFile(file)
            setUploadOpen(true)
          }}
        />
      )}
      <div
        style={{
          border: '1px solid #1f2937',
          borderRadius: 10,
          padding: 16,
          minHeight: 320,
          background: 'rgba(15,23,42,0.55)',
          color: '#e0e6ed',
        }}
      >
        {messages.map((m, idx) => {
          const label = m.role === 'assistant' ? 'Growen' : m.role === 'user' ? 'Vos' : 'Sistema'
          return (
            <div key={`${label}-${idx}`} style={{ margin: '10px 0' }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}:</div>
              {renderMessageContent(m, idx)}
            </div>
          )
        })}
      </div>
      <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
        <input
          style={{ flex: 1, padding: 10, borderRadius: 8, border: '1px solid #374151', background: '#0f172a', color: '#e0e6ed' }}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Escribe un mensaje o /help"
          onKeyDown={(event) => event.key === 'Enter' && send()}
        />
        {canUpload && (
          <button
            onClick={() => {
              if (!canUpload) {
                setMessages((prev) => [...prev, { role: 'system', text: 'No tenes permisos para subir archivos.' }])
                return
              }
              setDroppedFile(null)
              setUploadOpen(true)
            }}
            style={{ width: 42, borderRadius: 8, border: '1px solid #374151', background: '#1f2937', color: '#e0e6ed' }}
          >
            +
          </button>
        )}
        <button
          onClick={send}
          style={{
            padding: '10px 18px',
            borderRadius: 8,
            border: 'none',
            background: '#2563eb',
            color: '#fff',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Enviar
        </button>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <button
          type="button"
          style={{ background: 'transparent', border: '1px solid #4f5b62', color: '#e0e6ed', padding: '4px 10px', borderRadius: 6, cursor: 'pointer' }}
          onClick={() => setInput((prev) => (prev && prev.trim().length > 0 ? prev : CONFIRM_PLACEHOLDER))}
        >
          Buscar por SKU
        </button>
        <button
          type="button"
          style={{ background: 'transparent', border: '1px solid #4f5b62', color: '#e0e6ed', padding: '4px 10px', borderRadius: 6, cursor: 'pointer' }}
          onClick={() => window.dispatchEvent(new Event('open-products'))}
        >
          Abrir Productos
        </button>
      </div>
      <UploadModal open={canUpload && uploadOpen} onClose={() => setUploadOpen(false)} onUploaded={handleUploaded} preselectedFile={droppedFile} />
      <SuppliersModal open={suppliersOpen} onClose={() => setSuppliersOpen(false)} />
      <ProductsDrawer open={productsOpen} onClose={() => setProductsOpen(false)} />
      {importInfo && (
        <ImportViewer open={true} jobId={importInfo.jobId} summary={importInfo.summary} onClose={() => setImportInfo(null)} />
      )}
    </div>
  )
}
