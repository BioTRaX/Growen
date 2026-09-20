// NG-HEADER: Nombre de archivo: priceComparison.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/market/priceComparison.spec.ts
// NG-HEADER: Descripción: Pruebas de los umbrales visuales del precio de Mercado.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { describe, expect, it } from 'vitest'

import { classifyPriceDelta } from './priceComparison'

describe('classifyPriceDelta', () => {
  it.each([
    [-20, 'much_cheaper'],
    [-19.99, 'very_cheaper'],
    [-15, 'very_cheaper'],
    [-14.99, 'moderately_cheaper'],
    [-10, 'moderately_cheaper'],
    [-9.99, 'slightly_cheaper'],
    [-5.01, 'slightly_cheaper'],
    [-5, 'aligned'],
    [5, 'aligned'],
    [5.01, 'slightly_expensive'],
    [9.99, 'slightly_expensive'],
    [10, 'moderately_expensive'],
    [14.99, 'moderately_expensive'],
    [15, 'very_expensive'],
  ] as const)('clasifica %s como %s', (delta, expected) => {
    expect(classifyPriceDelta(delta)).toBe(expected)
  })

  it('no compara valores ausentes o no finitos', () => {
    expect(classifyPriceDelta(null)).toBe('unavailable')
    expect(classifyPriceDelta(Number.NaN)).toBe('unavailable')
  })
})
