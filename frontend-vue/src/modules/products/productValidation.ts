// NG-HEADER: Nombre de archivo: productValidation.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/productValidation.ts
// NG-HEADER: Descripción: Validaciones puras para mutaciones de Productos Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md

export function parsePositivePrice(value: string): number | null {
  const parsed = Number(value.trim().replace(',', '.'))
  return Number.isFinite(parsed) && parsed > 0 ? Number(parsed.toFixed(2)) : null
}

export function isValidStock(value: number): boolean {
  return Number.isFinite(value) && value >= 0 && value <= 1_000_000_000 && Math.abs(value * 100 - Math.round(value * 100)) < 1e-8
}
