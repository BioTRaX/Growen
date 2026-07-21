// NG-HEADER: Nombre de archivo: products.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/api/products.ts
// NG-HEADER: Descripción: Cliente HTTP tipado del módulo Vue de Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { http } from '../../../services/http'
import type {
  ProductCategory,
  CreatedProduct,
  ProductCreatePayload,
  ProductDeleteResult,
  ProductDetail,
  ProductListFilters,
  ProductListResponse,
  ProductPurchaseHistory,
  ProductSupplier,
  SupplierItemCreatePayload,
  CanonicalBatchCreateResponse,
  CanonicalBatchJobResponse,
  CanonicalSkuPreviewResponse,
  MassCanonicalDraftRow,
  ProductTag,
} from '../types'

export function toProductApiParams(filters: ProductListFilters): Record<string, string | number> {
  const params: Record<string, string | number> = {
    page: filters.page,
    page_size: filters.page_size,
    type: filters.type,
  }
  if (filters.q.trim()) params.q = filters.q.trim()
  if (filters.supplier_id) params.supplier_id = filters.supplier_id
  if (filters.category_id) params.category_id = filters.category_id
  if (filters.stock) params.stock = filters.stock
  if (filters.recent) params.created_since_days = filters.recent
  return params
}

export async function listProducts(filters: ProductListFilters, signal?: AbortSignal): Promise<ProductListResponse> {
  return (await http.get<ProductListResponse>('/products', { params: toProductApiParams(filters), signal })).data
}

export async function listProductCategories(kind?: ProductCategory['kind']): Promise<ProductCategory[]> {
  return (await http.get<ProductCategory[]>('/categories', { params: kind ? { kind } : undefined })).data
}

export async function createProductCategory(name: string, kind: ProductCategory['kind']): Promise<ProductCategory> {
  return (await http.post<ProductCategory>('/categories', {
    name: name.trim(),
    kind,
  })).data
}

export async function listProductTags(q = '', signal?: AbortSignal): Promise<ProductTag[]> {
  return (await http.get<ProductTag[]>('/tags', { params: q.trim() ? { q: q.trim() } : undefined, signal })).data
}

export async function createProductTag(name: string): Promise<ProductTag> {
  return (await http.post<ProductTag>('/tags', { name: name.trim() })).data
}

export async function assignProductTags(productId: number, tagNames: string[]): Promise<void> {
  await http.post(`/tags/products/${productId}/tags`, { tag_names: tagNames })
}

export async function removeProductTag(productId: number, tagId: number): Promise<void> {
  await http.delete(`/tags/products/${productId}/tags/${tagId}`)
}

export async function bulkAssignProductTags(productIds: number[], tagNames: string[]): Promise<void> {
  await http.post('/tags/products/bulk-tags', { product_ids: productIds, tag_names: tagNames })
}

export async function listProductSuppliers(): Promise<ProductSupplier[]> {
  return (await http.get<ProductSupplier[]>('/suppliers/search', { params: { q: '', limit: 50 } })).data
}

export async function getProduct(id: number): Promise<ProductDetail> {
  return (await http.get<ProductDetail>(`/products/${id}`)).data
}

export async function getProductHistory(id: number): Promise<ProductPurchaseHistory> {
  return (await http.get<ProductPurchaseHistory>(`/products/${id}/purchase-history`)).data
}

export async function createProduct(payload: ProductCreatePayload): Promise<CreatedProduct> {
  return (await http.post<CreatedProduct>('/products', payload)).data
}

export async function createSupplierItem(supplierId: number, payload: SupplierItemCreatePayload): Promise<{ id: number }> {
  return (await http.post<{ id: number }>(`/suppliers/${supplierId}/items`, payload)).data
}

export async function updateProductStock(productId: number, stock: number, expectedStock?: number): Promise<{ product_id: number; stock: number }> {
  return (await http.patch<{ product_id: number; stock: number }>(`/products/${productId}/stock`, {
    stock,
    ...(expectedStock === undefined ? {} : { expected_stock: expectedStock }),
  })).data
}

export async function updateCanonicalSalePrice(canonicalProductId: number, salePrice: number): Promise<{ id: number; sale_price: number | null }> {
  return (await http.patch<{ id: number; sale_price: number | null }>(`/products-ex/products/${canonicalProductId}/sale-price`, { sale_price: salePrice })).data
}

export async function updateSupplierSalePrice(supplierItemId: number, salePrice: number): Promise<{ id: number; sale_price: number | null }> {
  return (await http.patch<{ id: number; sale_price: number | null }>(`/products-ex/supplier-items/${supplierItemId}/sale-price`, { sale_price: salePrice })).data
}

export async function updateSupplierBuyPrice(supplierItemId: number, buyPrice: number): Promise<{ id: number; buy_price: number | null }> {
  return (await http.patch<{ id: number; buy_price: number | null }>(`/products-ex/supplier-items/${supplierItemId}/buy-price`, { buy_price: buyPrice })).data
}

export async function enrichProducts(ids: number[]): Promise<void> {
  await http.post('/products/enrich-multiple', { ids })
}

export async function fillMissingSalePrices(supplierId: number | null): Promise<{ updated: number }> {
  return (await http.post<{ updated: number }>('/products-ex/supplier-items/fill-missing-sale', { supplier_id: supplierId })).data
}

export async function deleteProducts(ids: number[]): Promise<ProductDeleteResult> {
  return (await http.delete<ProductDeleteResult>('/catalog/products', { data: { ids } })).data
}

export async function previewCanonicalSkus(rows: MassCanonicalDraftRow[]): Promise<CanonicalSkuPreviewResponse> {
  return (await http.post<CanonicalSkuPreviewResponse>('/canonical-products/sku-preview', {
    items: rows.map((row) => ({ category_id: row.categoryId, subcategory_id: row.subcategoryId })),
  })).data
}

export async function createCanonicalBatch(
  clientRequestId: string,
  rows: MassCanonicalDraftRow[],
): Promise<CanonicalBatchCreateResponse> {
  return (await http.post<CanonicalBatchCreateResponse>('/canonical-products/batch-job', {
    client_request_id: clientRequestId,
    items: rows.map((row) => ({
      name: row.name.trim(),
      brand: row.brand.trim() || null,
      category_id: row.categoryId,
      subcategory_id: row.subcategoryId,
      tag_names: row.tagNames,
      source_product_id: row.sourceProductId,
    })),
  })).data
}

export async function getCanonicalBatchJob(jobId: string): Promise<CanonicalBatchJobResponse> {
  return (await http.get<CanonicalBatchJobResponse>(`/canonical-products/batch-jobs/${jobId}`)).data
}
