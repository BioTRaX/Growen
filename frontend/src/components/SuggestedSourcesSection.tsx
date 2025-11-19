// NG-HEADER: Nombre de archivo: SuggestedSourcesSection.tsx
// NG-HEADER: Ubicación: frontend/src/components/SuggestedSourcesSection.tsx
// NG-HEADER: Descripción: Sección de fuentes sugeridas automáticamente (MCP Web Search)
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useState } from 'react'
import { useToast } from './ToastProvider'
import {
  discoverProductSources,
  addSourceFromSuggestion,
  batchAddSourcesFromSuggestions,
  type DiscoveredSource,
  type BatchSourceResult,
} from '../services/market'

interface SuggestedSourcesSectionProps {
  productId: number
  productName: string
  onSourcesAdded?: () => void
}

export default function SuggestedSourcesSection({
  productId,
  productName,
  onSourcesAdded,
}: SuggestedSourcesSectionProps) {
  const { push } = useToast()

  const [discovering, setDiscovering] = useState(false)
  const [suggestions, setSuggestions] = useState<DiscoveredSource[]>([])
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set())
  const [adding, setAdding] = useState(false)
  const [queryUsed, setQueryUsed] = useState<string>('')
  const [markAsMandatory, setMarkAsMandatory] = useState(false)

  async function handleDiscover() {
    setDiscovering(true)
    setSuggestions([])
    setSelectedUrls(new Set())
    setQueryUsed('')

    try {
      const result = await discoverProductSources(productId, 20) // Max 20 resultados

      if (!result.success) {
        push({
          kind: 'error',
          message: result.error || 'Error al buscar fuentes',
        })
        return
      }

      setSuggestions(result.sources)
      setQueryUsed(result.query)

      if (result.sources.length === 0) {
        push({
          kind: 'info',
          message: `No se encontraron fuentes válidas para "${productName}". Prueba agregar manualmente.`,
        })
      } else {
        push({
          kind: 'success',
          message: `${result.sources.length} fuentes sugeridas encontradas`,
        })
      }
    } catch (error: any) {
      push({
        kind: 'error',
        message: error?.message || 'Error al buscar fuentes',
      })
    } finally {
      setDiscovering(false)
    }
  }

  function handleToggleSelection(url: string) {
    const newSelected = new Set(selectedUrls)
    if (newSelected.has(url)) {
      newSelected.delete(url)
    } else {
      newSelected.add(url)
    }
    setSelectedUrls(newSelected)
  }

  function handleSelectAll() {
    if (selectedUrls.size === suggestions.length) {
      setSelectedUrls(new Set())
    } else {
      setSelectedUrls(new Set(suggestions.map(s => s.url)))
    }
  }

  async function handleAddSelected() {
    if (selectedUrls.size === 0) {
      push({ kind: 'info', message: 'Selecciona al menos una fuente' })
      return
    }

    setAdding(true)

    try {
      const sourcesToAdd = suggestions
        .filter(s => selectedUrls.has(s.url))
        .map(s => ({
          url: s.url,
          source_name: undefined, // Se detecta automáticamente del dominio
          validate_price: true,
          source_type: 'static' as const,
          is_mandatory: markAsMandatory, // Usar valor del checkbox
        }))

      const result = await batchAddSourcesFromSuggestions(productId, {
        sources: sourcesToAdd,
        stop_on_error: false,
      })

      const successCount = result.successful
      const failCount = result.failed

      if (successCount > 0) {
        push({
          kind: 'success',
          message: `${successCount} fuente${successCount > 1 ? 's' : ''} agregada${successCount > 1 ? 's' : ''} exitosamente`,
        })

        // Limpiar sugerencias agregadas exitosamente
        const addedUrls = new Set(
          result.results.filter((r: BatchSourceResult) => r.success).map((r: BatchSourceResult) => r.url)
        )
        setSuggestions(suggestions.filter(s => !addedUrls.has(s.url)))
        setSelectedUrls(new Set())

        // Notificar al padre
        if (onSourcesAdded) {
          onSourcesAdded()
        }
      }

      if (failCount > 0) {
        const failures = result.results.filter((r: BatchSourceResult) => !r.success)
        const failureMessages = failures.map((f: BatchSourceResult) => `• ${f.url}: ${f.message}`)
        push({
          kind: 'error',
          message: `${failCount} fuente${failCount > 1 ? 's' : ''} no pudo${failCount > 1 ? 'ieron' : ''} agregarse:\n${failureMessages.slice(0, 3).join('\n')}${failureMessages.length > 3 ? '\n...' : ''}`,
        })
      }
    } catch (error: any) {
      push({
        kind: 'error',
        message: error?.message || 'Error al agregar fuentes',
      })
    } finally {
      setAdding(false)
    }
  }

  return (
    <div style={{ marginTop: 24, padding: 16, background: 'var(--bg-secondary)', borderRadius: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
          🔍 Buscar fuentes automáticamente
        </h3>
        <button
          onClick={handleDiscover}
          disabled={discovering}
          style={{
            padding: '8px 16px',
            background: 'var(--primary)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            cursor: discovering ? 'not-allowed' : 'pointer',
            opacity: discovering ? 0.6 : 1,
            fontWeight: 500,
          }}
        >
          {discovering ? 'Buscando...' : 'Buscar ahora'}
        </button>
      </div>

      <p style={{ margin: '8px 0', fontSize: 14, color: 'var(--text-secondary)' }}>
        El sistema buscará automáticamente tiendas online con precios para este producto usando MCP Web Search.
      </p>

      {queryUsed && (
        <div style={{ marginTop: 12, padding: 8, background: 'var(--bg-tertiary)', borderRadius: 4, fontSize: 13 }}>
          <strong>Query usada:</strong> "{queryUsed}"
        </div>
      )}

      {suggestions.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button
                onClick={handleSelectAll}
                style={{
                  padding: '6px 12px',
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border)',
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontSize: 13,
                }}
              >
                {selectedUrls.size === suggestions.length ? 'Deseleccionar todo' : 'Seleccionar todo'}
              </button>
              <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                {selectedUrls.size} de {suggestions.length} seleccionadas
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={markAsMandatory}
                  onChange={(e) => setMarkAsMandatory(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ fontWeight: markAsMandatory ? 600 : 400, color: markAsMandatory ? 'var(--warning)' : 'inherit' }}>
                  Marcar como obligatorias
                </span>
              </label>
              <button
                onClick={handleAddSelected}
                disabled={selectedUrls.size === 0 || adding}
                style={{
                  padding: '8px 16px',
                  background: selectedUrls.size > 0 ? 'var(--success)' : 'var(--bg-tertiary)',
                  color: selectedUrls.size > 0 ? 'white' : 'var(--text-secondary)',
                  border: 'none',
                  borderRadius: 6,
                  cursor: selectedUrls.size > 0 && !adding ? 'pointer' : 'not-allowed',
                  fontWeight: 500,
                }}
              >
                {adding ? 'Agregando...' : `Agregar seleccionadas (${selectedUrls.size})`}
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {suggestions.map((source, idx) => {
              const isSelected = selectedUrls.has(source.url)
              return (
                <div
                  key={idx}
                  onClick={() => handleToggleSelection(source.url)}
                  style={{
                    padding: 12,
                    background: isSelected ? 'var(--primary-bg)' : 'var(--bg-primary)',
                    border: `1px solid ${isSelected ? 'var(--primary)' : 'var(--border)'}`,
                    borderRadius: 6,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'start', gap: 12 }}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleToggleSelection(source.url)}
                      style={{ marginTop: 4, cursor: 'pointer' }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <strong style={{ fontSize: 14 }}>{source.title}</strong>
                        {source.url.includes('mercadolibre') && (
                          <span style={{ fontSize: 11, padding: '2px 6px', background: 'var(--warning-bg)', color: 'var(--warning)', borderRadius: 4, fontWeight: 600 }}>
                            MERCADOLIBRE
                          </span>
                        )}
                        {source.url.includes('santaplanta') && (
                          <span style={{ fontSize: 11, padding: '2px 6px', background: 'var(--success-bg)', color: 'var(--success)', borderRadius: 4, fontWeight: 600 }}>
                            ALTA CONFIANZA
                          </span>
                        )}
                      </div>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        style={{
                          fontSize: 12,
                          color: 'var(--primary)',
                          textDecoration: 'none',
                          wordBreak: 'break-all',
                        }}
                      >
                        {source.url}
                      </a>
                      {source.snippet && (
                        <p style={{ margin: '8px 0 0 0', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                          {source.snippet}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {suggestions.length === 0 && !discovering && queryUsed && (
        <div style={{ marginTop: 16, padding: 16, background: 'var(--bg-tertiary)', borderRadius: 6, textAlign: 'center' }}>
          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
            No se encontraron fuentes válidas. Prueba agregar manualmente usando el botón "Agregar fuente".
          </p>
        </div>
      )}
    </div>
  )
}
