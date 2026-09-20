// NG-HEADER: Nombre de archivo: productDescription.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/productDescription.ts
// NG-HEADER: Descripción: Utilidades puras para formateo y manipulación de descripciones HTML de productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md

export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

export function formatDescriptionToHtml(val: string): string {
  const trimmed = val.trim()
  if (!trimmed) return ''
  if (/<[a-z][\s\S]*>/i.test(trimmed)) {
    return trimmed
  }
  const paragraphs = trimmed
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
  return paragraphs
    .map((p) => `<p>${escapeHtml(p).replace(/\n/g, '<br>')}</p>`)
    .join('')
}
