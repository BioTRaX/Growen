// NG-HEADER: Nombre de archivo: StockShortages.tsx
// NG-HEADER: Ubicación: frontend/src/pages/StockShortages.tsx
// NG-HEADER: Descripción: Página de gestión de faltantes de stock con dashboard y tabla
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { PATHS } from '../routes/paths'
import {
    listShortages,
    getShortagesStats,
    ShortageItem,
    ShortagesStatsResponse,
    ShortageReason,
    REASON_LABELS,
    STATUS_LABELS,
} from '../services/shortages'
import { useToast } from '../components/ToastProvider'
import ReportShortageModal from '../components/ReportShortageModal'

export default function StockShortages() {
    const navigate = useNavigate()
    const { push } = useToast()

    // Estado principal
    const [items, setItems] = useState<ShortageItem[]>([])
    const [stats, setStats] = useState<ShortagesStatsResponse | null>(null)
    const [page, setPage] = useState(1)
    const [total, setTotal] = useState(0)
    const [pages, setPages] = useState(0)
    const [loading, setLoading] = useState(false)

    // Filtros
    const [filterReason, setFilterReason] = useState<ShortageReason | ''>('')

    // Modal
    const [showModal, setShowModal] = useState(false)

    const pageSize = 20

    // Cargar estadísticas
    useEffect(() => {
        getShortagesStats()
            .then(setStats)
            .catch(() => push({ kind: 'error', message: 'Error cargando estadísticas' }))
    }, [])

    // Cargar listado
    const loadItems = async () => {
        setLoading(true)
        try {
            const res = await listShortages({
                page,
                page_size: pageSize,
                reason: filterReason || undefined,
            })
            setItems(res.items)
            setTotal(res.total)
            setPages(res.pages)
        } catch {
            push({ kind: 'error', message: 'Error cargando faltantes' })
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        loadItems()
    }, [page, filterReason])

    const handleSuccess = () => {
        // Recargar datos después de crear un faltante
        setPage(1)
        loadItems()
        getShortagesStats().then(setStats).catch(() => { })
    }

    const formatDate = (isoString: string) => {
        try {
            return new Date(isoString).toLocaleString('es-AR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
            })
        } catch {
            return isoString
        }
    }

    const getReasonColor = (reason: ShortageReason): string => {
        switch (reason) {
            case 'GIFT':
                return '#a78bfa' // violeta
            case 'PENDING_SALE':
                return '#fbbf24' // amarillo
            case 'UNKNOWN':
            default:
                return '#94a3b8' // gris
        }
    }

    return (
        <div className="panel p-4" style={{ margin: 16 }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                <h2 style={{ margin: 0, flex: 1 }}>Faltantes de Stock</h2>
                <button className="btn-dark" onClick={() => setShowModal(true)}>
                    + Reportar Faltante
                </button>
                <button className="btn" onClick={() => navigate(PATHS.stock)}>
                    ← Volver a Stock
                </button>
            </div>

            {/* Dashboard Cards */}
            {stats && (
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                        gap: 16,
                        marginBottom: 24,
                    }}
                >
                    <div className="stat-card">
                        <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent)' }}>
                            {stats.total_items}
                        </div>
                        <div style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>Total Reportes</div>
                    </div>
                    <div className="stat-card">
                        <div style={{ fontSize: '2rem', fontWeight: 700, color: '#f87171' }}>
                            {stats.total_quantity}
                        </div>
                        <div style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>Unidades Faltantes</div>
                    </div>
                    <div className="stat-card">
                        <div style={{ fontSize: '2rem', fontWeight: 700, color: '#22c55e' }}>
                            {stats.this_month}
                        </div>
                        <div style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>Este Mes</div>
                    </div>
                    <div className="stat-card">
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
                            {Object.entries(stats.by_reason).map(([reason, count]) => (
                                <span
                                    key={reason}
                                    style={{
                                        padding: '4px 10px',
                                        borderRadius: 12,
                                        fontSize: '0.85rem',
                                        background: `${getReasonColor(reason as ShortageReason)}33`,
                                        color: getReasonColor(reason as ShortageReason),
                                    }}
                                >
                                    {REASON_LABELS[reason as ShortageReason]}: {count}
                                </span>
                            ))}
                        </div>
                        <div style={{ color: 'var(--muted)', fontSize: '0.9rem', marginTop: 8 }}>
                            Por Motivo
                        </div>
                    </div>
                </div>
            )}

            {/* Filtros */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
                <select
                    className="select"
                    value={filterReason}
                    onChange={(e) => {
                        setFilterReason(e.target.value as ShortageReason | '')
                        setPage(1)
                    }}
                >
                    <option value="">Todos los motivos</option>
                    {Object.entries(REASON_LABELS).map(([key, label]) => (
                        <option key={key} value={key}>
                            {label}
                        </option>
                    ))}
                </select>
                <span style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>
                    {total} resultado{total !== 1 ? 's' : ''}
                </span>
            </div>

            {/* Tabla */}
            <table className="table w-full">
                <thead>
                    <tr>
                        <th style={{ textAlign: 'left' }}>Fecha</th>
                        <th style={{ textAlign: 'left' }}>Producto</th>
                        <th className="text-center">Cantidad</th>
                        <th className="text-center">Motivo</th>
                        <th className="text-center">Estado</th>
                        <th style={{ textAlign: 'left' }}>Usuario</th>
                        <th style={{ textAlign: 'left' }}>Observación</th>
                    </tr>
                </thead>
                <tbody>
                    {loading ? (
                        <tr>
                            <td colSpan={7} style={{ textAlign: 'center', padding: 24 }}>
                                Cargando...
                            </td>
                        </tr>
                    ) : items.length === 0 ? (
                        <tr>
                            <td colSpan={7} style={{ textAlign: 'center', padding: 24, color: 'var(--muted)' }}>
                                No hay faltantes registrados
                            </td>
                        </tr>
                    ) : (
                        items.map((item) => (
                            <tr key={item.id}>
                                <td>{formatDate(item.created_at)}</td>
                                <td>
                                    <a
                                        href={`/productos/${item.product_id}`}
                                        className="product-title"
                                        style={{ fontWeight: 500 }}
                                    >
                                        {item.product_title}
                                    </a>
                                </td>
                                <td className="text-center" style={{ fontWeight: 600, color: '#f87171' }}>
                                    -{item.quantity}
                                </td>
                                <td className="text-center">
                                    <span
                                        style={{
                                            padding: '4px 10px',
                                            borderRadius: 12,
                                            fontSize: '0.85rem',
                                            background: `${getReasonColor(item.reason)}33`,
                                            color: getReasonColor(item.reason),
                                        }}
                                    >
                                        {REASON_LABELS[item.reason]}
                                    </span>
                                </td>
                                <td className="text-center">
                                    <span
                                        style={{
                                            padding: '4px 8px',
                                            borderRadius: 8,
                                            fontSize: '0.8rem',
                                            background: item.status === 'OPEN' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(100, 116, 139, 0.2)',
                                            color: item.status === 'OPEN' ? '#22c55e' : '#64748b',
                                        }}
                                    >
                                        {STATUS_LABELS[item.status]}
                                    </span>
                                </td>
                                <td style={{ color: 'var(--muted)' }}>{item.user_name || '-'}</td>
                                <td
                                    style={{
                                        maxWidth: 200,
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap',
                                        color: 'var(--muted)',
                                    }}
                                    title={item.observation || ''}
                                >
                                    {item.observation || '-'}
                                </td>
                            </tr>
                        ))
                    )}
                </tbody>
            </table>

            {/* Paginación */}
            {pages > 1 && (
                <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'center' }}>
                    <button
                        className="btn"
                        disabled={page === 1 || loading}
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                        ← Anterior
                    </button>
                    <span style={{ padding: '8px 16px', color: 'var(--muted)' }}>
                        Página {page} de {pages}
                    </span>
                    <button
                        className="btn"
                        disabled={page >= pages || loading}
                        onClick={() => setPage((p) => p + 1)}
                    >
                        Siguiente →
                    </button>
                </div>
            )}

            {/* Modal */}
            <ReportShortageModal open={showModal} onClose={() => setShowModal(false)} onSuccess={handleSuccess} />

            {/* Estilos para stat-card */}
            <style>{`
        .stat-card {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 20px;
          text-align: center;
        }
      `}</style>
        </div>
    )
}
