<!-- NG-HEADER: Nombre de archivo: MERCADO_IMPLEMENTACION.md -->
<!-- NG-HEADER: Ubicación: docs/MERCADO_IMPLEMENTACION.md -->
<!-- NG-HEADER: Descripción: Detalles técnicos de implementación de la funcionalidad Mercado -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Funcionalidad "Mercado" - Detalles de Implementación

## Resumen

La funcionalidad "Mercado" permite a administradores y colaboradores visualizar y comparar los precios de venta de los productos con rangos de precios actuales del mercado, facilitando decisiones de pricing informadas.

## Arquitectura General

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│                                                               │
│  ┌─────────────┐    ┌──────────────┐   ┌─────────────────┐ │
│  │  Market.tsx │───▶│ AppToolbar   │   │ MarketDetail    │ │
│  │  (tabla)    │    │ (navegación) │   │ Modal (Etapa 4) │ │
│  └─────────────┘    └──────────────┘   └─────────────────┘ │
│         │                                                     │
│         │ GET /market/products (Etapa 2)                    │
│         │ POST /products/{id}/update-market (Etapa 3)       │
└─────────┼─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                        │
│                                                               │
│  ┌──────────────────┐         ┌──────────────────────────┐  │
│  │ /market/products │◀────────│ Products + MarketSources │  │
│  │  (endpoint)      │         │    (DB models)           │  │
│  └──────────────────┘         └──────────────────────────┘  │
│                                                               │
│  ┌──────────────────────────┐                                │
│  │ /products/{id}/update-   │                                │
│  │  market (trigger scrape) │                                │
│  └────────────┬─────────────┘                                │
└───────────────┼──────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                  Worker de Scraping                          │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Playwright  │  │ BeautifulSoup│  │ MCP Web Search    │  │
│  │ (JS sites)  │  │ (static HTML)│  │ (fuentes extra)   │  │
│  └─────────────┘  └──────────────┘  └───────────────────┘  │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Parsers Específicos                      │   │
│  │  - MercadoLibre                                       │   │
│  │  - SantaPlanta                                        │   │
│  │  - Fabricantes directos                               │   │
│  │  - Genérico (fallback)                                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Estado Actual (Etapa 0 + 1)

### Frontend Implementado

#### Componente Principal: `Market.tsx`

**Ubicación**: `frontend/src/pages/Market.tsx`

**Características**:
- Tabla responsive con 6 columnas: Producto, Precio Venta, Precio Mercado, Última Actualización, Categoría, Acciones
- **Sistema de filtros avanzado**:
  - **Búsqueda por nombre/SKU**: Input de texto con debounce de 300ms para evitar llamadas excesivas
  - **Filtro por proveedor**: Autocomplete reutilizado de Stock con búsqueda dinámica
  - **Filtro por categoría**: Dropdown con todas las categorías del sistema
  - **Filtros simultáneos**: Todos los filtros pueden aplicarse al mismo tiempo
  - **Limpieza de filtros**: Botón "Limpiar filtros" visible cuando hay filtros activos
  - **Badges de filtros activos**: Muestra visualmente los filtros aplicados con opción de remover individualmente
- Indicadores visuales de comparación:
  - Verde: precio por debajo del mercado (`.price-below-market`)
  - Rojo: precio por encima del mercado (`.price-above-market`)
  - Azul: precio dentro del rango (`.price-in-market`)
- Paginación (50 items por página)
- Navegación rápida a Productos y Stock
- **Estados vacíos mejorados**:
  - Sin filtros: mensaje de pendiente implementación backend
  - Con filtros sin resultados: mensaje específico + botón para limpiar filtros
- Placeholder para modal de detalles (Etapa 4)

**Estados gestionados**:
```typescript
// Filtros
categoryId: string
supplierId: string
q: string (búsqueda)

// Datos
items: MarketProduct[]
page: number
total: number
loading: boolean

// UI
selectedProductId: number | null (modal)
```

**Tipo de datos** (temporal, será reemplazado por servicio):
```typescript
interface MarketProduct {
  product_id: number
  preferred_name: string
  name: string
  sale_price: number | null
  market_price_min: number | null
  market_price_max: number | null
  market_price_reference: number | null
  last_market_update: string | null
  category_path?: string
}
```

#### Navegación y Rutas

**Modificaciones en `paths.ts`**:
```typescript
market: "/mercado"
```

**Modificaciones en `App.tsx`**:
- Import lazy: `const Market = lazy(() => import('./pages/Market'))`
- Ruta protegida con roles `["colaborador", "admin"]`

