// NG-HEADER: Nombre de archivo: types.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/types.ts
// NG-HEADER: Descripción: Contratos TypeScript del módulo Vue de Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md

export type ProductTypeFilter = 'all' | 'canonical' | 'supplier'
export type ProductStockFilter = '' | 'gt:0' | 'eq:0'
export type ProductRecentFilter = '' | 1 | 7 | 30

export interface ProductListFilters {
  q: string
  supplier_id: number | null
  category_id: number | null
  stock: ProductStockFilter
  recent: ProductRecentFilter
  type: ProductTypeFilter
  page: number
  page_size: number
}

export interface ProductTag {
  id: number
  name: string
}

export interface ProductListItem {
  product_id: number
  name: string
  preferred_name: string | null
  supplier: { id: number; slug: string; name: string }
  supplier_item_id: number | null
  precio_compra: number | null
  precio_venta: number | null
  canonical_sale_price: number | null
  compra_minima: number | null
  category_id: number | null
  subcategory_id: number | null
  category_path: string | null
  stock: number
  updated_at: string | null
  canonical_product_id: number | null
  canonical_sku: string | null
  canonical_name: string | null
  first_variant_sku: string | null
  tags: ProductTag[]
  image_url: string | null
  images_count: number
  primary_image_id: number | null
  technical_specs?: unknown
  usage_instructions?: unknown
}

export interface ProductListResponse {
  page: number
  page_size: number
  total: number
  items: ProductListItem[]
}

export interface ProductCategory {
  id: number
  name: string
  parent_id: number | null
  kind: 'category' | 'subcategory'
  path: string
}

export interface ProductSupplier {
  id: number
  name: string
  slug: string
}

export interface ProductDetail {
  id: number
  title: string
  preferred_title: string | null
  stock: number
  sku_root: string | null
  category_path: string | null
  category_id: number | null
  subcategory_id: number | null
  description_html: string | null
  canonical_product_id: number | null
  canonical_sku: string | null
  canonical_name: string | null
  canonical_sale_price: number | null
  supplier_sale_price: number | null
  sale_price: number | null
  images: Array<{ id: number; url: string; alt_text: string | null; is_primary: boolean }>
  tags: ProductTag[]
}

export interface ProductPurchaseHistoryItem {
  purchase_id: number
  purchase_line_id: number
  date: string
  supplier: { id: number; name: string }
  remito_number: string
  supplier_sku: string | null
  supplier_title: string | null
  quantity: number
  gross_unit_cost: number
  discount_pct: number
  net_unit_cost: number
  attachment_url: string | null
}

export interface ProductStockMovement {
  type: string
  source_id: number | null
  delta: number
  balance_after: number
  created_at: string
}

export interface ProductPurchaseHistory {
  product_id: number
  product_name: string
  items: ProductPurchaseHistoryItem[]
  movements: ProductStockMovement[]
}

export interface ProductCreatePayload {
  title: string
  category_id: number | null
  subcategory_id: number | null
  tag_names: string[]
  initial_stock: number
}

export interface CreatedProduct {
  id: number
  title: string
  sku_root: string
  slug: string
  stock: number
  category_id: number | null
  subcategory_id: number | null
  status: string | null
}

export interface SupplierItemCreatePayload {
  supplier_product_id: string
  title: string
  product_id: number
  purchase_price: number
  sale_price: number
}

export interface ProductDeleteResult {
  requested: number[]
  deleted: number[]
  blocked_stock: number[]
  blocked_refs: number[]
}

export type CanonicalBatchJobStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'PARTIAL' | 'FAILED'
export type CanonicalBatchItemStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'

export interface MassCanonicalDraftRow {
  sourceProductId: number
  internalProductId: number
  sourceName: string
  supplierName: string
  name: string
  brand: string
  categoryId: number | null
  subcategoryId: number | null
  tagNames: string[]
  previewSku: string | null
}

export interface MassCanonicalDraft {
  version: 3
  userId: number
  clientRequestId: string
  step: number
  updatedAt: string
  expiresAt: string
  jobId: string | null
  commonTagNames: string[]
  rows: MassCanonicalDraftRow[]
}

export interface CanonicalSkuPreviewResponse {
  items: Array<{ position: number; sku: string; definitive: false }>
}

export interface CanonicalBatchCreateResponse {
  status: CanonicalBatchJobStatus
  job_id: string
  message: string
  total_items: number
  status_url: string
}

export interface CanonicalBatchJobItem {
  position: number
  source_product_id: number | null
  status: CanonicalBatchItemStatus
  canonical_product_id: number | null
  sku_custom: string | null
  error: { code: string; message: string } | null
}

export interface CanonicalBatchJobResponse {
  job_id: string
  status: CanonicalBatchJobStatus
  total_items: number
  processed_items: number
  success_count: number
  error_count: number
  error_message: string | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
  items: CanonicalBatchJobItem[]
}
