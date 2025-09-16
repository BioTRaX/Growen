// NG-HEADER: Nombre de archivo: corrStore.ts
// NG-HEADER: Ubicación: frontend/src/lib/corrStore.ts
// NG-HEADER: Descripción: Almacén simple en memoria para registrar correlaciones de requests/responses
// NG-HEADER: Lineamientos: Ver AGENTS.md

export type CorrItem = {
  ts: string
  method: string
  url: string
  status: number
  ms: number
  cid?: string
}

const MAX_ITEMS = 300
let items: CorrItem[] = []

export function diagAdd(entry: CorrItem) {
  items.unshift(entry)
  if (items.length > MAX_ITEMS) items = items.slice(0, MAX_ITEMS)
}

export function diagList(): CorrItem[] {
  return items
}

export function diagClear() {
  items = []
}
