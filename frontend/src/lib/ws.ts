export function createWS(onMessage: (m: string) => void) {
  const url = (import.meta.env.VITE_WS_URL as string) || '/ws'
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}${url}`)
  ws.onmessage = (e) => onMessage(e.data)
  return ws
}
