// NG-HEADER: Nombre de archivo: AdditionalCostsEditor.tsx
// NG-HEADER: Ubicación: frontend/src/components/sales/AdditionalCostsEditor.tsx
// NG-HEADER: Descripción: Editor de costos adicionales dinámicos para ventas
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState } from 'react'
import type { AdditionalCost } from '../../services/sales'

type Props = {
  costs: AdditionalCost[]
  onChange: (costs: AdditionalCost[]) => void
}

export default function AdditionalCostsEditor({ costs, onChange }: Props) {
  const [newConcept, setNewConcept] = useState('')
  const [newAmount, setNewAmount] = useState<number | ''>('')

  function addCost() {
    if (!newConcept.trim() || !newAmount || newAmount <= 0) return
    onChange([...costs, { concept: newConcept.trim(), amount: Number(newAmount) }])
    setNewConcept('')
    setNewAmount('')
  }

  function removeCost(index: number) {
    onChange(costs.filter((_, i) => i !== index))
  }

  function updateCost(index: number, field: 'concept' | 'amount', value: string | number) {
    const updated = [...costs]
    if (field === 'concept') {
      updated[index] = { ...updated[index], concept: String(value) }
    } else {
      updated[index] = { ...updated[index], amount: Number(value) || 0 }
    }
    onChange(updated)
  }

  const total = costs.reduce((sum, c) => sum + c.amount, 0)

  return (
    <div className="additional-costs-editor" style={{ marginTop: 16 }}>
      <label style={{ fontWeight: 600, marginBottom: 8, display: 'block' }}>
        Costos Adicionales
      </label>
      
      {costs.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {costs.map((cost, idx) => (
            <div 
              key={idx} 
              style={{ 
                display: 'flex', 
                gap: 8, 
                alignItems: 'center', 
                marginBottom: 6,
                background: 'var(--input-bg)',
                padding: '8px 12px',
                borderRadius: 6,
                border: '1px solid var(--input-border)'
              }}
            >
              <input
                type="text"
                value={cost.concept}
                onChange={(e) => updateCost(idx, 'concept', e.target.value)}
                placeholder="Concepto"
                className="input"
                style={{ flex: 1, minWidth: 120 }}
              />
              <span style={{ color: 'var(--muted)' }}>$</span>
              <input
                type="number"
                value={cost.amount}
                onChange={(e) => updateCost(idx, 'amount', e.target.value)}
                placeholder="Monto"
                className="input"
                style={{ width: 100 }}
                min={0}
                step="0.01"
              />
              <button
                type="button"
                onClick={() => removeCost(idx)}
                className="btn btn-danger"
                style={{ padding: '4px 8px', fontSize: '0.85rem' }}
                title="Eliminar"
              >
                ✕
              </button>
            </div>
          ))}
          <div style={{ 
            textAlign: 'right', 
            color: 'var(--success)', 
            fontWeight: 600,
            marginTop: 8 
          }}>
            Total extras: ${total.toFixed(2)}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input
          type="text"
          value={newConcept}
          onChange={(e) => setNewConcept(e.target.value)}
          placeholder="Ej: Envío"
          className="input"
          style={{ flex: 1 }}
          onKeyDown={(e) => e.key === 'Enter' && addCost()}
        />
        <span style={{ color: 'var(--muted)' }}>$</span>
        <input
          type="number"
          value={newAmount}
          onChange={(e) => setNewAmount(e.target.value ? Number(e.target.value) : '')}
          placeholder="0.00"
          className="input"
          style={{ width: 100 }}
          min={0}
          step="0.01"
          onKeyDown={(e) => e.key === 'Enter' && addCost()}
        />
        <button
          type="button"
          onClick={addCost}
          className="btn-primary"
          style={{ padding: '8px 16px' }}
        >
          + Agregar
        </button>
      </div>
    </div>
  )
}