**Modificaciones en `AppToolbar.tsx`**:
- Botón "Mercado" visible solo para staff (admin/colaborador)
- Ubicación: entre "Productos" y selector de tema

### Funciones Auxiliares Implementadas

```typescript
// Formateo de precios
formatPrice(price: number | null): string
// Ej: null → "-", 1250.50 → "$ 1250.50"

// Formateo de rango
formatMarketRange(min: number | null, max: number | null): string
// Ej: (100, 150) → "$ 100.00 - $ 150.00"
// Ej: (null, null) → "Sin datos"

// Formateo de fechas relativas
formatDate(dateStr: string | null): string
// Ej: hoy → "Hoy", hace 3 días → "Hace 3 días"

// Clasificación de precio
getPriceComparisonClass(sale, min, max): string
// Retorna clase CSS según posición en rango

// Gestión de filtros
resetAndSearch(): void
// Reinicia paginación y array de items al cambiar filtros

clearAllFilters(): void
// Limpia todos los filtros activos (búsqueda, proveedor, categoría)

hasActiveFilters(): boolean
// Verifica si hay algún filtro aplicado (para mostrar botón limpiar)
```

### Flujo de Filtrado

1. **Cambio de filtro**: Usuario modifica búsqueda, proveedor o categoría
2. **Debounce**: Se espera 300ms para evitar llamadas excesivas
3. **Reset paginación**: Se reinicia a página 1
4. **Llamada al backend**: Se envían todos los filtros como query params
5. **Actualización UI**: Tabla se actualiza con resultados filtrados
6. **Feedback visual**: 
   - Badges muestran filtros activos
   - Contador muestra cantidad de resultados
   - Estado vacío si no hay coincidencias

### Control de Acceso

- Solo usuarios con rol `admin` o `colaborador` pueden acceder
- Validado en nivel de ruta (`ProtectedRoute`)
- Botón de navegación condicionalmente visible en toolbar

## Modelo de Datos Propuesto (Etapa 2)

### Nueva Tabla: `market_sources`

```sql
CREATE TABLE market_sources (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    source_name VARCHAR(200) NOT NULL,
    url TEXT NOT NULL,
    last_price NUMERIC(10, 2),
    last_checked_at TIMESTAMP,
    is_mandatory BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_product_source UNIQUE (product_id, source_name)
);

CREATE INDEX idx_market_sources_product ON market_sources(product_id);
CREATE INDEX idx_market_sources_updated ON market_sources(last_checked_at DESC);
```

### Campos Adicionales en `products`

```sql
ALTER TABLE products ADD COLUMN market_price_min NUMERIC(10, 2);
ALTER TABLE products ADD COLUMN market_price_max NUMERIC(10, 2);
ALTER TABLE products ADD COLUMN market_last_update TIMESTAMP;

CREATE INDEX idx_products_market_update ON products(market_last_update DESC);
```

### Relaciones

- Un producto puede tener múltiples fuentes (1:N)
- Cada fuente guarda su último precio y timestamp
- El rango min-max se calcula dinámicamente o se cachea en `products`

## Endpoints Backend Propuestos (Etapa 2)

### `GET /market/products`

**Descripción**: Lista productos con datos de mercado

**Query params**:
```typescript
{
  q?: string           // búsqueda nombre/SKU
  supplier_id?: number // filtro proveedor
  category_id?: number // filtro categoría
  page?: number        // paginación (default: 1)
  page_size?: number   // items por página (default: 50)
  sort_by?: string     // campo ordenamiento
  order?: 'asc'|'desc' // dirección
}
```

**Response**:
```typescript
{
  items: MarketProduct[]
  total: number
  page: number
  page_size: number
}
```

**Lógica**:
1. Join `products` con `market_sources` (LEFT para incluir sin fuentes)
2. Calcular min/max por producto (GROUP BY)
3. Aplicar filtros de búsqueda y categoría
4. Paginar y retornar

### `POST /products/{id}/update-market`

**Descripción**: Lanza scraping de precios para un producto

**Path params**:
- `id`: product_id

**Body** (opcional):
```typescript
{
  force?: boolean       // forzar incluso si actualizado recientemente
  sources?: string[]    // limitar a fuentes específicas
  include_web?: boolean // incluir búsqueda web adicional
}
```

**Response**:
```typescript
{
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
}
```

**Lógica**:
1. Validar permisos (admin/colaborador)
2. Verificar última actualización (skip si reciente y no force)
3. Obtener fuentes obligatorias de `market_sources`
4. Lanzar worker de scraping (async si Dramatiq, sync si simple)
5. Actualizar precios y timestamps
6. Recalcular rango
7. Retornar resultado

