// NG-HEADER: Nombre de archivo: SalesChannelSelector.tsx
// NG-HEADER: Ubicación: frontend/src/components/sales/SalesChannelSelector.tsx
// NG-HEADER: Descripción: Selector de canal de venta con búsqueda y creación al vuelo
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState, useEffect, useRef } from 'react'
import { listChannels, createChannel, type SalesChannel } from '../../services/sales'

type Props = {
  value: number | null
  onChange: (channelId: number | null, channelName?: string) => void
}

export default function SalesChannelSelector({ value, onChange }: Props) {
  const [channels, setChannels] = useState<SalesChannel[]>([])
  const [search, setSearch] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadChannels()
  }, [])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
        setShowCreate(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  async function loadChannels() {
    try {
      const data = await listChannels()
      setChannels(data.items)
    } catch (err) {
      console.error('Error loading channels:', err)
    }
  }

  async function handleCreate() {
    if (!newName.trim()) return
    setCreating(true)
    setError(null)
    try {
      const channel = await createChannel(newName.trim())
      setChannels(prev => [...prev, channel].sort((a, b) => a.name.localeCompare(b.name)))
      onChange(channel.id, channel.name)
      setNewName('')
      setShowCreate(false)
      setIsOpen(false)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Error al crear canal')
    } finally {
      setCreating(false)
    }
  }

  const selectedChannel = channels.find(c => c.id === value)
  const filteredChannels = channels.filter(c => 
    c.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <label style={{ fontWeight: 600, marginBottom: 8, display: 'block' }}>
        Canal de Venta
      </label>

      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          background: 'var(--input-bg)',
          border: '1px solid var(--input-border)',
          borderRadius: 6,
          cursor: 'pointer',
          minHeight: 44,
        }}
      >
        <span style={{ color: selectedChannel ? 'var(--text)' : 'var(--muted)' }}>
          {selectedChannel ? selectedChannel.name : 'Seleccionar canal...'}
        </span>
        <span style={{ color: 'var(--muted)' }}>▼</span>
      </div>

      {isOpen && (
        <div
          className="dropdown-panel"
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: 4,
            zIndex: 100,
            maxHeight: 300,
            overflow: 'auto',
          }}
        >
          <div style={{ padding: 8, borderBottom: '1px solid var(--border)' }}>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar canal..."
              className="input"
              style={{ width: '100%' }}
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
          </div>

          <div style={{ maxHeight: 180, overflow: 'auto' }}>
            {/* Opción para quitar selección */}
            <div
              onClick={() => {
                onChange(null)
                setIsOpen(false)
              }}
              style={{
                padding: '10px 14px',
                cursor: 'pointer',
                color: 'var(--muted)',
                fontStyle: 'italic',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--table-row-hover)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              Sin canal
            </div>

            {filteredChannels.map((ch) => (
              <div
                key={ch.id}
                onClick={() => {
                  onChange(ch.id, ch.name)
                  setIsOpen(false)
                  setSearch('')
                }}
                style={{
                  padding: '10px 14px',
                  cursor: 'pointer',
                  background: ch.id === value ? 'rgba(124, 77, 255, 0.2)' : 'transparent',
                }}
                onMouseEnter={(e) => {
                  if (ch.id !== value) e.currentTarget.style.background = 'var(--table-row-hover)'
                }}
                onMouseLeave={(e) => {
                  if (ch.id !== value) e.currentTarget.style.background = 'transparent'
                }}
              >
                {ch.name}
              </div>
            ))}

            {filteredChannels.length === 0 && search && (
              <div style={{ padding: '10px 14px', color: 'var(--muted)', fontStyle: 'italic' }}>
                No se encontraron canales
              </div>
            )}
          </div>

          {/* Crear nuevo canal */}
          <div style={{ borderTop: '1px solid var(--border)', padding: 8 }}>
            {!showCreate ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  setShowCreate(true)
                  setNewName(search)
                }}
                className="btn-primary"
                style={{ width: '100%', padding: '8px 12px' }}
              >
                + Agregar nuevo canal
              </button>
            ) : (
              <div onClick={(e) => e.stopPropagation()}>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Nombre del canal"
                  className="input"
                  style={{ width: '100%', marginBottom: 8 }}
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                />
                {error && (
                  <div style={{ color: '#f87171', fontSize: '0.85rem', marginBottom: 8 }}>
                    {error}
                  </div>
                )}
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => {
                      setShowCreate(false)
                      setNewName('')
                      setError(null)
                    }}
                    className="btn"
                    style={{ flex: 1 }}
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    onClick={handleCreate}
                    className="btn-primary"
                    style={{ flex: 1 }}
                    disabled={creating || !newName.trim()}
                  >
                    {creating ? 'Creando...' : 'Crear'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

