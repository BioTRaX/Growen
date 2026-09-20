// NG-HEADER: Nombre de archivo: purchaseValidation.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/purchases/purchaseValidation.spec.ts
// NG-HEADER: Descripción: Pruebas del feedback de validación de compras.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { describe, expect, it } from 'vitest'
import type { PurchaseValidationResult } from '../../services/purchases'
import { validationFeedback } from './purchaseValidation'

function result(overrides: Partial<PurchaseValidationResult> = {}): PurchaseValidationResult {
  return {
    status: 'ok', unmatched: 0, lines: 1, linked: 0, missing_skus: [], errors: [], warnings: [], ...overrides,
  }
}

describe('validationFeedback', () => {
  it('prioriza errores bloqueantes aunque también existan advertencias', () => {
    const feedback = validationFeedback(result({
      errors: [{ line_id: 7, errors: ['La bonificación debe estar entre 0 y 100'] }],
      warnings: [{ line_id: 8, code: 'new_product', message: 'Se creará al confirmar' }],
    }))

    expect(feedback.message).toBe('')
    expect(feedback.error).toContain('1 línea(s)')
    expect(feedback.error).toContain('bonificación')
  })

  it('confirma la validación y comunica las altas pendientes', () => {
    const feedback = validationFeedback(result({
      warnings: [{ line_id: 8, code: 'new_product', message: 'Se creará al confirmar' }],
    }))

    expect(feedback.error).toBe('')
    expect(feedback.message).toBe('Compra validada. 1 producto(s) se crearán al confirmar.')
  })
})