### `GET /products/{id}/market/sources`

**Descripción**: Lista fuentes configuradas para un producto

**Response**:
```typescript
{
  mandatory: MarketSource[]
  additional: MarketSource[]
}

interface MarketSource {
  id: number
  name: string
  url: string
  last_price: number | null
  last_checked_at: string | null
  is_mandatory: boolean
}
```

### `POST /products/{id}/market/sources`

**Descripción**: Agrega una fuente al producto

**Body**:
```typescript
{
  name: string          // "MercadoLibre", "SantaPlanta", etc.
  url: string          // URL del producto en la fuente
  is_mandatory: boolean // si es obligatoria
}
```

### `DELETE /products/{id}/market/sources/{source_id}`

**Descripción**: Elimina una fuente

## Estrategia de Scraping (Etapa 3)

### Arquitectura del Worker

```
workers/scraping/
├── __init__.py
├── market_prices.py           # Orquestador principal
├── base.py                    # Clase base Parser
├── utils.py                   # Normalización precios, manejo errores
└── parsers/
    ├── __init__.py
    ├── mercadolibre.py       # Parser específico ML
    ├── santaplanta.py        # Parser específico SantaPlanta
    ├── generic.py            # Parser fallback
    └── web_search.py         # Integración MCP Web Search
```

### Flujo de Scraping

1. **Recepción de tarea**:
   - Endpoint recibe `product_id`
   - Busca fuentes obligatorias en DB
   - Genera lista de URLs a scrapear

2. **Ejecución de parsers**:
   - Por cada fuente, selecciona parser específico o genérico
   - Intenta con Requests + BeautifulSoup primero
   - Si falla, fallback a Playwright (JS rendering)
   - Manejo de timeouts y errores por fuente

3. **Normalización**:
   - Detectar símbolo de moneda (ARS: `$`, `ARS`)
   - Limpiar formato (puntos/comas, espacios)
   - Convertir a float
   - Validar rango razonable (> 0, < 1000000)

4. **Persistencia**:
   - Actualizar `market_sources.last_price` y `last_checked_at`
   - Recalcular min/max del producto
   - Actualizar `products.market_price_min/max/last_update`
   - Log de operación

5. **Fuentes adicionales** (opcional):
   - Invocar MCP Web Search con query tipo "precio {nombre_producto}"
   - Filtrar resultados por dominios conocidos
   - Parsear precios de resultados
   - Agregar como fuentes "adicionales" (no mandatory)

### Parsers Específicos

#### MercadoLibre

```python
class MercadoLibreParser(BaseParser):
    def parse_price(self, html: str) -> float | None:
        soup = BeautifulSoup(html, 'html.parser')
        # Selector: .ui-pdp-price__second-line .andes-money-amount__fraction
        price_element = soup.select_one('.andes-money-amount__fraction')
        if not price_element:
            return None
        return self.normalize_price(price_element.text)
```

#### SantaPlanta

```python
class SantaPlantaParser(BaseParser):
    def parse_price(self, html: str) -> float | None:
        soup = BeautifulSoup(html, 'html.parser')
        # Selector específico de SantaPlanta (ajustar según su HTML)
        price_element = soup.select_one('.product-price')
        if not price_element:
            return None
        return self.normalize_price(price_element.text)
```

#### Genérico (Fallback)

```python
class GenericParser(BaseParser):
    def parse_price(self, html: str) -> float | None:
        # Busca patrones comunes: $1.234,56 o ARS 1234.56
        patterns = [
            r'\$\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
            r'ARS\s*(\d+(?:[.,]\d+)?)',
            r'precio[:\s]+\$?\s*(\d+(?:[.,]\d+)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return self.normalize_price(match.group(1))
        return None
```

### Manejo de Errores

```python
class ScrapingError(Exception):
    """Error base de scraping"""

class SourceUnavailableError(ScrapingError):
    """Fuente no responde o timeout"""

class PriceNotFoundError(ScrapingError):
    """No se encontró precio en la página"""

class InvalidPriceError(ScrapingError):
    """Precio detectado pero inválido"""
```

**Estrategia**:
- Si una fuente falla, continuar con las demás
- Loggear error específico con contexto (URL, producto, mensaje)
- No bloquear actualización de otras fuentes
- Retornar lista de éxitos/fallos al cliente

### Actualización Programada (Futuro)

```python
# Cron job diario o semanal
@dramatiq.actor
def update_all_market_prices():
    products = session.query(Product).filter(
        Product.market_last_update < datetime.now() - timedelta(days=7)
    ).all()
    
    for product in products:
        update_product_market_prices.send(product.id)
```

