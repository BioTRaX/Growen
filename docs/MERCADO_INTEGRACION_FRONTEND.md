<!-- NG-HEADER: Nombre de archivo: MERCADO_INTEGRACION_FRONTEND.md -->
<!-- NG-HEADER: Ubicación: docs/MERCADO_INTEGRACION_FRONTEND.md -->
<!-- NG-HEADER: Descripción: Guía de integración frontend-backend del módulo Mercado -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Integración Frontend-Backend - Módulo Mercado

## Resumen

Este documento describe la integración entre el frontend (React + TypeScript) y el backend (FastAPI) para el módulo Mercado, específicamente para la funcionalidad de listado de productos con precios.

**Estado**: ✅ Completado (2025-11-11)

**Endpoint integrado**: `GET /market/products`

---

## 1. Arquitectura de Integración

### 1.1 Flujo de Datos

```
Usuario → Market.tsx → market.ts → HTTP Client → Backend API → Database
                ↓                                      ↓
         UI actualizada ← Transformación ← JSON Response
```

### 1.2 Componentes Involucrados

#### Frontend
- **Página**: `frontend/src/pages/Market.tsx`
- **Servicio**: `frontend/src/services/market.ts`
- **HTTP Client**: `frontend/src/services/http.ts` (wrapper de fetch/axios)

#### Backend
- **Router**: `services/routers/market.py`
- **API Principal**: `services/api.py`
- **Modelos ORM**: `db/models.py` (CanonicalProduct, Category, ProductEquivalence)

---

## 2. Implementación Frontend

### 2.1 Interfaces TypeScript

Definidas en `frontend/src/services/market.ts`:

```typescript
/**
 * Item de producto en la lista de mercado
 */
export interface MarketProductItem {
  product_id: number
  preferred_name: string
  sale_price: number | null
  market_price_reference: number | null
  market_price_min: number | null
  market_price_max: number | null
  last_market_update: string | null
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
```

**Mapeo con backend**: Las interfaces TypeScript reflejan exactamente los schemas Pydantic del backend (`MarketProductItem`, `MarketProductsResponse`).

### 2.2 Función de Servicio

```typescript
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
```

**Características**:
- Construcción dinámica de query params (solo incluye los definidos)
- Conversión de tipos (number → string para URLSearchParams)
- Retorna tipado fuerte (`Promise<MarketProductsResponse>`)
- Manejo de errores delegado al HTTP client

### 2.3 Uso en Componente React

En `frontend/src/pages/Market.tsx`:

```typescript
async function loadProducts() {
  setLoading(true)
  try {
    const response = await listMarketProducts({
      q: q || undefined,
      category_id: categoryId ? parseInt(categoryId) : undefined,
      supplier_id: supplierId ? parseInt(supplierId) : undefined,
      page,
      page_size: pageSize,
    })
    
    setItems(response.items)
    setTotal(response.total)
    setTotalPages(response.pages)
  } catch (error: any) {
    push({ 
      kind: 'error', 
      message: error?.message || 'Error cargando productos del mercado' 
    })
    setItems([])
    setTotal(0)
    setTotalPages(0)
  } finally {
    setLoading(false)
  }
}
```

**Características**:
- Estados de carga (`loading: boolean`)
- Manejo de errores con toast notification
- Reset de datos en caso de error
- Conversión de strings vacíos a `undefined` (filtros opcionales)

### 2.4 Debounce de Filtros

```typescript
useEffect(() => {
  const t = setTimeout(() => {
    loadProducts()
  }, 300)
  return () => clearTimeout(t)
}, [q, supplierId, categoryId, page])
```

**Beneficios**:
- Evita llamadas excesivas al escribir en búsqueda
- 300ms de espera antes de ejecutar
- Limpieza automática del timeout al desmontar

---

## 3. Implementación Backend

### 3.1 Schemas Pydantic

Definidos en `services/routers/market.py`:

```python
class MarketProductItem(BaseModel):
    product_id: int
    preferred_name: str
    sale_price: Optional[float] = None
    market_price_reference: Optional[float] = None
    market_price_min: Optional[float] = None
    market_price_max: Optional[float] = None
    last_market_update: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None

class MarketProductsResponse(BaseModel):
    items: list[MarketProductItem]
    total: int
    page: int
    page_size: int
    pages: int
```

**Notas**:
- `Optional[float]` para precios (pueden ser NULL en DB)
- `Optional[str]` para last_market_update (ISO 8601 timestamp o NULL)
- `preferred_name` es computado (no existe en DB)

### 3.2 Endpoint

```python
@router.get(
    "/products", 
    response_model=MarketProductsResponse, 
    dependencies=[Depends(require_roles("colaborador", "admin"))]
)
async def list_market_products(
    q: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    supplier_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session)
):
    # Query base con eager loading
    query = select(CanonicalProduct).options(
        selectinload(CanonicalProduct.category),
        selectinload(CanonicalProduct.subcategory)
    )
    
    # Filtros dinámicos...
    # Paginación...
    # Construcción de items...
    
    return MarketProductsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )
```

