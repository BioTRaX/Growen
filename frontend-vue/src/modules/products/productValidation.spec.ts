// NG-HEADER: Nombre de archivo: productValidation.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/productValidation.spec.ts
// NG-HEADER: Descripción: Pruebas de precios y stock antes de mutar Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { describe, expect, it } from 'vitest'
import { isValidStock, parsePositivePrice } from './productValidation'

describe('validaciones de Productos', () => {
  it('acepta decimales con coma y limita a dos posiciones', () => {
    expect(parsePositivePrice('123,456')).toBe(123.46)
  })

  it('rechaza precios vacíos, negativos o no numéricos', () => {
    expect(parsePositivePrice('')).toBeNull()
    expect(parsePositivePrice('-1')).toBeNull()
    expect(parsePositivePrice('precio')).toBeNull()
  })

  it('acepta stock con hasta dos decimales dentro del rango del backend', () => {
    expect(isValidStock(0)).toBe(true)
    expect(isValidStock(10.25)).toBe(true)
    expect(isValidStock(1_000_000_000)).toBe(true)
    expect(isValidStock(1.234)).toBe(false)
    expect(isValidStock(-1)).toBe(false)
  })
})