## Modal de Detalles (Etapa 4 - ✅ Completada)

### Servicio: `frontend/src/services/market.ts`

**Interfaces exportadas**:
```typescript
interface MarketSource {
  id: number
  product_id: number
  source_name: string
  url: string
  last_price: number | null
  last_checked_at: string | null  // ISO 8601
  is_mandatory: boolean
  created_at: string
  updated_at: string
}

interface ProductSourcesResponse {
  product_id: number
  mandatory_sources: MarketSource[]
  additional_sources: MarketSource[]
}

interface UpdateMarketPricesResponse {
  product_id: number
  updated_count: number
  failed_count: number
  sources_updated: Array<{
    source_id: number
    source_name: string
    price: number | null
    error?: string
  }>
}

interface AddSourcePayload {
  source_name: string
  url: string
  is_mandatory: boolean
}
```

**Funciones exportadas**:

1. **`getProductSources(productId: number): Promise<ProductSourcesResponse>`**
   - Obtiene todas las fuentes de precio asociadas al producto
   - Separa fuentes obligatorias y adicionales
   - **Endpoint backend esperado**: `GET /products/{id}/market/sources`

2. **`updateProductMarketPrices(productId: number, options?): Promise<UpdateMarketPricesResponse>`**
   - Dispara actualización de precios mediante scraping
   - Opciones: `onlyMandatory` (boolean), `force` (boolean)
   - **Endpoint backend esperado**: `POST /products/{id}/update-market`

3. **`addProductSource(productId: number, payload: AddSourcePayload): Promise<MarketSource>`**
   - Agrega nueva fuente de precio al producto
   - **Endpoint backend esperado**: `POST /products/{id}/market/sources`

4. **`deleteProductSource(productId: number, sourceId: number): Promise<void>`**
   - Elimina fuente de precio
   - **Endpoint backend esperado**: `DELETE /products/{id}/market/sources/{source_id}`

5. **`validateSourceUrl(url: string): { valid: boolean; error?: string }`**
   - Validación cliente de URL:
     - Debe comenzar con http:// o https://
     - Debe contener hostname válido
     - Retorna mensaje de error específico si inválida

**Estado actual**: Mock data implementado con timestamps realistas para permitir desarrollo completo del frontend antes de backend.

---

### Componente Principal: `MarketDetailModal.tsx`

**Ubicación**: `frontend/src/components/MarketDetailModal.tsx`

**Props**:
```typescript
interface MarketDetailModalProps {
  productId: number | null
  productName: string
  open: boolean
  onClose: () => void
  onPricesUpdated?: () => void  // callback para refrescar tabla principal
}
```

**Estado gestionado**:
```typescript
const [sources, setSources] = useState<ProductSourcesResponse | null>(null)
const [loading, setLoading] = useState(false)
const [updating, setUpdating] = useState(false)
const [showAddSource, setShowAddSource] = useState(false)
const [deletingId, setDeletingId] = useState<number | null>(null)
```

**Funciones principales**:

1. **`loadSources()`**: Carga fuentes del producto al abrir modal
2. **`handleUpdatePrices()`**: Dispara actualización de precios, muestra feedback con toast
3. **`handleDeleteSource(sourceId)`**: Elimina fuente con confirmación previa
4. **`handleAddSourceSuccess()`**: Callback para refrescar después de agregar fuente

**Estructura visual del modal**:

```
┌─────────────────────────────────────────────────────────────┐
│ [×] Fuentes de Precio - {Nombre del Producto}               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  📊 Resumen:                                                 │
│    • Total fuentes: 5                                        │
│    • Obligatorias: 2                                         │
│    • Adicionales: 3                                          │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 🔴 Fuentes Obligatorias                                 │ │
│  │                                                          │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │ MercadoLibre                          [🗑️ Eliminar]│  │ │
│  │  │ Precio: $1,250.00                                 │  │ │
│  │  │ Actualizado: hace 2 horas [✓ fresco]              │  │ │
│  │  │ 🔗 Ver en sitio                                   │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │                                                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ ➕ Fuentes Adicionales                                  │ │
│  │                                                          │ │
│  │  [Tarjetas similares a fuentes obligatorias]           │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ [🔄 Actualizar Precios]  [➕ Agregar Nueva Fuente]      │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│                                      [Cerrar]                 │
└─────────────────────────────────────────────────────────────┘
```

**Sub-componente interno: `SourceCard`**:

Renderiza cada fuente individual con:
- Nombre de la fuente (título)
- Precio formateado (o "Sin precio" si null)
- Fecha de última actualización con **indicador de frescura**:
  - 🟢 **Fresh** (<24h): verde
  - 🟡 **Stale** (1-7 días): amarillo
  - 🔴 **Never** (>7 días o null): rojo
