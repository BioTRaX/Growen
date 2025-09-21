// NG-HEADER: Nombre de archivo: BugReportButton.tsx
// NG-HEADER: Ubicación: frontend/src/components/BugReportButton.tsx
// NG-HEADER: Descripción: Botón flotante global para enviar reportes de errores al backend
// NG-HEADER: Lineamientos: Ver AGENTS.md
import React, { useEffect, useState } from 'react'
import { sendBugReport } from '../services/bugReport'
import { useToast } from './ToastProvider'
import { useTheme } from '../theme/ThemeProvider'

const styles = `
.bugreport-fab { position: fixed; right: 18px; bottom: 18px; z-index: 9998; }
.bugreport-fab button { border:none; border-radius: 999px; box-shadow:0 10px 24px rgba(0,0,0,.25); cursor:pointer; padding: 10px 14px; display:flex; gap:8px; align-items:center; font-weight:600 }
.bugreport-fab button:hover { filter: brightness(0.95); }
.bugreport-modal-backdrop { position:fixed; inset:0; background:rgba(0,0,0,.45); z-index:9999; display:flex; align-items:flex-end; justify-content:flex-end; }
.bugreport-modal { width: min(560px, 98vw); margin: 12px; border-radius: 12px; overflow:hidden; box-shadow:0 14px 40px rgba(0,0,0,.35); }
.bugreport-header { display:flex; align-items:center; justify-content:space-between; padding:12px 14px; font-weight:600 }
.bugreport-body { padding: 12px; }
.bugreport-body textarea { width:100%; min-height: 120px; resize: vertical; font-family: ui-sans-serif, system-ui, sans-serif; padding:8px; border-radius:8px }
.bugreport-actions { display:flex; gap:8px; justify-content:flex-end; padding: 12px }
`;

function InjectBRStyles() {
  useEffect(() => {
    if (document.getElementById('bugreport-styles')) return
    const s = document.createElement('style')
    s.id = 'bugreport-styles'
    s.innerHTML = styles
    document.head.appendChild(s)
  }, [])
  return null
}

export default function BugReportButton() {
  const theme = useTheme()
  const [open, setOpen] = useState(false)
  const [msg, setMsg] = useState('')
  const [sending, setSending] = useState(false)
  const toast = useToast()

  const onSend = async () => {
    if (!msg.trim()) {
      toast.push({ kind: 'error', message: 'Escribí un breve detalle del problema', title: 'Reporte vacío' })
      return
    }
    setSending(true)
    try {
  const ua = typeof navigator !== 'undefined' ? navigator.userAgent : undefined
  const url = typeof window !== 'undefined' ? window.location.href : undefined
  // Calcular hora local GMT-3 desde el cliente
  const now = new Date()
  const gmt3Ms = now.getTime() - (3 * 60 * 60 * 1000)
  const ts_gmt3 = new Date(gmt3Ms).toISOString()
  let screenshot: string | undefined
  try {
    // Carga dinámica para evitar penalizar el bundle inicial si no se usa
    const mod = await import('html2canvas')
    const html2canvas = mod.default || (mod as any)
    const canvas = await html2canvas(document.body, { useCORS: true, logging: false, backgroundColor: null, windowWidth: document.documentElement.scrollWidth, windowHeight: document.documentElement.scrollHeight })
    // Comprimir a JPEG con calidad media para no exceder ~300-500KB típicos
    screenshot = canvas.toDataURL('image/jpeg', 0.7)
    // Control básico de tamaño (~1.5MB máx.)
    if (screenshot && screenshot.length > 1_500_000 * 1.37) { // aprox base64 overhead 37%
      // Reintentar con calidad menor
      screenshot = canvas.toDataURL('image/jpeg', 0.5)
    }
  } catch {
    // Si falla la captura, continuamos sin screenshot
    screenshot = undefined
  }
  const res = await sendBugReport({ message: msg.trim(), user_agent: ua, url, context: { client_ts_gmt3: ts_gmt3 }, screenshot })
      if (res?.status === 'ok') {
        toast.push({ kind: 'success', message: '¡Gracias! Registramos tu reporte para revisión.', title: 'Reporte enviado' })
        setMsg('')
        setOpen(false)
      } else {
        toast.push({ kind: 'error', message: 'No pudimos registrar el reporte (offline o error). Probá más tarde.', title: 'Error' })
      }
    } catch (e) {
      toast.push({ kind: 'error', message: 'No pudimos registrar el reporte (offline o error). Probá más tarde.', title: 'Error' })
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <InjectBRStyles />
      <div className="bugreport-fab" aria-hidden>
        <button onClick={() => setOpen(true)} title="Reportar un problema" style={{ background: theme.danger, color: '#fff' }}>
          <span aria-hidden>🐞</span>
          <span>Reportar</span>
        </button>
      </div>
      {open && (
        <div className="bugreport-modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) setOpen(false) }}>
          <div className="bugreport-modal" role="dialog" aria-modal="true" style={{ background: theme.card, color: theme.text, border: `1px solid ${theme.border}` }}>
            <div className="bugreport-header" style={{ borderBottom: `1px solid ${theme.border}` }}>
              <div>Reportar un problema</div>
              <button onClick={() => setOpen(false)} style={{ background:'none', border:'none', fontSize:18, cursor:'pointer' }}>×</button>
            </div>
            <div className="bugreport-body">
              <label htmlFor="bugreport-comment" style={{ display:'block', fontSize:12, color: theme.name === 'dark' ? '#bbb' : '#333', marginBottom:6 }}>Comentario</label>
              <textarea id="bugreport-comment" placeholder="Contanos qué pasó, qué esperabas que suceda y cualquier detalle útil (pasos, SKU, etc.)"
                value={msg} onChange={e => setMsg(e.target.value)} style={{ background: theme.name === 'dark' ? '#111' : '#fff', color: theme.text, border: `1px solid ${theme.border}` }} />
              <div className="bugreport-muted" style={{ color: theme.name === 'dark' ? '#999' : '#666' }}>
                Se enviará la URL actual, tu User-Agent, la hora local (GMT-3) y, si es posible, una captura de pantalla en baja resolución. No incluyas datos sensibles.
              </div>
            </div>
            <div className="bugreport-actions">
              <button onClick={() => setOpen(false)} disabled={sending} style={{ padding:'8px 12px', background: theme.name === 'dark' ? '#222' : '#eee', color: theme.text, border:`1px solid ${theme.border}`, borderRadius:8, cursor:'pointer' }}>Cancelar</button>
              <button onClick={onSend} disabled={sending} style={{ padding:'8px 12px', background: theme.accent, color:'#fff', border:`1px solid ${theme.accent}`, borderRadius:8, cursor:'pointer' }}>{sending? 'Enviando…' : 'Enviar'}</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
