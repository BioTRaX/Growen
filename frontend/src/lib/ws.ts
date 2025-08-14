export function connect(path: string): WebSocket {
  const ws = new WebSocket(path)
  ws.onclose = () => {
    console.log('conexión cerrada')
  }
  return ws
}
