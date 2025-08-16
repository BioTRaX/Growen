import { useEffect, useRef, useState } from 'react'
import { createWS, WSMessage } from '../lib/ws'
import { chatHttp } from '../lib/http'
import UploadModal from './UploadModal'
import ImportViewer from './ImportViewer'

type Msg = { role: 'user' | 'assistant' | 'system'; text: string }

export default function ChatWindow() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [droppedFile, setDroppedFile] = useState<File | null>(null)
  const [importInfo, setImportInfo] = useState<
    | { jobId: number; summary: any; kpis: any }
    | null
  >(null)

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

  function handleUploaded(info: { jobId: number; summary: any; kpis: any }) {
    setImportInfo(info)
    setMessages((p) => [
      ...p,
      {
        role: 'system',
        text: `✅ Archivo recibido. Inicié dry-run (job ${info.jobId}). Abro visor.`,
      },
    ])
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    const f = e.dataTransfer.files?.[0]
    if (f) {
      setDroppedFile(f)
      setUploadOpen(true)
    }
  }

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      style={{ maxWidth: 800, margin: '40px auto', padding: 16 }}
    >
      <h1>Growen</h1>
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
              <strong>{label}:</strong> {m.text}
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
        <button
          onClick={() => {
            setDroppedFile(null)
            setUploadOpen(true)
          }}
        >
          +
        </button>
        <button onClick={send}>Enviar</button>
      </div>
      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={handleUploaded}
        initialFile={droppedFile}
      />
      {importInfo && (
        <ImportViewer
          open={true}
          jobId={importInfo.jobId}
          summary={importInfo.summary}
          kpis={importInfo.kpis}
          onClose={() => setImportInfo(null)}
        />
      )}
    </div>
  )
}
