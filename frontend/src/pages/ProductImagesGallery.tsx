// NG-HEADER: Nombre de archivo: ProductImagesGallery.tsx
// NG-HEADER: Ubicación: frontend/src/pages/ProductImagesGallery.tsx
// NG-HEADER: Descripción: Galería de imágenes de un producto con metadatos y acciones.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import http from '../services/http'
import { PATHS } from '../routes/paths'
import ReactCrop, { type Crop, type PixelCrop } from 'react-image-crop'
import 'react-image-crop/dist/ReactCrop.css'

interface ImageVersion {
    path: string | null
    width: number | null
    height: number | null
    size_bytes: number | null
    size_human: string
    mime: string | null
}

interface ProductImage {
    id: number
    url: string
    display_url: string
    path: string
    mime: string | null
    width: number | null
    height: number | null
    bytes: number | null
    size_human: string
    is_primary: boolean
    locked: boolean
    alt_text: string | null
    title_text: string | null
    checksum_sha256: string | null
    created_at: string | null
    updated_at: string | null
    versions: Record<string, ImageVersion>
    has_webp: boolean
}

interface GalleryData {
    product_id: number
    product_name: string
    canonical_sku: string | null
    images: ProductImage[]
    total: number
}

export default function ProductImagesGallery() {
    const { id } = useParams<{ id: string }>()
    const navigate = useNavigate()

    const [data, setData] = useState<GalleryData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [selectedImage, setSelectedImage] = useState<ProductImage | null>(null)
    const [processing, setProcessing] = useState<number | null>(null)
    const [cacheBuster, setCacheBuster] = useState(Date.now())

    // Helper to add cache buster to URLs
    const addCacheBuster = (url: string) => {
        if (!url) return url
        const sep = url.includes('?') ? '&' : '?'
        return `${url}${sep}t=${cacheBuster}`
    }

    const loadImages = useCallback(async () => {
        if (!id) return
        setLoading(true)
        setError(null)
        try {
            const res = await http.get(`/products/${id}/images`)
            setData(res.data)
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Error al cargar imágenes')
        } finally {
            setLoading(false)
        }
    }, [id])

    useEffect(() => {
        loadImages()
    }, [loadImages])

    async function handleSetPrimary(imgId: number) {
        if (!id) return
        setProcessing(imgId)
        try {
            await http.post(`/products/${id}/images/${imgId}/set-primary`)
            await loadImages()
        } catch (e: any) {
            alert(e.response?.data?.detail || 'Error al establecer imagen principal')
        } finally {
            setProcessing(null)
        }
    }

    // State for delete confirmation
    const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
    // State for crop confirmation (used for quick square crop)
    const [confirmCropId, setConfirmCropId] = useState<number | null>(null)

    // State for interactive visual crop
    const [cropMode, setCropMode] = useState(false)
    const [crop, setCrop] = useState<Crop>()
    const [completedCrop, setCompletedCrop] = useState<PixelCrop>()
    const imgRef = useRef<HTMLImageElement>(null)

    // State for configurable square crop margin
    const [cropMargin, setCropMargin] = useState(0) // 0-40% to trim from each side

    async function handleApplyCrop() {
        if (!id || !selectedImage || !completedCrop || !imgRef.current) return

        // Convert pixel crop to percentage
        const imgWidth = imgRef.current.naturalWidth
        const imgHeight = imgRef.current.naturalHeight

        if (imgWidth === 0 || imgHeight === 0) {
            alert('Error: no se pudo obtener el tamaño de la imagen')
            return
        }

        const cropData = {
            x: (completedCrop.x / imgRef.current.width) * 100,
            y: (completedCrop.y / imgRef.current.height) * 100,
            width: (completedCrop.width / imgRef.current.width) * 100,
            height: (completedCrop.height / imgRef.current.height) * 100,
        }

        setProcessing(selectedImage.id)
        try {
            await http.post(`/products/${id}/images/${selectedImage.id}/crop-custom`, cropData)
            setCacheBuster(Date.now())
            setCropMode(false)
            setCrop(undefined)
            setCompletedCrop(undefined)
            await loadImages()
            // Refresh selected image
            const res = await http.get(`/products/${id}/images`)
            const updated = res.data.images.find((img: ProductImage) => img.id === selectedImage.id)
            if (updated) setSelectedImage(updated)
            alert('Recorte aplicado')
        } catch (e: any) {
            alert(e.response?.data?.detail || 'Error al recortar imagen')
        } finally {
            setProcessing(null)
        }
    }

    function cancelCrop() {
        setCropMode(false)
        setCrop(undefined)
        setCompletedCrop(undefined)
    }

    async function handleDelete(imgId: number) {
        if (!id) return
        setProcessing(imgId)
        try {
            await http.delete(`/products/${id}/images/${imgId}`)
            setSelectedImage(null)
            setConfirmDeleteId(null)
            await loadImages()
        } catch (e: any) {
            alert(e.response?.data?.detail || 'Error al eliminar imagen')
        } finally {
            setProcessing(null)
        }
    }

    async function handleRotate(imgId: number, degrees: number = 90) {
        if (!id) return
        setProcessing(imgId)
        try {
            await http.post(`/products/${id}/images/${imgId}/rotate`, { degrees })
            // Update cache buster to force browser reload
            setCacheBuster(Date.now())
            await loadImages()
            // Refresh selected image if it's the same
            if (selectedImage && selectedImage.id === imgId) {
                const res = await http.get(`/products/${id}/images`)
                const updated = res.data.images.find((img: ProductImage) => img.id === imgId)
                if (updated) setSelectedImage(updated)
            }
        } catch (e: any) {
            alert(e.response?.data?.detail || 'Error al rotar imagen')
        } finally {
            setProcessing(null)
        }
    }

    async function handleCropSquare(imgId: number) {
        if (!id) return
        setProcessing(imgId)
        try {
            await http.post(`/products/${id}/images/${imgId}/crop-square`, null, {
                params: { margin_percent: cropMargin }
            })
            // Update cache buster to force browser reload
            setCacheBuster(Date.now())
            await loadImages()
            // Refresh selected image if it's the same
            if (selectedImage && selectedImage.id === imgId) {
                const res = await http.get(`/products/${id}/images`)
                const updated = res.data.images.find((img: ProductImage) => img.id === imgId)
                if (updated) setSelectedImage(updated)
            }
        } catch (e: any) {
            alert(e.response?.data?.detail || 'Error al recortar imagen')
        } finally {
            setProcessing(null)
        }
    }

    async function handleGenerateWebP(imgId: number) {
        if (!id) return
        setProcessing(imgId)
        try {
            await http.post(`/products/${id}/images/${imgId}/generate-webp`)
            await loadImages()
            alert('WebP generado correctamente')
        } catch (e: any) {
            alert(e.response?.data?.detail || 'Error al generar WebP')
        } finally {
            setProcessing(null)
        }
    }

    async function handleWatermark(imgId: number) {
        if (!id) return
        setProcessing(imgId)
        try {
            await http.post(`/products/${id}/images/${imgId}/process/watermark`, {})
            await loadImages()
            alert('Marca de agua aplicada')
        } catch (e: any) {
            alert(e.response?.data?.detail || 'Error al aplicar marca de agua')
        } finally {
            setProcessing(null)
        }
    }

    async function handleLogo(imgId: number) {
        if (!id) return
        setProcessing(imgId)
        try {
            await http.post(`/products/${id}/images/${imgId}/process/logo`, {
                position: 'br',
                scale: 30,
                opacity: 0.9,
            })
            // Update cache buster to force browser reload
            setCacheBuster(Date.now())
            await loadImages()
            // Refresh selected image if it's the same
            if (selectedImage && selectedImage.id === imgId) {
                const res = await http.get(`/products/${id}/images`)
                const updated = res.data.images.find((img: ProductImage) => img.id === imgId)
                if (updated) setSelectedImage(updated)
            }
            alert('Logo aplicado')
        } catch (e: any) {
            alert(e.response?.data?.detail || 'Error al aplicar logo')
        } finally {
            setProcessing(null)
        }
    }

    async function handleDownload(img: ProductImage) {
        // Download the WebP derivative (display_url) with SKU as filename
        try {
            // Use display_url (WebP derivative) if available, otherwise fall back to url
            const downloadUrl = img.display_url || img.url

            // Fetch the image as blob to force custom filename
            const response = await fetch(downloadUrl)
            const blob = await response.blob()

            // Determine extension - prefer webp if it's a WebP file
            let ext = 'webp'
            if (downloadUrl.includes('.webp')) {
                ext = 'webp'
            } else if (downloadUrl.includes('.jpg') || downloadUrl.includes('.jpeg')) {
                ext = 'jpg'
            } else if (downloadUrl.includes('.png')) {
                ext = 'png'
            }

            // Debug: log what we have
            console.log('Download debug:', {
                canonical_sku: data?.canonical_sku,
                product_name: data?.product_name,
                downloadUrl,
                ext
            })

            // Use canonical_sku if available, otherwise use product name or fallback
            let baseName = 'image'
            if (data?.canonical_sku && data.canonical_sku.trim()) {
                baseName = data.canonical_sku.trim()
            } else if (data?.product_name && data.product_name.trim()) {
                // Clean product name for filename (remove special chars)
                baseName = data.product_name.trim().replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 50)
            } else {
                baseName = `image-${img.id}`
            }
            const filename = `${baseName}.${ext}`
            console.log('Download filename:', filename)

            // Create blob URL and trigger download
            const blobUrl = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = blobUrl
            link.download = filename
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            URL.revokeObjectURL(blobUrl)
        } catch (e) {
            console.error('Download error:', e)
            alert('Error al descargar imagen')
        }
    }

    if (loading) {
        return (
            <div className="container" style={{ padding: 24 }}>
                <div className="skeleton" style={{ height: 40, width: 300, marginBottom: 24 }} />
                <div className="row" style={{ gap: 16, flexWrap: 'wrap' }}>
                    {[1, 2, 3, 4].map(i => (
                        <div key={i} className="skeleton" style={{ width: 200, height: 200, borderRadius: 8 }} />
                    ))}
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="container" style={{ padding: 24 }}>
                <div className="alert alert-error">{error}</div>
                <button className="btn" onClick={() => navigate(-1)}>← Volver</button>
            </div>
        )
    }

    if (!data) return null

    return (
        <div className="container" style={{ padding: 24, maxWidth: 1200 }}>
            {/* Header */}
            <div className="row" style={{ alignItems: 'center', marginBottom: 24, gap: 16, flexWrap: 'wrap' }}>
                <Link to={PATHS.imagesProducts} className="btn btn-ghost">← Volver</Link>
                <div style={{ flex: 1, minWidth: 200 }}>
                    <h1 style={{ margin: 0, fontSize: 24 }}>{data.product_name}</h1>
                    {data.canonical_sku && (
                        <span style={{
                            background: 'var(--accent, #22c55e)',
                            color: '#000',
                            padding: '2px 8px',
                            borderRadius: 4,
                            fontSize: 12,
                            fontWeight: 600,
                            marginTop: 4,
                            display: 'inline-block'
                        }}>
                            {data.canonical_sku}
                        </span>
                    )}
                </div>
                <div className="text-sm" style={{ opacity: 0.6 }}>
                    {data.total} imagen{data.total !== 1 ? 'es' : ''}
                </div>
            </div>

            {/* Gallery Grid */}
            {data.images.length === 0 ? (
                <div className="card" style={{ padding: 48, textAlign: 'center' }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>📷</div>
                    <p style={{ margin: 0, opacity: 0.6 }}>Este producto no tiene imágenes</p>
                </div>
            ) : (
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                    gap: 16
                }}>
                    {data.images.map(img => (
                        <div
                            key={img.id}
                            className="card"
                            style={{
                                padding: 0,
                                overflow: 'hidden',
                                cursor: 'pointer',
                                position: 'relative',
                                border: img.is_primary ? '2px solid var(--accent, #22c55e)' : undefined
                            }}
                            onClick={() => setSelectedImage(img)}
                        >
                            <img
                                src={addCacheBuster(img.display_url)}
                                alt={img.alt_text || `Imagen ${img.id}`}
                                style={{
                                    width: '100%',
                                    aspectRatio: '1',
                                    objectFit: 'cover',
                                    display: 'block'
                                }}
                                onError={(e) => {
                                    const target = e.target as HTMLImageElement
                                    if (target.src !== img.url && img.url) {
                                        target.src = img.url
                                    }
                                }}
                            />
                            {img.is_primary && (
                                <span style={{
                                    position: 'absolute',
                                    top: 8,
                                    left: 8,
                                    background: 'var(--accent, #22c55e)',
                                    color: '#000',
                                    padding: '2px 6px',
                                    borderRadius: 4,
                                    fontSize: 10,
                                    fontWeight: 600
                                }}>
                                    PRINCIPAL
                                </span>
                            )}
                            {img.has_webp && (
                                <span style={{
                                    position: 'absolute',
                                    top: 8,
                                    right: 8,
                                    background: '#3b82f6',
                                    color: '#fff',
                                    padding: '2px 6px',
                                    borderRadius: 4,
                                    fontSize: 10,
                                    fontWeight: 600
                                }}>
                                    WebP
                                </span>
                            )}
                            <div style={{
                                padding: 8,
                                background: 'var(--bg-secondary, #1a1a1a)',
                                fontSize: 11,
                                display: 'flex',
                                justifyContent: 'space-between'
                            }}>
                                <span>{img.size_human}</span>
                                <span>{img.width}×{img.height}</span>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Image Detail Modal */}
            {selectedImage && (
                <div
                    style={{
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        background: 'rgba(0,0,0,0.85)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 1000,
                        padding: 24
                    }}
                    onClick={() => setSelectedImage(null)}
                >
                    <div
                        className="card"
                        style={{
                            maxWidth: 900,
                            maxHeight: '90vh',
                            overflow: 'auto',
                            display: 'flex',
                            gap: 24,
                            padding: 24
                        }}
                        onClick={e => e.stopPropagation()}
                    >
                        {/* Image Preview */}
                        <div style={{ flex: 1, minWidth: 300 }}>
                            {cropMode ? (
                                <ReactCrop
                                    crop={crop}
                                    onChange={(c) => setCrop(c)}
                                    onComplete={(c) => setCompletedCrop(c)}
                                    style={{ maxHeight: 500, background: '#111', borderRadius: 8 }}
                                >
                                    <img
                                        ref={imgRef}
                                        src={addCacheBuster(selectedImage.display_url || selectedImage.url)}
                                        alt={selectedImage.alt_text || 'Imagen'}
                                        style={{
                                            maxWidth: '100%',
                                            maxHeight: 500,
                                            objectFit: 'contain',
                                        }}
                                    />
                                </ReactCrop>
                            ) : (
                                <img
                                    src={addCacheBuster(selectedImage.display_url || selectedImage.url)}
                                    alt={selectedImage.alt_text || 'Imagen'}
                                    style={{
                                        width: '100%',
                                        maxHeight: 500,
                                        objectFit: 'contain',
                                        borderRadius: 8,
                                        background: '#111'
                                    }}
                                    onError={(e) => {
                                        // Fall back to url if display_url fails
                                        const target = e.target as HTMLImageElement
                                        if (target.src !== selectedImage.url && selectedImage.url) {
                                            target.src = selectedImage.url
                                        }
                                    }}
                                />
                            )}

                            {/* Crop action buttons - shown when in crop mode */}
                            {cropMode && (
                                <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'center' }}>
                                    <button
                                        className="btn-primary btn-lg"
                                        onClick={handleApplyCrop}
                                        disabled={!completedCrop || processing === selectedImage.id}
                                    >
                                        ✓ Aplicar Recorte
                                    </button>
                                    <button
                                        className="btn btn-lg"
                                        onClick={cancelCrop}
                                        disabled={processing === selectedImage.id}
                                    >
                                        Cancelar
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Metadata & Actions */}
                        <div style={{ width: 280, display: 'flex', flexDirection: 'column', gap: 16 }}>
                            <h3 style={{ margin: 0 }}>Metadatos</h3>

                            <table style={{ fontSize: 12, width: '100%' }}>
                                <tbody>
                                    <tr>
                                        <td style={{ opacity: 0.6, padding: '4px 8px 4px 0' }}>ID</td>
                                        <td>{selectedImage.id}</td>
                                    </tr>
                                    <tr>
                                        <td style={{ opacity: 0.6, padding: '4px 8px 4px 0' }}>Formato</td>
                                        <td>{selectedImage.mime || '?'}</td>
                                    </tr>
                                    <tr>
                                        <td style={{ opacity: 0.6, padding: '4px 8px 4px 0' }}>Dimensiones</td>
                                        <td>{selectedImage.width || '?'} × {selectedImage.height || '?'} px</td>
                                    </tr>
                                    <tr>
                                        <td style={{ opacity: 0.6, padding: '4px 8px 4px 0' }}>Tamaño</td>
                                        <td>{selectedImage.size_human}</td>
                                    </tr>
                                    <tr>
                                        <td style={{ opacity: 0.6, padding: '4px 8px 4px 0' }}>Creación</td>
                                        <td>{selectedImage.created_at ? new Date(selectedImage.created_at).toLocaleDateString() : '?'}</td>
                                    </tr>
                                    {selectedImage.checksum_sha256 && (
                                        <tr>
                                            <td style={{ opacity: 0.6, padding: '4px 8px 4px 0' }}>SHA256</td>
                                            <td style={{ fontSize: 9, wordBreak: 'break-all' }}>{selectedImage.checksum_sha256.substring(0, 16)}...</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>

                            {/* Versions */}
                            {Object.keys(selectedImage.versions).length > 0 && (
                                <>
                                    <h4 style={{ margin: 0 }}>Versiones</h4>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11 }}>
                                        {Object.entries(selectedImage.versions).map(([kind, v]) => (
                                            <div key={kind} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                                                <span style={{ textTransform: 'uppercase', fontWeight: 600 }}>{kind}</span>
                                                <span>{v.width}×{v.height} • {v.size_human}</span>
                                            </div>
                                        ))}
                                    </div>
                                </>
                            )}

                            {/* Processing Actions */}
                            <h4 style={{ margin: 0 }}>Procesamiento</h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                <div style={{ display: 'flex', gap: 8 }}>
                                    <button
                                        className="btn btn-sm"
                                        onClick={() => handleRotate(selectedImage.id, 270)}
                                        disabled={processing === selectedImage.id}
                                        title="Rotar 90° izquierda"
                                    >
                                        ↺ -90°
                                    </button>
                                    <button
                                        className="btn btn-sm"
                                        onClick={() => handleRotate(selectedImage.id, 90)}
                                        disabled={processing === selectedImage.id}
                                        title="Rotar 90° derecha"
                                    >
                                        ↻ +90°
                                    </button>
                                </div>
                                {/* Crop buttons */}
                                <div style={{ display: 'flex', gap: 8 }}>
                                    <button
                                        className="btn btn-sm"
                                        onClick={() => setCropMode(true)}
                                        disabled={processing === selectedImage.id || cropMode}
                                        title="Recortar área personalizada"
                                    >
                                        ✂️ Recortar
                                    </button>
                                    {confirmCropId === selectedImage.id ? (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <label style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                                                    Margen: {cropMargin}%
                                                </label>
                                                <input
                                                    type="range"
                                                    min={0}
                                                    max={40}
                                                    step={5}
                                                    value={cropMargin}
                                                    onChange={(e) => setCropMargin(Number(e.target.value))}
                                                    style={{ flex: 1, minWidth: 80 }}
                                                />
                                            </div>
                                            <div style={{ display: 'flex', gap: 8 }}>
                                                <button
                                                    className="btn btn-sm btn-primary"
                                                    onClick={() => { handleCropSquare(selectedImage.id); setConfirmCropId(null) }}
                                                    disabled={processing === selectedImage.id}
                                                >
                                                    ✓ Aplicar
                                                </button>
                                                <button
                                                    className="btn btn-sm"
                                                    onClick={() => setConfirmCropId(null)}
                                                >
                                                    ✕
                                                </button>
                                            </div>
                                        </div>
                                    ) : (
                                        <button
                                            className="btn btn-sm"
                                            onClick={() => setConfirmCropId(selectedImage.id)}
                                            disabled={processing === selectedImage.id}
                                            title="Recortar automático a cuadrado centrado"
                                        >
                                            ⬜ Cuadrado
                                        </button>
                                    )}
                                </div>
                                <button
                                    className="btn btn-sm"
                                    onClick={() => handleGenerateWebP(selectedImage.id)}
                                    disabled={processing === selectedImage.id}
                                >
                                    🖼️ Generar WebP
                                </button>
                                <button
                                    className="btn btn-sm"
                                    onClick={() => handleWatermark(selectedImage.id)}
                                    disabled={processing === selectedImage.id}
                                >
                                    💧 Marca de Agua
                                </button>
                                <button
                                    className="btn btn-sm"
                                    onClick={() => handleLogo(selectedImage.id)}
                                    disabled={processing === selectedImage.id}
                                >
                                    🏷️ Aplicar Logo
                                </button>
                            </div>

                            {/* Actions */}
                            <h4 style={{ margin: 0 }}>Acciones</h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                {!selectedImage.is_primary && (
                                    <button
                                        className="btn btn-sm"
                                        onClick={() => handleSetPrimary(selectedImage.id)}
                                        disabled={processing === selectedImage.id}
                                    >
                                        ⭐ Establecer Principal
                                    </button>
                                )}
                                <button
                                    className="btn btn-sm"
                                    onClick={() => handleDownload(selectedImage)}
                                >
                                    ⬇️ Descargar
                                </button>

                                {/* Delete with confirmation */}
                                {confirmDeleteId === selectedImage.id ? (
                                    <div style={{ display: 'flex', gap: 8 }}>
                                        <button
                                            className="btn btn-sm btn-error"
                                            onClick={() => handleDelete(selectedImage.id)}
                                            disabled={processing === selectedImage.id}
                                        >
                                            ✓ Confirmar
                                        </button>
                                        <button
                                            className="btn btn-sm"
                                            onClick={() => setConfirmDeleteId(null)}
                                        >
                                            Cancelar
                                        </button>
                                    </div>
                                ) : (
                                    <button
                                        className="btn btn-sm btn-error"
                                        onClick={() => setConfirmDeleteId(selectedImage.id)}
                                        disabled={processing === selectedImage.id || selectedImage.locked}
                                    >
                                        🗑️ Eliminar
                                    </button>
                                )}
                            </div>

                            <button
                                className="btn btn-ghost"
                                onClick={() => setSelectedImage(null)}
                                style={{ marginTop: 'auto' }}
                            >
                                Cerrar
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
