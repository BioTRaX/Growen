import { useEffect, useState } from 'react'
import { CanonicalOffer, listOffersByCanonical } from '../services/canonical'

interface Props {
  canonicalId: number
  onClose: () => void
}

export default function CanonicalOffers({ canonicalId, onClose }: Props) {
  const [offers, setOffers] = useState<CanonicalOffer[]>([])

  useEffect(() => {
    listOffersByCanonical(canonicalId)
      .then(setOffers)
      .catch(() => {})
  }, [canonicalId])

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.3)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div className="panel p-4" style={{ width: 600, maxHeight: '80%', overflow: 'auto' }}>
        <button onClick={onClose} style={{ float: 'right' }}>
          Cerrar
        </button>
        <h3>Comparativa de precios</h3>
        <table className="table w-full">
          <thead>
            <tr>
              <th>Proveedor</th>
              <th>Compra</th>
              <th>Venta</th>
              <th>Fecha</th>
            </tr>
          </thead>
          <tbody>
            {offers.map((of, idx) => (
              <tr key={idx} className={of.mejor_precio ? 'best-price' : ''}>
                <td>{of.supplier.name}</td>
                <td>{of.precio_compra ?? ''}</td>
                <td>{of.precio_venta ?? ''}</td>
                <td>{of.updated_at ? new Date(of.updated_at).toLocaleString() : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
