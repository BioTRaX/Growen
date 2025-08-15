export type WSMessage = { role: string; text: string }

export function createWS(onMessage: (m: WSMessage) => void) {
  const url = (import.meta.env.VITE_WS_URL as string) || '/ws'
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}${url}`)
  ws.onmessage = (e) => onMessage(JSON.parse(e.data))
  return ws
}
