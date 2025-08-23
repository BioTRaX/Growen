export type WSMessage = { role: string; text: string }

export function createWS(onMessage: (m: WSMessage) => void) {
  const url = (import.meta.env.VITE_WS_URL as string) || '/ws'
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'

  let ws: WebSocket | null = null
  let retries = 0
  let closed = false
  let retryTimer: number | null = null

  const controller: {
    send: (d: string) => void
    close: () => void
    readonly readyState: number
    onopen: ((ev: Event) => any) | null
    onerror: ((ev: Event) => any) | null
    onclose: ((ev: CloseEvent) => any) | null
  } = {
    send: (d: string) => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(d)
    },
    close: () => {
      closed = true
      if (retryTimer) clearTimeout(retryTimer)
      ws?.close(1000, 'client closed')
    },
    get readyState() {
      return ws ? ws.readyState : WebSocket.CLOSED
    },
    onopen: null,
    onerror: null,
    onclose: null,
  }

  const connect = () => {
    ws = new WebSocket(`${proto}://${location.host}${url}`)
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.role !== 'ping') onMessage(msg)
      } catch {
        console.warn('Mensaje WS inválido', e.data)
      }
    }
    ws.onopen = (ev) => {
      retries = 0
      controller.onopen?.(ev)
    }
    ws.onerror = (ev) => controller.onerror?.(ev)
    ws.onclose = (ev) => {
      controller.onclose?.(ev)
      if (!closed) {
        const delay = Math.min(1000 * 2 ** retries, 10000)
        retries++
        retryTimer = window.setTimeout(connect, delay)
      }
    }
  }

  connect()
  return controller as unknown as WebSocket
}
