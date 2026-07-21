// NG-HEADER: Nombre de archivo: purchaseLineTotal.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/purchases/purchaseLineTotal.spec.ts
// NG-HEADER: Descripción: Pruebas del total reactivo mostrado por línea de compra.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { describe, expect, it } from 'vitest'
import { purchaseLineTotal } from './purchaseLineTotal'

describe('purchaseLineTotal', () => {
  it('multiplica cantidad y costo cuando no hay bonificación', () => {
    expect(purchaseLineTotal({ qty: 2, unit_cost: 2059.2, line_discount: 0 })).toBe(4118.4)
  })

  it('aplica la bonificación porcentual y redondea a centavos', () => {
    expect(purchaseLineTotal({ qty: 3, unit_cost: 10.005, line_discount: 20 })).toBe(24.01)
  })

  it('interpreta una bonificación negativa como recargo durante la edición', () => {
    expect(purchaseLineTotal({ qty: 2, unit_cost: 2216.8, line_discount: -20 })).toBe(5320.32)
  })

  it('evita mostrar NaN ante una edición numérica incompleta', () => {
    expect(purchaseLineTotal({ qty: Number.NaN, unit_cost: 100, line_discount: 0 })).toBe(0)
  })
})
