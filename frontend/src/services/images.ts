// NG-HEADER: Nombre de archivo: images.ts
// NG-HEADER: Ubicación: frontend/src/services/images.ts
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import http from './http'

export interface ImageItem {
  id: number
  url: string
  path?: string
  alt_text?: string
  title_text?: string
  is_primary?: boolean
  locked?: boolean
  active?: boolean
  sort_order?: number
}

export async function uploadProductImage(productId: number, file: File): Promise<{ image_id: number; url: string }> {
  const form = new FormData()
  form.append('file', file)
  const r = await http.post(`/products/${productId}/images/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return r.data
}

export async function addImageFromUrl(productId: number, url: string): Promise<{ image_id: number; url: string }> {
  const r = await http.post(`/products/${productId}/images/from-url`, { url })
  return r.data
}

export async function setPrimary(productId: number, imageId: number) {
  await http.post(`/products/${productId}/images/${imageId}/set-primary`)
}

export async function lockImage(productId: number, imageId: number) {
  await http.post(`/products/${productId}/images/${imageId}/lock`)
}

export async function deleteImage(productId: number, imageId: number) {
  await http.delete(`/products/${productId}/images/${imageId}`)
}

export async function reorderImages(productId: number, imageIds: number[]) {
  await http.post(`/products/${productId}/images/reorder`, { image_ids: imageIds })
}

export async function removeBg(productId: number, imageId: number) {
  await http.post(`/products/${productId}/images/${imageId}/process/remove-bg`)
}

export async function watermark(productId: number, imageId: number, position: 'br' | 'bl' | 'tr' | 'tl' = 'br', opacity = 0.18) {
  await http.post(`/products/${productId}/images/${imageId}/process/watermark`, { position, opacity })
}

export async function refreshSEO(productId: number, imageId: number): Promise<{ alt: string; title: string }> {
  const r = await http.post(`/products/${productId}/images/${imageId}/seo/refresh`)
  return r.data
}

export async function pushTN(productId: number) {
  await http.post(`/products/${productId}/images/push/tiendanube`)
}

export async function pushTNBulk(productIds: number[]) {
  const r = await http.post(`/products/images/push/tiendanube/bulk`, { product_ids: productIds })
  return r.data as { results: { product_id: number; remote_media_id: string }[] }
}

