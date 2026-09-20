// NG-HEADER: Nombre de archivo: purchaseLineTotal.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/purchases/purchaseLineTotal.ts
// NG-HEADER: Descripción: Cálculo monetario de totales por línea de compra.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import type { PurchaseLine } from '../../services/purchases'

type LineAmounts = Pick<PurchaseLine, 'qty' | 'unit_cost' | 'line_discount'>

export function purchaseLineTotal(line: LineAmounts): number {
  const quantity = Number(line.qty)
  const grossUnitCost = Number(line.unit_cost)
  const discountPercent = Number(line.line_discount)

  if (![quantity, grossUnitCost, discountPercent].every(Number.isFinite)) return 0

  const total = quantity * grossUnitCost * (1 - discountPercent / 100)
  return Math.round((total + Number.EPSILON) * 100) / 100
}