**Características**:
- Control de acceso: `require_roles("colaborador", "admin")`
- Validación automática de params (Pydantic)
- Eager loading para evitar N+1 queries
- Cálculo de `total_pages` en backend

### 3.3 Lógica de preferred_name

```python
preferred_name = prod.sku_custom if prod.sku_custom else prod.name
```

**Regla**: Si `sku_custom` está definido (no NULL ni vacío), usarlo; sino, usar `name`.

**Consistencia**: El frontend siempre recibe `preferred_name` ya computado, no necesita implementar esta lógica.

---

## 4. Flujo de Integración Completo

### 4.1 Escenario: Usuario aplica filtros

1. **Usuario escribe "lámpara"** en campo de búsqueda
   - Estado: `q = "lámpara"`, debounce inicia (300ms)

2. **Debounce expira, se ejecuta `loadProducts()`**
   - Llama: `listMarketProducts({ q: "lámpara", page: 1, page_size: 50 })`

3. **`listMarketProducts()` construye URL**
   - URL: `/market/products?q=lámpara&page=1&page_size=50`
   - HTTP GET al backend

4. **Backend recibe request**
   - Middleware de autenticación valida token
   - Dependency `require_roles` verifica rol (admin/colaborador)
   - Query params parseados: `{ q: "lámpara", page: 1, page_size: 50 }`

5. **Backend ejecuta query**
   ```sql
   SELECT canonical_products.*, categories.name AS category_name
   FROM canonical_products
   LEFT JOIN categories ON categories.id = canonical_products.category_id
   WHERE (
       LOWER(canonical_products.name) LIKE '%lámpara%' OR
       LOWER(canonical_products.sku_custom) LIKE '%lámpara%' OR
       LOWER(canonical_products.ng_sku) LIKE '%lámpara%'
   )
   ORDER BY LOWER(canonical_products.name)
   LIMIT 50 OFFSET 0;
   ```

6. **Backend construye respuesta**
   - Itera productos, calcula `preferred_name`, obtiene `category_name`
   - Retorna JSON:
   ```json
   {
     "items": [
       {
         "product_id": 42,
         "preferred_name": "Lámpara LED 100W",
         "sale_price": 1250.00,
         "market_price_reference": 1100.00,
         "market_price_min": null,
         "market_price_max": null,
         "last_market_update": null,
         "category_id": 5,
         "category_name": "Iluminación",
         "supplier_id": null,
         "supplier_name": null
       }
     ],
     "total": 1,
     "page": 1,
     "page_size": 50,
     "pages": 1
   }
   ```

7. **Frontend procesa respuesta**
   - `setItems(response.items)` → actualiza tabla
   - `setTotal(1)`, `setTotalPages(1)` → actualiza paginación
   - `setLoading(false)` → oculta spinner

8. **UI muestra resultados**
   - Tabla renderiza 1 fila con "Lámpara LED 100W"
   - Paginación: "Página 1 de 1 (1 productos)"

### 4.2 Escenario: Error de autenticación

1. **Request sin token válido**
   - Backend: Middleware rechaza con `401 Unauthorized`

2. **HTTP client intercepta error**
   - Lanza excepción con `error.message = "No autorizado"`

3. **`catch` block en `loadProducts()`**
   - `push({ kind: 'error', message: 'No autorizado' })`
   - `setItems([])` → limpia tabla
   - `setLoading(false)` → oculta spinner

4. **UI muestra toast de error**
   - Usuario ve: "❌ No autorizado"

### 4.3 Escenario: Paginación

1. **Usuario clickea "Siguiente"**
   - `setPage(2)` → trigger `useEffect`

2. **Debounce (300ms) y llamada**
   - `listMarketProducts({ page: 2, page_size: 50 })`

3. **Backend retorna página 2**
   - Query con `OFFSET 50 LIMIT 50`

4. **Frontend reemplaza items**
   - `setItems(response.items)` (NO append, reemplaza)

5. **Tabla muestra productos 51-100**

---

## 5. Manejo de Errores

### 5.1 Errores HTTP Comunes

| Código | Escenario | Manejo Backend | Manejo Frontend |
|--------|-----------|----------------|-----------------|
| 401 | Sin token válido | Middleware rechaza | Toast: "No autorizado" |
| 403 | Rol insuficiente | `require_roles` rechaza | Toast: "Permiso denegado" |
| 422 | Validación fallida | Pydantic valida params | Toast: "Parámetros inválidos" |
| 500 | Error interno | Exception handler | Toast: "Error del servidor" |

### 5.2 Validaciones Frontend

```typescript
// Validación de page_size antes de enviar (opcional, backend también valida)
const safePageSize = Math.min(Math.max(pageSize, 1), 200)

await listMarketProducts({ page_size: safePageSize })
```

