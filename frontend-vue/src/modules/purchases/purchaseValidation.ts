// NG-HEADER: Nombre de archivo: purchaseValidation.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/purchases/purchaseValidation.ts
// NG-HEADER: Descripción: Presentación del resultado de validación de una compra.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import type { PurchaseValidationResult } from '../../services/purchases'

export interface ValidationFeedback {
  error: string
  message: string
}

export function validationFeedback(result: PurchaseValidationResult): ValidationFeedback {
  if (result.errors.length) {
    const reasons = [...new Set(result.errors.flatMap((issue) => issue.errors))]
    const reasonText = reasons.length ? ` ${reasons.join('. ')}.` : ''
    return {
      error: `No se pudo validar: ${result.errors.length} línea(s) tienen datos inválidos.${reasonText} Corregí los campos marcados y volvé a validar.`,
      message: '',
    }
  }

  return {
    error: '',
    message: result.warnings.length
      ? `Compra validada. ${result.warnings.length} producto(s) se crearán al confirmar.`
      : 'Compra validada.',
  }
}
