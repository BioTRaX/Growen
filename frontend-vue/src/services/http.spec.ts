// NG-HEADER: Nombre de archivo: http.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/http.spec.ts
// NG-HEADER: Descripción: Pruebas de normalización de errores HTTP del frontend Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { describe, expect, it } from 'vitest'
import { classifyHttpError, getHttpErrorMessage, normalizeApiBase } from './http'

describe('getHttpErrorMessage', () => {
  it('extrae mensajes FastAPI simples y estructurados', () => {
    expect(getHttpErrorMessage({ response: { data: { detail: 'Producto no encontrado' } } })).toBe('Producto no encontrado')
    expect(getHttpErrorMessage({ response: { data: { detail: { message: 'Filtro inválido' } } } })).toBe('Filtro inválido')
  })

  it('ignora cancelaciones y usa fallback para errores desconocidos', () => {
    expect(getHttpErrorMessage({ code: 'ERR_CANCELED' })).toBe('')
    expect(getHttpErrorMessage({}, 'Error controlado')).toBe('Error controlado')
  })

  it('acepta bases relativas y conserva el fallback /api', () => {
    expect(normalizeApiBase('/api/')).toBe('/api')
    expect(normalizeApiBase('https://api.example.test/')).toBe('https://api.example.test')
    expect(normalizeApiBase('')).toBe('/api')
  })

  it('clasifica estados relevantes para la UI', () => {
    expect(classifyHttpError({ response: { status: 401 } })).toBe('unauthorized')
    expect(classifyHttpError({ response: { status: 403 } })).toBe('forbidden')
    expect(classifyHttpError({ response: { status: 409 } })).toBe('conflict')
    expect(classifyHttpError({ response: { status: 422 } })).toBe('validation')
  })
})