- Enlace "🔗 Ver en sitio" (abre en nueva pestaña)
- Botón "🗑️ Eliminar" con confirmación

**Características UX**:
- Loading skeleton mientras carga fuentes
- Spinner en botón "Actualizar Precios" durante operación
- Confirmación nativa (`window.confirm`) antes de eliminar
- Toasts para feedback:
  - Éxito al actualizar: "✓ Precios actualizados. X fuentes consultadas."
  - Error al actualizar: "⚠ Error al actualizar precios"
  - Error al eliminar: "⚠ Error al eliminar fuente"
- Scroll interno si hay muchas fuentes
- Backdrop con click para cerrar

---

### Sub-Modal: `AddSourceModal.tsx`

**Ubicación**: `frontend/src/components/AddSourceModal.tsx`

**Props**:
```typescript
interface AddSourceModalProps {
  productId: number | null
  open: boolean
  onClose: () => void
  onSuccess: () => void  // callback al agregar exitosamente
}
```

**Estado del formulario**:
```typescript
const [name, setName] = useState('')
const [url, setUrl] = useState('')
const [isMandatory, setIsMandatory] = useState(false)
const [submitting, setSubmitting] = useState(false)
const [errors, setErrors] = useState<{name?: string; url?: string}>({})
```

**Validaciones implementadas**:

1. **Nombre**:
   - Requerido
   - Mínimo 3 caracteres
   - Máximo 200 caracteres
   - Error: "El nombre debe tener entre 3 y 200 caracteres"

2. **URL**:
   - Requerida
   - Debe comenzar con `http://` o `https://`
   - Debe contener hostname válido
   - Usa `validateSourceUrl()` del servicio
   - Error: mensaje específico de `validateSourceUrl`

**Comportamiento del formulario**:
- Limpieza automática de errores al cambiar campo
- Validación al submit (no en tiempo real para no ser intrusivo)
- Submit deshabilitado si ya está enviando
- Limpieza del formulario después de éxito
- Toast de confirmación: "✓ Fuente agregada exitosamente"
- Toast de error: "⚠ Error al agregar fuente"

**Estructura visual**:

```
┌─────────────────────────────────────────────────────────────┐
│ [×] Agregar Nueva Fuente                                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Nombre de la fuente *                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ej. MercadoLibre, SantaPlanta, FabricanteX          │   │
│  └──────────────────────────────────────────────────────┘   │
│  [mensaje de error si aplica]                                │
│                                                               │
│  URL del producto *                                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ https://ejemplo.com/producto                         │   │
│  └──────────────────────────────────────────────────────┘   │
│  [mensaje de error si aplica]                                │
│                                                               │
│  ☐ Marcar como fuente obligatoria                           │
│                                                               │
│  ℹ️ Ejemplos de fuentes válidas:                            │
│    • MercadoLibre: buscar el producto y copiar URL          │
│    • SantaPlanta: página del producto específico            │
│    • Fabricante directo: link al catálogo/producto          │
│                                                               │
│                    [Cancelar]  [Agregar Fuente]              │
└─────────────────────────────────────────────────────────────┘
```

**Detalles técnicos**:
- z-index: 1001 (por encima del modal padre que tiene backdrop con z-index 1000)
- Ancho fijo: 500px, centrado
- Submit con Enter en inputs
- Escape para cerrar (si no hay cambios pendientes)

---

### Integración en `Market.tsx`

**Cambios realizados**:

1. **Nuevo estado**:
```typescript
const [selectedProductId, setSelectedProductId] = useState<number | null>(null)
const [selectedProductName, setSelectedProductName] = useState<string>('')
```

2. **Handlers agregados**:
```typescript
function handleOpenDetail(productId: number, productName: string) {
  setSelectedProductId(productId)
  setSelectedProductName(productName)
}

function handleCloseDetail() {
  setSelectedProductId(null)
  setSelectedProductName('')
}

function handlePricesUpdated() {
  loadProducts()  // Refresca tabla para mostrar nuevos rangos
}
```

3. **Botón en tabla actualizado**:
```tsx
<button 
  onClick={() => handleOpenDetail(
    product.product_id, 
    product.preferred_name || product.name
  )}
  style={{...}}
>
  👁️ Ver
</button>
```

4. **Renderizado del modal**:
```tsx
<MarketDetailModal
  productId={selectedProductId}
  productName={selectedProductName}
  open={!!selectedProductId}
  onClose={handleCloseDetail}
  onPricesUpdated={handlePricesUpdated}
/>
```

