// NG-HEADER: Nombre de archivo: format.ts
// NG-HEADER: Ubicación: frontend/src/lib/format.ts
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
export function formatARS(n: number | null | undefined): string {
  if (n == null) return ''
  try {
    return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n)
  } catch {
    return `$ ${n.toFixed(2)}`
  }
}

export function parseDecimalInput(s: string): number | null {
  if (!s) return null
  const v = s.replace(/,/g, '.')
  const num = Number(v)
  if (!isFinite(num) || num <= 0) return null
  return Math.round(num * 100) / 100
}