### 5.3 Validaciones Backend

```python
page_size: int = Query(50, ge=1, le=200)  # Mínimo 1, máximo 200
page: int = Query(1, ge=1)  # Mínimo 1
```

**Beneficio**: Doble validación previene requests inválidos y mejora seguridad.

---

## 6. Testing de Integración

### 6.1 Tests Backend (test_market_api.py)

```python
@pytest.mark.asyncio
async def test_market_products_filter_by_name(client_collab, db):
    # Setup: Crear productos de prueba
    prod1 = CanonicalProduct(name="Cámara HD", sale_price=Decimal("500.00"))
    prod2 = CanonicalProduct(name="Cámara 4K", sale_price=Decimal("800.00"))
    db.add_all([prod1, prod2])
    await db.commit()
    
    # Test: Filtrar por "cámara"
    resp = await client_collab.get("/market/products?q=cámara")
    
    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert "Cámara" in data["items"][0]["preferred_name"]
```

**Cobertura**: 12 test cases (ver `docs/API_MARKET.md` sección Tests)

### 6.2 Tests Frontend (pendientes)

**Recomendación**: React Testing Library

```typescript
describe('Market.tsx - listMarketProducts integration', () => {
  it('should load products on mount', async () => {
    // Mock HTTP response
    mockHttp.get.mockResolvedValue({
      data: {
        items: [mockProduct],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1
      }
    })
    
    render(<Market />)
    
    // Assert: Spinner visible inicialmente
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
    
    // Assert: Producto aparece después de carga
    await waitFor(() => {
      expect(screen.getByText('Lámpara LED')).toBeInTheDocument()
    })
  })
})
```

---

## 7. Optimizaciones Implementadas

### 7.1 Frontend

✅ **Debounce de búsqueda** (300ms): Reduce llamadas al escribir  
✅ **Conversión de tipos**: String vacío → `undefined` (no envía param innecesario)  
✅ **Reset de estados**: Limpia datos al cambiar filtros  
✅ **Loading states**: Feedback visual durante carga  

### 7.2 Backend

✅ **Eager loading**: `selectinload(category, subcategory)` evita N+1  
✅ **Subquery eficiente**: Filtro por proveedor con `IN` (no join)  
✅ **Paginación optimizada**: `LIMIT/OFFSET` con count separado  
✅ **Índices DB**: `name`, `category_id` (herencia de tabla existente)  

---

## 8. Próximos Pasos de Integración

### 8.1 Etapa 2 (CRUD de Fuentes)

**Backend pendiente**:
- Endpoints: `GET/POST/DELETE /products/{id}/market/sources`
- Endpoint: `PATCH /products/{id}/market-reference`
- Migración: Tabla `market_sources`

**Frontend pendiente**:
- Actualizar `getProductSources()` para consumir endpoint real
- Implementar `addProductSource()`, `deleteProductSource()`
- Reemplazar mock data en `MarketDetailModal.tsx`

### 8.2 Etapa 3 (Worker de Scraping)

**Backend pendiente**:
- Endpoint: `POST /products/{id}/update-market`
- Worker: `workers/scraping/market_prices.py`
- Parsers: MercadoLibre, SantaPlanta, genérico

**Frontend pendiente**:
- Implementar `updateProductMarketPrices()` con endpoint real
- Actualizar UI con loading state durante scraping (2-10 seg)

---

## 9. Troubleshooting

### 9.1 Error: "No se encontraron productos"

**Causa probable**: DB vacía o filtros demasiado restrictivos

**Solución**:
1. Verificar que existen productos: `SELECT COUNT(*) FROM canonical_products;`
2. Limpiar filtros en UI
3. Revisar logs backend para query ejecutada

### 9.2 Error: "403 Forbidden"

**Causa**: Usuario sin rol admin/colaborador

**Solución**:
1. Verificar rol en token JWT/sesión
2. Asignar rol correcto: `UPDATE users SET role='colaborador' WHERE id=X;`

### 9.3 Error: "TypeError: Cannot read property 'items'"

**Causa**: Frontend espera `response.data.items` pero backend retorna diferente estructura

**Solución**:
1. Verificar estructura de respuesta con DevTools (Network tab)
2. Ajustar path de acceso a datos según HTTP client usado

### 9.4 Productos duplicados en tabla

**Causa**: Paginación usando append en lugar de replace

**Solución**:
```typescript
// ❌ Incorrecto
setItems([...items, ...response.items])

// ✅ Correcto
setItems(response.items)
```

---

## 10. Referencias

- **Documentación API**: `docs/API_MARKET.md`
- **Plan maestro**: `docs/MERCADO.md`
- **Tests backend**: `tests/test_market_api.py`
- **Código frontend**: `frontend/src/pages/Market.tsx`, `frontend/src/services/market.ts`
- **Código backend**: `services/routers/market.py`

---

**Actualizado**: 2025-11-11  
**Estado**: Integración GET /market/products completada y funcional