---

## Edición de Precios (Extensión Etapa 4 - ✅ Completada)

### Componente: `EditablePriceField.tsx`

**Ubicación**: `frontend/src/components/EditablePriceField.tsx`

**Props**:
```typescript
interface EditablePriceFieldProps {
  label: string
  value: number | null
  onSave: (newValue: number) => Promise<void>
  disabled?: boolean
  placeholder?: string
  formatPrefix?: string  // default: '$'
}
```

**Características**:

1. **Modo lectura**: Muestra valor formateado con ícono ✏️
   - Clic para entrar en modo edición
   - Hover muestra cursor pointer
   - Si `disabled=true`, no permite edición

2. **Modo edición**: Input numérico con botones de acción
   - Input type="number" con step="0.01"
   - Validación en tiempo real con `validatePrice()`
   - Botones: ✓ (guardar) y ✕ (cancelar)
   - Atajos de teclado: Enter (guardar), Esc (cancelar)
   - Loading state durante guardado
   - Mensajes de error bajo el input

3. **Validaciones** (función `validatePrice` en `market.ts`):
   - Debe ser número válido
   - Debe ser mayor a cero
   - Máximo: 999,999,999
   - Mensajes de error específicos

4. **UX/UI**:
   - Focus automático al entrar en edición
   - Select automático del texto para facilitar reemplazo
   - Hint de atajos de teclado visible
   - Estados de loading (cursor: wait, opacidad reducida)
   - No guarda si el valor no cambió (evita llamadas innecesarias)

**Reutilizable**: Diseñado para usarse en cualquier contexto que requiera editar precios.

---

### Integración en `MarketDetailModal.tsx`

**Nuevas funciones agregadas en `market.ts`**:

```typescript
// Actualizar precio de venta
export async function updateProductSalePrice(
  productId: number,
  salePrice: number,
  note?: string
): Promise<{ id: number; sale_price: number }>

// Actualizar valor de mercado de referencia
export async function updateMarketReference(
  productId: number,
  marketReference: number
): Promise<{ id: number; market_price_reference: number }>

// Validación de precios
export function validatePrice(value: string | number): { 
  valid: boolean; 
  error?: string 
}
```

**Endpoints backend esperados** (Etapa 2):
- `PATCH /products-ex/products/{id}/sale-price` → actualiza precio de venta (reutiliza endpoint existente)
- `PATCH /products/{id}/market-reference` → actualiza valor de mercado de referencia (nuevo endpoint)

**Handlers en MarketDetailModal**:

```typescript
async function handleSaveSalePrice(newPrice: number) {
  // 1. Llama a updateProductSalePrice()
  // 2. Actualiza estado local (setSources)
  // 3. Muestra toast de éxito
  // 4. Notifica al padre (onPricesUpdated) para refrescar tabla
  // 5. En caso de error, muestra toast y re-lanza excepción
}

async function handleSaveMarketReference(newPrice: number) {
  // Similar a handleSaveSalePrice pero para market_price_reference
}
```

**Interfaz actualizada `ProductSourcesResponse`**:

```typescript
export interface ProductSourcesResponse {
  product_id: number
  product_name: string
  sale_price: number | null              // ⬅️ nuevo
  market_price_reference: number | null  // ⬅️ nuevo
  market_price_min: number | null        // ⬅️ nuevo
  market_price_max: number | null        // ⬅️ nuevo
  mandatory: MarketSource[]
  additional: MarketSource[]
}
```

**Nueva sección en el modal: "Gestión de Precios"**:

Ubicada entre el header y la lista de fuentes, muestra 3 campos en grid:

1. **Precio de Venta** (editable):
   - `EditablePriceField` vinculado a `handleSaveSalePrice`
   - Actualiza el precio del producto en la tabla principal
   - Registra cambio en historial (si backend lo soporta)

2. **Valor Mercado (Referencia)** (editable):
   - `EditablePriceField` vinculado a `handleSaveMarketReference`
   - Permite ajuste manual cuando scraping falla o datos son incorrectos
   - Útil para ingresar valor conocido de otra fuente

3. **Rango de Mercado** (solo lectura):
   - Muestra `market_price_min` - `market_price_max`
   - Calculado automáticamente desde las fuentes
   - Estilo visual diferenciado (fondo gris, sin hover)
   - Texto explicativo: "Calculado automáticamente"

**Feedback visual**:
- Toast de éxito: "Precio de venta actualizado correctamente"
- Toast de éxito: "Valor de mercado de referencia actualizado"
- Toast de error: "Error actualizando precio de venta"
- Tip al final de la sección con ícono 💡

