// NG-HEADER: Nombre de archivo: MassCanonicalRecoveryModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/MassCanonicalRecoveryModal.tsx
// NG-HEADER: Descripción: Modal para recuperar o descartar sesión de alta masiva abandonada
// NG-HEADER: Lineamientos: Ver AGENTS.md

interface Props {
    open: boolean
    productCount: number
    onContinue: () => void
    onDiscard: () => void
}

/**
 * Modal que aparece cuando se detecta una sesión de alta masiva abandonada.
 * Permite al usuario continuar donde quedó o descartar la sesión.
 */
export default function MassCanonicalRecoveryModal({ open, productCount, onContinue, onDiscard }: Props) {
    if (!open) return null

    return (
        <div className="modal-backdrop" onClick={onDiscard}>
            <div
                className="modal"
                style={{
                    maxWidth: 480,
                    background: 'var(--panel-bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    padding: 24,
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Icono de alerta */}
                <div style={{ textAlign: 'center', marginBottom: 16 }}>
                    <span style={{ fontSize: 48 }}>📋</span>
                </div>

                {/* Título */}
                <h3 style={{
                    margin: 0,
                    marginBottom: 12,
                    textAlign: 'center',
                    color: 'var(--text-color)',
                    fontSize: 20,
                }}>
                    Sesión de Alta Masiva Encontrada
                </h3>

                {/* Descripción */}
                <p style={{
                    margin: 0,
                    marginBottom: 24,
                    textAlign: 'center',
                    color: 'var(--text-secondary)',
                    fontSize: 14,
                    lineHeight: 1.5,
                }}>
                    Hay una sesión pendiente con <strong style={{ color: 'var(--primary)' }}>{productCount} producto{productCount !== 1 ? 's' : ''}</strong> por dar de alta.
                    <br />
                    ¿Deseas continuar donde quedaste o descartar la sesión?
                </p>

                {/* Botones */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'center',
                    gap: 12,
                }}>
                    <button
                        className="btn-secondary"
                        onClick={onDiscard}
                        style={{
                            padding: '10px 20px',
                            borderRadius: 8,
                        }}
                    >
                        Descartar
                    </button>
                    <button
                        className="btn-dark"
                        onClick={onContinue}
                        style={{
                            padding: '10px 20px',
                            borderRadius: 8,
                            background: 'var(--primary)',
                            color: 'white',
                        }}
                    >
                        Continuar
                    </button>
                </div>
            </div>
        </div>
    )
}
