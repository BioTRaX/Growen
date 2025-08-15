import { useEffect, useRef, useState } from 'react'
import { createWS } from '../lib/ws'
import { chatHttp } from '../lib/http'

type Msg = { role: 'user' | 'assistant' | 'system'; text: string }

export default function ChatWindow() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    try {
      const ws = createWS((m) => {
        setMessages((prev) => [...prev, { role: 'assistant', text: m }])
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
        const reply = r.reply || r.message || JSON.stringify(r)
        setMessages((p) => [...p, { role: 'assistant', text: reply }])
      }
    } catch (err: any) {
      setMessages((p) => [
        ...p,
        { role: 'system', text: `Error: ${err.message}` },
      ])
    }
  }

  return (
    <div style={{ maxWidth: 800, margin: '40px auto', padding: 16 }}>
      <h1>Growen</h1>
      <div
        style={{
          border: '1px solid #ddd',
          borderRadius: 8,
          padding: 12,
          minHeight: 300,
        }}
      >
        {messages.map((m, i) => (
          <div key={i} style={{ margin: '6px 0' }}>
            <strong>{m.role}:</strong> {m.text}
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <input
          style={{ flex: 1, padding: 8 }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Escribe un mensaje o /help"
          onKeyDown={(e) => e.key === 'Enter' && send()}
        />
        <button onClick={send}>Enviar</button>
      </div>
    </div>
  )
}