**Flujo completo**:
```
Usuario clic en campo → Modo edición → Ingresa valor → Enter →
Validación → Llamada API → Actualiza estado local → Toast éxito →
Refresca tabla padre
```

---

### Control de Acceso

**Restricción por roles**: La edición de precios solo está disponible para usuarios con rol `admin` o `colaborador` (herencia de restricción de la página Market).

**Implementación futura** (opcional para mayor seguridad):
- Agregar prop `canEdit: boolean` a `EditablePriceField`
- Calcular en MarketDetailModal basado en `useAuth().role`
- Si el usuario no tiene permisos, mostrar campos en modo lectura permanente

---

### Auditoría y Historial

**Próxima mejora** (post-Etapa 4):

Cuando se actualice el precio de venta, registrar en tabla de auditoría:
- Producto afectado
- Usuario que realizó el cambio
- Valor anterior y nuevo
- Timestamp
- Nota opcional (campo `note` ya presente en `updateProductSalePrice`)

**Visualización** (futuro):
- Agregar pestaña "Historial de Precios" en el modal
- Mostrar tabla con cambios recientes (últimos 30 días)
- Gráfico de línea temporal

---

### Próximos pasos para Etapa 4

**Backend requerido** (Etapa 2):

1. Crear tabla `market_sources`:
```sql
CREATE TABLE market_sources (
  id SERIAL PRIMARY KEY,
  product_id INT REFERENCES products(id) ON DELETE CASCADE,
  source_name VARCHAR(200) NOT NULL,
  url TEXT NOT NULL,
  last_price NUMERIC(10,2),
  last_checked_at TIMESTAMP,
  is_mandatory BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(product_id, url)
);
CREATE INDEX idx_market_sources_product ON market_sources(product_id);
```

2. Implementar endpoints:
   - `GET /products/{id}/market/sources` → retorna ProductSourcesResponse (con precios del producto)
   - `POST /products/{id}/market/sources` → recibe AddSourcePayload
   - `DELETE /products/{id}/market/sources/{source_id}` → elimina fuente
   - `POST /products/{id}/update-market` → dispara worker scraping
   - `PATCH /products/{id}/market-reference` → actualiza market_price_reference **(nuevo para edición)**

3. Actualizar `products` table (si no existen):
   - `market_price_min NUMERIC(10,2)`
   - `market_price_max NUMERIC(10,2)`
   - `market_price_reference NUMERIC(10,2)` **(nuevo campo para valor manual)**
   - `market_last_update TIMESTAMP`

**Worker de scraping** (Etapa 3):
- Ver sección "Estrategia de Scraping" más abajo
- Integración con parsers específicos (MercadoLibre, SantaPlanta)
- MCP Web Search para fuentes adicionales

**Tests** (Etapa 5):
- Unit tests para market service (validateSourceUrl, mock responses)
- React Testing Library para modal components (interacción, validación)
- Integration tests para flujo completo (abrir modal → agregar fuente → actualizar → verificar)

## Tests (Etapa 5)

### Backend

#### Unit Tests: Parsers

```python
# tests/test_market_parsers.py

def test_mercadolibre_parser_success():
    html = load_fixture('mercadolibre_sample.html')
    parser = MercadoLibreParser()
    price = parser.parse_price(html)
    assert price == 1250.50

def test_parser_invalid_html():
    parser = MercadoLibreParser()
    price = parser.parse_price("<html></html>")
    assert price is None
```

#### Integration Tests: Scraping

```python
# tests/test_market_scraping.py
import respx
from httpx import Response

@respx.mock
async def test_update_product_market_prices():
    # Mock respuesta de MercadoLibre
    respx.get('https://www.mercadolibre.com.ar/...').mock(
        return_value=Response(200, html=SAMPLE_HTML)
    )
    
    result = await update_product_market_prices(product_id=1)
    
    assert result['updated_sources'][0]['success'] is True
    assert result['market_price_min'] == 1200.00
```

#### Tests de Endpoints

```python
# tests/test_market_endpoints.py

def test_get_market_products_auth():
    """Solo admin/colaborador pueden acceder"""
    response = client.get('/market/products', headers=guest_headers)
    assert response.status_code == 403

def test_get_market_products_filter_category():
    response = client.get('/market/products?category_id=5')
    assert response.status_code == 200
    data = response.json()
    assert all(p['category_id'] == 5 for p in data['items'])
```

### Frontend

#### Tests de Componente

