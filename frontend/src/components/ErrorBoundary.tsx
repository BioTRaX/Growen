// NG-HEADER: Nombre de archivo: ErrorBoundary.tsx
// NG-HEADER: Ubicación: frontend/src/components/ErrorBoundary.tsx
// NG-HEADER: Descripción: Límite global de errores para mostrar mensaje amigable
// NG-HEADER: Lineamientos: Ver AGENTS.md
import React from 'react'
import axios from 'axios'

interface State { hasError: boolean; error?: any }

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: any): State {
    return { hasError: true, error }
  }

  async componentDidCatch(error: any, info: any) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary] error', error, info)
    try {
      await axios.post('/debug/frontend/log-error', {
        message: String(error?.message || error || 'unknown'),
        stack: error?.stack || null,
        component_stack: info?.componentStack || null,
        user_agent: navigator.userAgent,
      }, { timeout: 5000 })
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('[ErrorBoundary] no se pudo enviar log-error', e)
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', maxWidth: 720, margin: '4rem auto', fontFamily: 'sans-serif' }}>
          <h2 style={{ marginBottom: '1rem' }}>Ups, algo se rompió al cargar la aplicación.</h2>
          <p style={{ lineHeight: 1.4 }}>
            Refrescá la página. Si persiste, limpiá el caché (Application &gt; Clear storage) o reconstruí el build.
            Revisá la consola del navegador para más detalles. El error fue enviado al backend (si la red respondió).
          </p>
          <button
            onClick={() => {
              // Forzar un intento de recarga limpia
              if (typeof window !== 'undefined') window.location.reload()
            }}
            style={{ marginTop: '1rem', padding: '0.6rem 1.2rem', cursor: 'pointer' }}
          >Reintentar</button>
        </div>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary