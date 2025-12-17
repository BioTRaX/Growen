// NG-HEADER: Nombre de archivo: market.ts
// NG-HEADER: Ubicación: frontend/src/services/market.ts
// NG-HEADER: Descripción: Servicios HTTP para funcionalidad de Mercado (comparación de precios)
// NG-HEADER: Lineamientos: Ver AGENTS.md

import http from './http'

/**
 * Item de producto en la lista de mercado
 */
export interface MarketProductItem {
  product_id: number
  internal_product_id: number | null
  preferred_name: string
  product_sku: string
  sale_price: number | null
  market_price_reference: number | null
  market_price_min: number | null
  market_price_max: number | null
  last_market_update: string | null
  has_active_alerts: boolean
  active_alerts_count: number
  category_id: number | null
  category_name: string | null
  supplier_id: number | null
  supplier_name: string | null
}

/**
 * Respuesta al listar productos de mercado
 */
export interface MarketProductsResponse {
  items: MarketProductItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

/**
 * Fuente descubierta automáticamente
 */
export interface DiscoveredSource {
  url: string
  title: string
  snippet: string
}

/**
 * Respuesta al descubrir fuentes automáticamente
 */
export interface DiscoverSourcesResponse {
  success: boolean
  query: string
  total_results: number
  valid_sources: number
  sources: DiscoveredSource[]
  error: string | null
}

/**
 * Request para agregar fuente desde sugerencia
 */
export interface AddSuggestedSourceRequest {
  url: string
  source_name?: string
  validate_price?: boolean
  source_type?: 'static' | 'dynamic'
  is_mandatory?: boolean
}

/**
 * Respuesta al agregar fuente desde sugerencia
 */
export interface AddSuggestedSourceResponse {
  success: boolean
  source_id: number | null
  message: string
  validation_result: {
    is_valid: boolean
    reason: string
  } | null
}

/**
 * Resultado individual de agregar fuente en batch
 */
export interface BatchSourceResult {
  url: string
  success: boolean
  source_id: number | null
  message: string
  validation_result: {
    is_valid: boolean
    reason: string
  } | null
}

/**
 * Respuesta al agregar múltiples fuentes
 */
export interface BatchAddSourcesResponse {
  total_requested: number
  successful: number
  failed: number
  results: BatchSourceResult[]
}

/**
 * Payload para agregar múltiples fuentes
 */
export interface BatchAddSourcesPayload {
  sources: AddSuggestedSourceRequest[]
  stop_on_error?: boolean
}

/**
 * Fuente de precio de mercado
 */
export interface MarketSource {
  id: number
  product_id: number
  source_name: string
  url: string
  last_price: number | null
  last_checked_at: string | null
  is_mandatory: boolean
  source_type: string | null
  currency: string | null
  created_at: string
  updated_at: string
}

/**
 * Respuesta al obtener fuentes de un producto
 */
export interface ProductSourcesResponse {
  product_id: number
  product_name: string
  sale_price: number | null
  market_price_reference: number | null
  market_price_min: number | null
  market_price_max: number | null
  mandatory: MarketSource[]
  additional: MarketSource[]
}

/**
 * Respuesta al actualizar precios de mercado
 */
export interface UpdateMarketPricesResponse {
  product_id: number
  updated_sources: {
    name: string
    old_price: number | null
    new_price: number | null
    success: boolean
    error?: string
  }[]
  market_price_min: number | null
  market_price_max: number | null
  market_price_reference: number | null
  errors: string[]
}

/**
 * Payload para agregar una fuente
 */
export interface AddSourcePayload {
  name: string
  url: string
  is_mandatory: boolean
}

/**
 * Lista productos del mercado con filtros opcionales
 * 
 * @param params Parámetros de búsqueda y filtrado
 * @returns Lista paginada de productos
 */
export async function listMarketProducts(params?: {
  q?: string
  category_id?: number
  supplier_id?: number
  page?: number
  page_size?: number
}): Promise<MarketProductsResponse> {
  const queryParams = new URLSearchParams()
  
  if (params?.q) queryParams.set('q', params.q)
  if (params?.category_id) queryParams.set('category_id', String(params.category_id))
  if (params?.supplier_id) queryParams.set('supplier_id', String(params.supplier_id))
  if (params?.page) queryParams.set('page', String(params.page))
  if (params?.page_size) queryParams.set('page_size', String(params.page_size))
  
  const url = `/market/products${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  const response = await http.get(url)
  return response.data
}

/**
 * Obtiene las fuentes de precio configuradas para un producto
 * 
 * @param productId ID del producto
 * @returns Fuentes obligatorias y adicionales
 */
export async function getProductSources(productId: number): Promise<ProductSourcesResponse> {
  const response = await http.get(`/market/products/${productId}/sources`)
  return response.data
}

/**
 * Dispara la actualización de precios de mercado para un producto
 * 
 * El backend procesa esto de forma asíncrona mediante un worker (Dramatiq).
 * Esta función retorna inmediatamente con status 202 Accepted.
 * La UI debe mostrar loading y refrescar datos periódicamente.
 * 
 * @param productId ID del producto
 * @param options Opciones de actualización (no soportadas por backend actualmente)
 * @returns Respuesta con job_id para tracking
 */
export async function updateProductMarketPrices(
  productId: number,
  options?: {
    force?: boolean
    sources?: string[]
    include_web?: boolean
  }
): Promise<{ status: string; message: string; product_id: number; job_id?: string }> {
  const response = await http.post(`/market/products/${productId}/refresh-market`)
  return response.data
}

/**
 * Agrega una nueva fuente de precio para un producto
 * 
 * @param productId ID del producto
 * @param payload Datos de la fuente a agregar
 * @returns Fuente creada
 */
export async function addProductSource(
  productId: number,
  payload: AddSourcePayload
): Promise<MarketSource> {
  const response = await http.post(`/market/products/${productId}/sources`, {
    source_name: payload.name,
    url: payload.url,
    is_mandatory: payload.is_mandatory,
    currency: 'ARS',
    source_type: 'static',
  })
  
  return {
    id: response.data.id,
    product_id: response.data.product_id,
    source_name: response.data.source_name,
    url: response.data.url,
    last_price: response.data.last_price,
    last_checked_at: response.data.last_checked_at,
    is_mandatory: response.data.is_mandatory,
    source_type: response.data.source_type ?? 'static',
    currency: response.data.currency ?? 'ARS',
    created_at: response.data.created_at,
    updated_at: response.data.updated_at ?? response.data.created_at,
  }
}

/**
 * Elimina una fuente de precio
 * 
 * @param productId ID del producto
 * @param sourceId ID de la fuente a eliminar
 */
export async function deleteProductSource(
  productId: number,
  sourceId: number
): Promise<void> {
  await http.delete(`/market/sources/${sourceId}`)
}

/**
 * Valida una URL de fuente
 * 
 * @param url URL a validar
 * @returns true si es válida
 */
export function validateSourceUrl(url: string): { valid: boolean; error?: string } {
  try {
    const parsed = new URL(url)
    
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return { valid: false, error: 'La URL debe usar HTTP o HTTPS' }
    }
    
    if (!parsed.hostname) {
      return { valid: false, error: 'La URL debe tener un dominio válido' }
    }
    
    return { valid: true }
  } catch (e) {
    return { valid: false, error: 'URL inválida' }
  }
}

/**
 * Actualiza el precio de venta de un producto
 * 
 * @param productId ID del producto
 * @param salePrice Nuevo precio de venta
 * @returns Producto actualizado
 */
export async function updateProductSalePrice(
  productId: number,
  salePrice: number
): Promise<{ product_id: number; sale_price: number }> {
  const response = await http.patch(`/market/products/${productId}/sale-price`, {
    sale_price: salePrice
  })
  return response.data
}

/**
 * Resultado individual de actualización masiva
 */
export interface BatchRefreshMarketItem {
  product_id: number
  status: 'enqueued' | 'not_found' | 'error'
  message: string
  job_id?: string | null
}

/**
 * Respuesta a actualización masiva de precios de mercado
 */
export interface BatchRefreshMarketResponse {
  total_requested: number
  enqueued: number
  not_found: number
  errors: number
  results: BatchRefreshMarketItem[]
}

/**
 * Inicia actualización masiva de precios de mercado para múltiples productos
 * 
 * El proceso encola tareas de scraping en segundo plano para cada producto.
 * Retorna inmediatamente con status 202 Accepted y resumen de resultados.
 * 
 * @param productIds Lista de IDs de productos a actualizar (máximo 100)
 * @returns Resumen de resultados con estado por producto
 */
export async function batchUpdateMarketPrices(
  productIds: number[]
): Promise<BatchRefreshMarketResponse> {
  if (productIds.length === 0) {
    throw new Error('Debe proporcionar al menos un producto')
  }
  if (productIds.length > 100) {
    throw new Error('Máximo 100 productos por request')
  }
  
  const response = await http.post('/market/products/batch-refresh', {
    product_ids: productIds
  })
  return response.data
}

/**
 * Actualiza el valor de mercado de referencia de un producto
 * 
 * @param productId ID del producto
 * @param marketReference Nuevo valor de mercado de referencia
 * @returns Producto actualizado
 */
export async function updateMarketReference(
  productId: number,
  marketReference: number
): Promise<{ id: number; market_price_reference: number }> {
  const response = await http.patch(`/market/products/${productId}/market-reference`, {
    market_price_reference: marketReference
  })
  return {
    id: response.data.product_id,
    market_price_reference: response.data.market_price_reference
  }
}

/**
 * Valida un precio (debe ser número positivo)
 * 
 * @param value Valor a validar
 * @returns Objeto con validación y mensaje de error si aplica
 */
export function validatePrice(value: string | number): { valid: boolean; error?: string } {
  const numValue = typeof value === 'string' ? parseFloat(value) : value
  
  if (isNaN(numValue)) {
    return { valid: false, error: 'Debe ingresar un número válido' }
  }
  
  if (numValue <= 0) {
    return { valid: false, error: 'El precio debe ser mayor a cero' }
  }
  
  if (numValue > 999999999) {
    return { valid: false, error: 'El precio es demasiado alto' }
  }
  
  return { valid: true }
}

/**
 * Descubre automáticamente fuentes de precio para un producto usando MCP Web Search
 * 
 * @param productId ID del producto
 * @param maxResults Máximo de resultados a solicitar al buscador (5-30)
 * @returns Respuesta con fuentes descubiertas
 */
export async function discoverProductSources(
  productId: number,
  maxResults: number = 15
): Promise<DiscoverSourcesResponse> {
  const response = await http.post(`/market/products/${productId}/discover-sources?max_results=${maxResults}`)
  return response.data
}

/**
 * Agrega una fuente de precio desde una sugerencia con validación automática
 * 
 * @param productId ID del producto
 * @param payload Datos de la fuente a agregar
 * @returns Respuesta con resultado de la adición
 */
export async function addSourceFromSuggestion(
  productId: number,
  payload: AddSuggestedSourceRequest
): Promise<AddSuggestedSourceResponse> {
  const response = await http.post(`/market/products/${productId}/sources/from-suggestion`, payload)
  return response.data
}

/**
 * Agrega múltiples fuentes de precio desde sugerencias con validación en paralelo
 * 
 * @param productId ID del producto
 * @param payload Datos de las fuentes a agregar
 * @returns Respuesta con resumen de éxitos y fallos
 */
export async function batchAddSourcesFromSuggestions(
  productId: number,
  payload: BatchAddSourcesPayload
): Promise<BatchAddSourcesResponse> {
  const response = await http.post(`/market/products/${productId}/sources/batch-from-suggestions`, payload)
  return response.data
}

/**
 * Request para actualizar una fuente de precio
 */
export interface UpdateMarketSourceRequest {
  source_name?: string
  url?: string
  last_price?: number
  is_mandatory?: boolean
}

/**
 * Actualiza los datos de una fuente de precio
 * 
 * @param sourceId ID de la fuente
 * @param payload Datos a actualizar (partial update)
 * @returns Fuente actualizada
 */
export async function updateMarketSource(
  sourceId: number,
  payload: UpdateMarketSourceRequest
): Promise<any> {
  const response = await http.patch(`/market/sources/${sourceId}`, payload)
  return response.data
}

/**
 * Elimina una fuente de precio
 * 
 * @param sourceId ID de la fuente a eliminar
 */
export async function deleteMarketSource(sourceId: number): Promise<void> {
  await http.delete(`/market/sources/${sourceId}`)
}