```typescript
// __tests__/Market.test.tsx

describe('Market page', () => {
  test('renders table with correct columns', () => {
    render(<Market />)
    expect(screen.getByText('Producto')).toBeInTheDocument()
    expect(screen.getByText('Precio Venta (ARS)')).toBeInTheDocument()
    expect(screen.getByText('Precio Mercado (ARS)')).toBeInTheDocument()
  })

  test('filters by search query', async () => {
    render(<Market />)
    const searchInput = screen.getByPlaceholderText('Buscar por nombre o SKU...')
    
    await userEvent.type(searchInput, 'fertilizante')
    
    await waitFor(() => {
      expect(mockSearchProducts).toHaveBeenCalledWith(
        expect.objectContaining({ q: 'fertilizante' })
      )
    })
  })

  test('shows price comparison indicator', () => {
    const product = {
      sale_price: 1000,
      market_price_min: 1200,
      market_price_max: 1500
    }
    
    render(<MarketRow product={product} />)
    const priceCell = screen.getByText('$ 1000.00')
    expect(priceCell).toHaveClass('price-below-market')
  })
})
```

## Seguridad

### Validaciones Backend

1. **Control de acceso**:
   - Middleware verifica rol admin/colaborador
   - Queries filtran por permisos (no exponer datos sensibles)

2. **Validación de URLs**:
   ```python
   def validate_source_url(url: str) -> bool:
       parsed = urlparse(url)
       if parsed.scheme not in ['http', 'https']:
           raise ValueError('URL debe ser HTTP/HTTPS')
       # Lista blanca de dominios permitidos (opcional)
       allowed_domains = ['mercadolibre.com.ar', 'santaplanta.com', ...]
       if allowed_domains and parsed.netloc not in allowed_domains:
           raise ValueError('Dominio no permitido')
       return True
   ```

3. **Rate limiting de scraping**:
   - Limitar requests por minuto a cada dominio
   - Respetar `robots.txt` cuando sea razonable
   - User-Agent identificable

4. **Sanitización de datos**:
   - Escapar HTML al mostrar nombres de fuentes
   - Validar precios (rango razonable, no negativos)

### Consideraciones Éticas de Scraping

- Usar cache agresivo (no scrapear más de 1 vez por día por fuente)
- Identificarse con User-Agent claro (`Growen Price Monitor/1.0`)
- No sobrecargar servidores externos (delays entre requests)
- Respetar señales de bloqueo (HTTP 429, Captchas)

## Performance

### Optimizaciones

1. **Cache en frontend**:
   - Usar React Query para cachear lista de productos
   - TTL de 5 minutos para datos de mercado

2. **Cache en backend**:
   - Redis para resultados de scraping (1 hora)
   - Índices en `market_sources(product_id, last_checked_at)`

3. **Lazy loading**:
   - Cargar fuentes bajo demanda en modal
   - Paginación de historial de precios

4. **Scraping asíncrono**:
   - No bloquear UI mientras actualiza
   - WebSocket o polling para notificar completado
   - Queue de Dramatiq para procesar en background

## Monitoreo

### Métricas Clave

- **Tasa de éxito de scraping** por fuente
- **Latencia promedio** de actualización por fuente
- **Frecuencia de actualización** por producto
- **Top 10 productos** con mayor diferencial precio
- **Tasa de errores** (timeout, formato, parseo)

### Logs Estructurados

```json
{
  "event": "market_price_scraped",
  "product_id": 123,
  "source_name": "MercadoLibre",
  "success": true,
  "old_price": 1200.00,
  "new_price": 1250.00,
  "elapsed_ms": 350,
  "timestamp": "2025-11-11T10:30:00Z"
}
```

### Alertas

- Precio cambió más de 20% en 24 horas
- Fuente obligatoria falló 3 veces consecutivas
- Producto sin actualización en > 14 días

## Roadmap Futuro

### Corto plazo (post Etapa 5)
- [ ] Actualización automática programada (cron)
- [ ] Notificaciones en UI cuando precios estén muy desalineados
- [ ] Exportar reporte de comparación de precios (Excel/PDF)

### Mediano plazo
- [ ] Análisis de tendencias (precio subiendo/bajando últimos 30 días)
- [ ] Sugerencias automáticas de ajuste de precio
- [ ] Integración con sistema de pricing dinámico
- [ ] Soporte a múltiples monedas (conversión USD→ARS)

### Largo plazo
- [ ] Machine Learning para predecir precio óptimo
- [ ] Integración con APIs oficiales de marketplaces
- [ ] Sistema de alertas configurable por producto
- [ ] Dashboard ejecutivo con métricas de competitividad

---

**Autor**: Sistema de IA (GitHub Copilot)  
**Fecha**: 2025-11-11  
**Versión**: 1.0 (Etapas 0 + 1 completadas)
