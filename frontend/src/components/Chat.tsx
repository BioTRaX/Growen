import { useEffect, useState } from 'react'
import { connect } from '../lib/ws'

export default function Chat() {
  const [socket, setSocket] = useState<WebSocket | null>(null)
  const [messages, setMessages] = useState<string[]>([])
  const [input, setInput] = useState('')

  useEffect(() => {
    const ws = connect('/ws/chat')
    ws.onmessage = (ev) => setMessages((m) => [...m, ev.data])
    setSocket(ws)
    return () => ws.close()
  }, [])

  const send = () => {
    socket?.send(input)
    setInput('')
  }

  return (
    <div style={{ flex: 1, padding: '1rem' }}>
      <div style={{ minHeight: '300px' }}>
        {messages.map((m, i) => (
          <div key={i}>{m}</div>
        ))}
      </div>
      <input value={input} onChange={(e) => setInput(e.target.value)} />
      <button onClick={send}>Enviar</button>
    </div>
  )
}
