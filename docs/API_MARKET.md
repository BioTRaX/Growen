<!-- NG-HEADER: Nombre de archivo: API_MARKET.md -->
<!-- NG-HEADER: Ubicación: docs/API_MARKET.md -->
<!-- NG-HEADER: Descripción: Documentación de API del módulo Mercado -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# API del Módulo Mercado

Este documento describe los endpoints del módulo "Mercado" que permite comparar precios de productos con valores de referencia del mercado.

## Endpoints

### GET /market/products

Lista productos con información de precios para el módulo Mercado.

**Roles permitidos**: `admin`, `colaborador`

**Descripción**:
Retorna una lista paginada de productos canónicos con su precio de venta actual, valor de mercado de referencia y rangos calculados (cuando estén disponibles).

#### Parámetros Query

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `q` | string | No | - | Búsqueda por nombre (parcial, case-insensitive). Busca en `name`, `sku_custom` y `ng_sku` |
| `category_id` | int | No | - | Filtrar por ID de categoría (incluye subcategorías) |
| `supplier_id` | int | No | - | Filtrar por ID de proveedor (a través de ProductEquivalence) |
| `page` | int | No | 1 | Número de página (≥ 1) |
| `page_size` | int | No | 50 | Tamaño de página (1-200) |

#### Respuesta Exitosa (200 OK)

```json
{
  "items": [
    {
      "product_id": 123,
      "preferred_name": "Cámara Digital Canon EOS",
      "sale_price": 1500.00,
      "market_price_reference": 1200.00,
      "market_price_min": 1180.00,
      "market_price_max": 1300.00,
      "last_market_update": "2025-11-10T15:30:00Z",
      "category_id": 5,
      "category_name": "Electrónica",
      "supplier_id": 2,
      "supplier_name": "Proveedor Principal"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 50,
  "pages": 1
}
```

#### Campos del Item

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `product_id` | int | ID del producto canónico |
| `preferred_name` | string | Nombre preferido (usa `sku_custom` si existe, sino `name`) |
| `sale_price` | float\|null | Precio de venta actual del producto |
| `market_price_reference` | float\|null | Valor de mercado de referencia (ingresado manualmente) |
| `market_price_min` | float\|null | Precio mínimo detectado en fuentes de mercado *(Etapa 2)* |
| `market_price_max` | float\|null | Precio máximo detectado en fuentes de mercado *(Etapa 2)* |
| `last_market_update` | string\|null | Fecha ISO 8601 de última actualización de mercado *(Etapa 2)* |
| `category_id` | int\|null | ID de la categoría principal |
| `category_name` | string\|null | Nombre de la categoría |
| `supplier_id` | int\|null | ID del proveedor principal (primera equivalencia) |
| `supplier_name` | string\|null | Nombre del proveedor principal |

**Nota**: Los campos `market_price_min`, `market_price_max` y `last_market_update` están marcados para implementación futura (Etapa 2) cuando se agregue la tabla `market_sources`. Actualmente retornan `null`.

#### Errores

| Código | Descripción |
|--------|-------------|
| 401 | Usuario no autenticado |
| 403 | Usuario sin permisos (requiere rol admin o colaborador) |
| 422 | Parámetros de query inválidos |

#### Ejemplos de Uso

**Listar todos los productos (primera página)**:
```bash
GET /market/products
```

**Buscar por nombre "cámara"**:
```bash
GET /market/products?q=cámara
```

**Filtrar por categoría**:
```bash
GET /market/products?category_id=5
```

**Filtrar por proveedor**:
```bash
GET /market/products?supplier_id=2
```

**Combinación de filtros con paginación**:
```bash
GET /market/products?q=laptop&category_id=3&page=1&page_size=20
```

**Página 2 con 100 items**:
```bash
GET /market/products?page=2&page_size=100
```

---

### GET /market/products/{product_id}/sources

Obtiene las fuentes de precio de mercado configuradas para un producto.

**Roles permitidos**: `admin`, `colaborador`

**Descripción**:
Retorna todas las fuentes de precio asociadas al producto, separadas en obligatorias y adicionales. Incluye el último precio obtenido y timestamp de última actualización para cada fuente.

#### Parámetros de Ruta

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `product_id` | int | ID del producto canónico |

#### Respuesta Exitosa (200 OK)

```json
{
  "product_id": 123,
  "product_name": "Cámara Digital Canon EOS",
  "sale_price": 1500.00,
  "market_price_reference": 1200.00,
  "mandatory": [
    {
      "id": 1,
      "source_name": "MercadoLibre",
      "url": "https://www.mercadolibre.com.ar/producto",
      "last_price": 1350.00,
      "last_checked_at": "2025-11-10T14:30:00Z",
      "is_mandatory": true,
      "created_at": "2025-10-01T10:00:00Z",
      "updated_at": "2025-11-10T14:30:00Z"
    },
    {
      "id": 2,
      "source_name": "SantaPlanta",
      "url": "https://www.santaplanta.com.ar/producto",
      "last_price": 1420.00,
      "last_checked_at": "2025-11-09T18:00:00Z",
      "is_mandatory": true,
      "created_at": "2025-10-01T10:00:00Z",
      "updated_at": "2025-11-09T18:00:00Z"
    }
  ],
  "additional": [
    {
      "id": 3,
      "source_name": "Tienda Online",
      "url": "https://www.ejemplo.com/producto",
      "last_price": null,
      "last_checked_at": null,
      "is_mandatory": false,
      "created_at": "2025-10-15T12:00:00Z",
      "updated_at": "2025-10-15T12:00:00Z"
    }
  ]
}
```

#### Campos de Respuesta

**Nivel Producto**:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `product_id` | int | ID del producto canónico |
| `product_name` | string | Nombre preferido del producto (usa `sku_custom` si existe, sino `name`) |
| `sale_price` | float\|null | Precio de venta actual del producto |
| `market_price_reference` | float\|null | Valor de mercado de referencia (manual) |
| `mandatory` | array | Lista de fuentes obligatorias |
| `additional` | array | Lista de fuentes adicionales |

**Campos de Fuente (MarketSourceItem)**:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | int | ID de la fuente |
| `source_name` | string | Nombre de la tienda o sitio (ej: "MercadoLibre", "SantaPlanta") |
| `url` | string | URL completa de la fuente |
| `last_price` | float\|null | Último precio obtenido en ARS (null si nunca se obtuvo) |
| `last_checked_at` | string\|null | Timestamp ISO 8601 de última actualización (null si nunca se actualizó) |
| `is_mandatory` | bool | Indica si es fuente obligatoria (true) o adicional (false) |
| `created_at` | string | Timestamp ISO 8601 de creación de la fuente |
| `updated_at` | string | Timestamp ISO 8601 de última modificación |

#### Errores

| Código | Descripción |
|--------|-------------|
| 401 | Usuario no autenticado |
| 403 | Usuario sin permisos (requiere rol admin o colaborador) |
| 404 | Producto no encontrado |

#### Ejemplos de Uso

**Obtener fuentes de un producto**:
```bash
GET /market/products/123/sources
```

**Respuesta cuando el producto no tiene fuentes**:
```json
{
  "product_id": 123,
  "product_name": "Producto Sin Fuentes",
  "sale_price": null,
  "market_price_reference": null,
  "mandatory": [],
  "additional": []
}
```

#### Comportamiento

1. **Separación de fuentes**: Las fuentes se separan automáticamente según el campo `is_mandatory`
2. **Orden**: Las fuentes obligatorias aparecen primero, ordenadas por fecha de creación ASC
3. **Preferred name**: Usa `sku_custom` si está definido, sino usa `name`
4. **Validación**: Retorna 404 si el producto no existe

---

## Lógica de Negocio

### Nombre Preferido (preferred_name)

El campo `preferred_name` se determina con la siguiente prioridad:

1. Si `sku_custom` está definido → usar `sku_custom`
2. Si no → usar `name` (nombre base del producto)

Esto permite que productos con SKU personalizado muestren ese SKU como nombre principal en la UI.

### Precio de Venta (sale_price)

Proviene del campo `sale_price` de la tabla `canonical_products`.

Este precio puede ser actualizado mediante:
- Endpoint `PATCH /products-ex/products/{id}/sale-price`
- Desde la UI del módulo Mercado (modal de detalle)

### Valor de Mercado de Referencia (market_price_reference)

Proviene del campo `market_price_reference` de la tabla `products` o `canonical_products`.

Este valor puede ser:
- Ingresado manualmente desde la UI
- Corregido cuando el scraping automático falla
- Usado como referencia cuando no hay fuentes automáticas

Endpoint para actualizar: `PATCH /products/{id}/market-reference` *(pendiente Etapa 2)*

### Rango de Mercado (market_price_min / market_price_max)

**Estado actual**: Retorna `null` (pendiente implementación Etapa 2)

**Implementación futura** (Etapa 2):
- Se calculará desde la tabla `market_sources`
- Tomará el mínimo y máximo de `last_price` de fuentes activas
- Se actualizará automáticamente cuando se ejecute scraping

### Última Actualización (last_market_update)

**Estado actual**: Retorna `null` (pendiente implementación Etapa 2)

**Implementación futura** (Etapa 2):
- Timestamp de la última vez que se actualizaron las fuentes
- Proviene del campo `updated_at` de `market_sources` más reciente
- Se usa para determinar "frescura" de los datos

### Filtro por Proveedor

El filtro `supplier_id` busca productos canónicos que tengan al menos una equivalencia (`ProductEquivalence`) con el proveedor especificado.

Un producto canónico puede tener múltiples proveedores. El campo `supplier_id` retornado en el item corresponde al primer proveedor encontrado (orden de inserción).

### Orden de Resultados

Los resultados se ordenan alfabéticamente por `name` (case-insensitive) del producto canónico.

---

### PATCH /market/products/{product_id}/sale-price

Actualiza el precio de venta de un producto canónico.

**Roles permitidos**: `admin`, `colaborador`

**Descripción**:
Permite modificar el precio de venta (`sale_price`) de un producto desde la UI del módulo Mercado. Valida que el precio sea positivo y actualiza automáticamente el timestamp `updated_at`.

#### Parámetros Path

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `product_id` | int | Sí | ID del producto canónico a actualizar |

#### Request Body

```json
{
  "sale_price": 150.00
}
```

| Campo | Tipo | Requerido | Validaciones | Descripción |
|-------|------|-----------|--------------|-------------|
| `sale_price` | float | Sí | > 0, ≤ 999999999 | Nuevo precio de venta |

**Validaciones**:
- El precio debe ser mayor a 0
- El precio debe ser menor o igual a 999,999,999 (límite superior)
- El producto debe existir en la base de datos

#### Respuesta Exitosa (200 OK)

```json
{
  "product_id": 123,
  "product_name": "Cámara Digital Canon EOS",
  "sale_price": 150.00,
  "previous_price": 100.00,
  "updated_at": "2025-11-11T18:30:00Z"
}
```

#### Campos de Respuesta

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `product_id` | int | ID del producto actualizado |
| `product_name` | string | Nombre preferido del producto (usa `sku_custom` si existe, sino `name`) |
| `sale_price` | float | Nuevo precio de venta aplicado |
| `previous_price` | float\|null | Precio anterior (null si el producto no tenía precio) |
| `updated_at` | string | Timestamp ISO 8601 de la actualización |

#### Errores

| Código | Descripción | Ejemplo de Respuesta |
|--------|-------------|----------------------|
| 401 | Usuario no autenticado | `{"detail": "Not authenticated"}` |
| 403 | Usuario sin permisos (requiere admin/colaborador) | `{"detail": "Forbidden"}` |
| 404 | Producto no encontrado | `{"detail": "Producto con ID 999 no encontrado"}` |
| 422 | Validación fallida (precio inválido) | `{"detail": [{"msg": "El precio de venta debe ser mayor a cero"}]}` |

#### Ejemplos de Uso

**Actualizar precio exitoso**:
```bash
PATCH /market/products/123/sale-price
Content-Type: application/json

{
  "sale_price": 1500.00
}

# Response 200 OK
{
  "product_id": 123,
  "product_name": "CUSTOM_SKU_001",
  "sale_price": 1500.00,
  "previous_price": 1200.00,
  "updated_at": "2025-11-11T18:30:00.123456Z"
}
```

**Actualizar precio desde NULL**:
```bash
PATCH /market/products/456/sale-price
Content-Type: application/json

{
  "sale_price": 200.00
}

# Response 200 OK
{
  "product_id": 456,
  "product_name": "Producto Sin Precio",
  "sale_price": 200.00,
  "previous_price": null,
  "updated_at": "2025-11-11T18:35:00.123456Z"
}
```

**Error: Precio negativo**:
```bash
PATCH /market/products/123/sale-price
Content-Type: application/json

{
  "sale_price": -50.00
}

# Response 422 Unprocessable Entity
{
  "detail": [
    {
      "type": "value_error",
      "msg": "El precio de venta debe ser mayor a cero",
      "loc": ["body", "sale_price"]
    }
  ]
}
```

**Error: Producto no existe**:
```bash
PATCH /market/products/999999/sale-price
Content-Type: application/json

{
  "sale_price": 100.00
}

# Response 404 Not Found
{
  "detail": "Producto con ID 999999 no encontrado"
}
```

#### Notas de Implementación

- **Conversión de tipos**: El endpoint convierte el precio de `float` (Pydantic) a `Decimal` (SQLAlchemy) para mantener precisión financiera.
- **Timestamp automático**: El campo `updated_at` se actualiza automáticamente al guardar.
- **Preferred name**: La respuesta usa `sku_custom` si está definido, de lo contrario usa `name` del producto.
- **Previous price**: Se guarda el valor anterior antes de actualizar, permitiendo comparación en la UI.

---

### PATCH /market/products/{product_id}/market-reference

Actualiza el precio de mercado de referencia de un producto canónico.

**Roles permitidos**: `admin`, `colaborador`

**Descripción**:
Permite establecer o corregir manualmente el valor de mercado de referencia (`market_price_reference`) de un producto. Este valor se usa para comparar con el precio de venta y detectar desviaciones. Útil cuando no hay datos automáticos de mercado disponibles o se requiere corrección manual.

#### Parámetros Path

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `product_id` | int | Sí | ID del producto canónico a actualizar |

#### Request Body

```json
{
  "market_price_reference": 250.00
}
```

| Campo | Tipo | Requerido | Validaciones | Descripción |
|-------|------|-----------|--------------|-------------|
| `market_price_reference` | float | Sí | >= 0, ≤ 999999999 | Nuevo precio de mercado de referencia |

**Validaciones**:
- El precio debe ser mayor o igual a 0 (permite 0 para indicar "sin valor de mercado")
- El precio debe ser menor o igual a 999,999,999 (límite superior)
- El producto debe existir en la base de datos

#### Respuesta Exitosa (200 OK)

```json
{
  "product_id": 123,
  "product_name": "Cámara Digital Canon EOS",
  "market_price_reference": 250.00,
  "previous_market_price": 200.00,
  "market_price_updated_at": "2025-11-11T19:30:00Z"
}
```

#### Campos de Respuesta

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `product_id` | int | ID del producto actualizado |
| `product_name` | string | Nombre preferido del producto (usa `sku_custom` si existe, sino `name`) |
| `market_price_reference` | float | Nuevo precio de mercado aplicado |
| `previous_market_price` | float\|null | Precio de mercado anterior (null si no tenía valor) |
| `market_price_updated_at` | string | Timestamp ISO 8601 de la actualización del precio de mercado |

#### Errores

| Código | Descripción | Ejemplo de Respuesta |
|--------|-------------|----------------------|
| 401 | Usuario no autenticado | `{"detail": "Not authenticated"}` |
| 403 | Usuario sin permisos (requiere admin/colaborador) | `{"detail": "Forbidden"}` |
| 404 | Producto no encontrado | `{"detail": "Producto con ID 999 no encontrado"}` |
| 422 | Validación fallida (precio inválido) | `{"detail": [{"msg": "El precio de mercado debe ser mayor o igual a cero"}]}` |

#### Ejemplos de Uso

**Actualizar precio de mercado exitoso**:
```bash
PATCH /market/products/123/market-reference
Content-Type: application/json

{
  "market_price_reference": 250.00
}

# Response 200 OK
{
  "product_id": 123,
  "product_name": "CUSTOM_SKU_002",
  "market_price_reference": 250.00,
  "previous_market_price": 200.00,
  "market_price_updated_at": "2025-11-11T19:30:00.123456Z"
}
```

**Establecer precio desde NULL (primera vez)**:
```bash
PATCH /market/products/456/market-reference
Content-Type: application/json

{
  "market_price_reference": 300.00
}

# Response 200 OK
{
  "product_id": 456,
  "product_name": "Producto Sin Precio Mercado",
  "market_price_reference": 300.00,
  "previous_market_price": null,
  "market_price_updated_at": "2025-11-11T19:35:00.123456Z"
}
```

**Establecer precio a cero (sin valor de mercado)**:
```bash
PATCH /market/products/789/market-reference
Content-Type: application/json

{
  "market_price_reference": 0.0
}

# Response 200 OK
{
  "product_id": 789,
  "product_name": "Producto Descontinuado",
  "market_price_reference": 0.0,
  "previous_market_price": 150.00,
  "market_price_updated_at": "2025-11-11T19:40:00.123456Z"
}
```

**Error: Precio negativo**:
```bash
PATCH /market/products/123/market-reference
Content-Type: application/json

{
  "market_price_reference": -50.00
}

# Response 422 Unprocessable Entity
{
  "detail": [
    {
      "type": "value_error",
      "msg": "El precio de mercado debe ser mayor o igual a cero",
      "loc": ["body", "market_price_reference"]
    }
  ]
}
```

**Error: Producto no existe**:
```bash
PATCH /market/products/999999/market-reference
Content-Type: application/json

{
  "market_price_reference": 100.00
}

# Response 404 Not Found
{
  "detail": "Producto con ID 999999 no encontrado"
}
```

#### Notas de Implementación

- **Conversión de tipos**: El endpoint convierte el precio de `float` (Pydantic) a `Decimal` (SQLAlchemy) para mantener precisión financiera.
- **Timestamp dedicado**: El campo `market_price_updated_at` se actualiza para rastrear específicamente cuándo se modificó el precio de mercado.
- **Updated_at general**: También se actualiza `updated_at` del producto para reflejar el cambio global.
- **Preferred name**: La respuesta usa `sku_custom` si está definido, de lo contrario usa `name` del producto.
- **Previous price**: Se guarda el valor anterior antes de actualizar, permitiendo auditoría de cambios.
- **Valor cero permitido**: A diferencia de `sale_price`, `market_price_reference` permite 0 para indicar "sin valor de mercado conocido".

---

### POST /market/products/{product_id}/refresh-market

Inicia el proceso asíncrono de actualización de precios de mercado (scraping) para un producto.

**Roles permitidos**: `admin`, `colaborador`

**Descripción**:
Encola una tarea de scraping en segundo plano para actualizar los precios de todas las fuentes de mercado asociadas al producto. El endpoint retorna inmediatamente con status `202 Accepted` mientras el worker procesa las fuentes en background.

El proceso del worker:
1. Obtiene todas las fuentes de mercado del producto
2. Ejecuta scraping de cada fuente (parseo de sitios externos)
3. Actualiza `last_price` y `last_checked_at` en cada fuente
4. Calcula `market_price_reference` como promedio de precios obtenidos
5. Actualiza `market_price_updated_at` del producto

**⚠️ Importante**: El scraping puede demorar varios segundos. La UI debe mostrar un indicador de carga y refrescar los datos periódicamente.

#### Parámetros Path

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `product_id` | int | Sí | ID del producto canónico a actualizar |

#### Request Body

No requiere body.

#### Respuesta Exitosa (202 Accepted)

```json
{
  "status": "processing",
  "message": "Actualización de precios de mercado iniciada para producto 123",
  "product_id": 123,
  "job_id": "abc123-def456"
}
```

#### Campos de Respuesta

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `status` | string | Estado del proceso: `"processing"` (tarea encolada) |
| `message` | string | Mensaje descriptivo de confirmación |
| `product_id` | int | ID del producto que será actualizado |
| `job_id` | string\|null | ID del job en Dramatiq (si disponible, para tracking futuro) |

#### Errores

| Código | Descripción | Ejemplo de Respuesta |
|--------|-------------|----------------------|
| 401 | Usuario no autenticado | `{"detail": "Not authenticated"}` |
| 403 | Usuario sin permisos (requiere admin/colaborador) | `{"detail": "Forbidden"}` |
| 404 | Producto no encontrado | `{"detail": "Producto con ID 999 no encontrado"}` |
| 500 | Error al encolar tarea | `{"detail": "Error al encolar tarea de actualización: ..."}` |

#### Ejemplos de Uso

**Iniciar actualización exitosa**:
```bash
POST /market/products/123/refresh-market
# No requiere body

# Response 202 Accepted
{
  "status": "processing",
  "message": "Actualización de precios de mercado iniciada para producto 123",
  "product_id": 123,
  "job_id": "abc123-def456-789ghi"
}
```

**Producto sin fuentes configuradas**:
```bash
POST /market/products/456/refresh-market

# Response 202 Accepted (acepta pero worker reportará 0 fuentes)
{
  "status": "processing",
  "message": "Actualización de precios de mercado iniciada para producto 456",
  "product_id": 456,
  "job_id": "xyz789-abc123"
}
```

**Error: Producto no existe**:
```bash
POST /market/products/999999/refresh-market

# Response 404 Not Found
{
  "detail": "Producto con ID 999999 no encontrado"
}
```

#### Comportamiento del Worker

**Worker**: `workers.market_scraping.refresh_market_prices_task`

**Cola Dramatiq**: `market` (separada de `images` para mejor organización)

El worker ejecuta las siguientes acciones:

1. **Validación**: Verifica que el producto exista
2. **Obtención de fuentes**: Query a `market_sources` filtrando por `product_id`
3. **Scraping por fuente**: Procesa cada fuente individualmente con manejo robusto de errores:
   - **Scraping estático** (requests + BeautifulSoup) para páginas HTML estándar
   - **Scraping dinámico** (Playwright headless) para páginas con JavaScript
   - Si una fuente falla, continúa con las demás (tolerancia a fallos parciales)
4. **Normalización de precios**: Detecta moneda (ARS, USD, EUR, etc.) y convierte a Decimal
5. **Actualización de precios**:
   - Si scraping exitoso: actualiza `last_price` y `last_checked_at`
   - Si falla: solo actualiza `last_checked_at` (marca intento)
6. **Cálculo de referencia**: Calcula promedio de precios obtenidos → `market_price_reference`
7. **Timestamps**: Actualiza `market_price_updated_at` y `updated_at` del producto
8. **Log detallado**: Registra resultado con contexto completo (fuentes exitosas/fallidas, errores específicos)

**Timeout**: 5 minutos por tarea  
**Reintentos**: Máximo 3 reintentos si falla completamente (fallos parciales no causan retry)

#### Iniciar el Worker

El worker de scraping de mercado requiere Redis y se ejecuta mediante Dramatiq:

**Opción 1 - Worker específico de mercado**:
```bash
# Windows
scripts\start_worker_market.cmd

# Linux/Mac
python -m dramatiq workers.market_scraping --processes 1 --threads 2 --queues market
```

**Opción 2 - Worker multi-cola (images + market)**:
```bash
# Windows
scripts\start_worker_all.cmd

# Linux/Mac
python -m dramatiq services.jobs.images workers.market_scraping --processes 1 --threads 3 --queues images,market
```

**Opción 3 - Modo desarrollo sin Redis**:

---

### POST /market/products/batch-refresh

Inicia el proceso asíncrono de actualización de precios de mercado (scraping) para múltiples productos en un solo request.

**Roles permitidos**: `admin`, `colaborador`

**Descripción**:
Encola tareas de scraping en segundo plano para actualizar los precios de todas las fuentes de mercado asociadas a cada producto seleccionado. El endpoint retorna inmediatamente con status `202 Accepted` mientras los workers procesan las fuentes en background.

Este endpoint es útil para actualizar múltiples productos seleccionados desde la UI del módulo Mercado, evitando múltiples requests individuales.

**Límites**:
- Mínimo: 1 producto
- Máximo: 100 productos por request

El proceso del worker para cada producto es idéntico al endpoint individual (`POST /market/products/{product_id}/refresh-market`).

**⚠️ Importante**: El scraping puede demorar varios segundos por producto. La UI debe mostrar un indicador de carga y refrescar los datos periódicamente.

#### Request Body

```json
{
  "product_ids": [123, 456, 789]
}
```

#### Campos del Request

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `product_ids` | array[int] | Sí | Lista de IDs de productos canónicos a actualizar (1-100 items) |

#### Respuesta Exitosa (202 Accepted)

```json
{
  "total_requested": 3,
  "enqueued": 2,
  "not_found": 1,
  "errors": 0,
  "results": [
    {
      "product_id": 123,
      "status": "enqueued",
      "message": "Actualización de precios iniciada para producto 123",
      "job_id": "abc123-def456"
    },
    {
      "product_id": 456,
      "status": "enqueued",
      "message": "Actualización de precios iniciada para producto 456",
      "job_id": "xyz789-abc123"
    },
    {
      "product_id": 789,
      "status": "not_found",
      "message": "Producto 789 no encontrado",
      "job_id": null
    }
  ]
}
```

#### Campos de Respuesta

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `total_requested` | int | Total de productos solicitados |
| `enqueued` | int | Productos encolados exitosamente |
| `not_found` | int | Productos no encontrados en la base de datos |
| `errors` | int | Productos con error al encolar (excepciones inesperadas) |
| `results` | array[BatchRefreshMarketItem] | Resultados detallados por producto |

#### BatchRefreshMarketItem

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `product_id` | int | ID del producto procesado |
| `status` | string | Estado: `"enqueued"`, `"not_found"`, o `"error"` |
| `message` | string | Mensaje descriptivo del resultado |
| `job_id` | string\|null | ID del job en Dramatiq (solo si status es "enqueued") |

#### Errores

| Código | Descripción | Ejemplo de Respuesta |
|--------|-------------|----------------------|
| 401 | Usuario no autenticado | `{"detail": "Not authenticated"}` |
| 403 | Usuario sin permisos (requiere admin/colaborador) | `{"detail": "Forbidden"}` |
| 422 | Lista vacía o excede límite máximo | `{"detail": "Máximo 100 productos por request"}` |
| 502 | Servicio de scraping no disponible | `{"detail": "Servicio de actualización de precios no disponible"}` |
| 500 | Error interno del servidor | `{"detail": "Error interno al iniciar actualización de precios"}` |

#### Ejemplos de Uso

**Actualización masiva exitosa**:
```bash
POST /market/products/batch-refresh
Content-Type: application/json

{
  "product_ids": [123, 456, 789]
}

# Response 202 Accepted
{
  "total_requested": 3,
  "enqueued": 3,
  "not_found": 0,
  "errors": 0,
  "results": [
    {
      "product_id": 123,
      "status": "enqueued",
      "message": "Actualización de precios iniciada para producto 123",
      "job_id": "abc123-def456"
    },
    {
      "product_id": 456,
      "status": "enqueued",
      "message": "Actualización de precios iniciada para producto 456",
      "job_id": "xyz789-abc123"
    },
    {
      "product_id": 789,
      "status": "enqueued",
      "message": "Actualización de precios iniciada para producto 789",
      "job_id": "def456-ghi789"
    }
  ]
}
```

**Algunos productos no encontrados**:
```bash
POST /market/products/batch-refresh

{
  "product_ids": [123, 999999, 456]
}

# Response 202 Accepted
{
  "total_requested": 3,
  "enqueued": 2,
  "not_found": 1,
  "errors": 0,
  "results": [
    {
      "product_id": 123,
      "status": "enqueued",
      "message": "Actualización de precios iniciada para producto 123",
      "job_id": "abc123-def456"
    },
    {
      "product_id": 999999,
      "status": "not_found",
      "message": "Producto 999999 no encontrado",
      "job_id": null
    },
    {
      "product_id": 456,
      "status": "enqueued",
      "message": "Actualización de precios iniciada para producto 456",
      "job_id": "xyz789-abc123"
    }
  ]
}
```

**Error: Lista vacía**:
```bash
POST /market/products/batch-refresh

{
  "product_ids": []
}

# Response 422 Unprocessable Entity
{
  "detail": "Debe proporcionar al menos un producto"
}
```

**Error: Excede límite máximo**:
```bash
POST /market/products/batch-refresh

{
  "product_ids": [1, 2, 3, ..., 101]  # 101 productos
}

# Response 422 Unprocessable Entity
{
  "detail": "Máximo 100 productos por request"
}
```

#### Comportamiento del Worker

Cada producto válido se encola como una tarea independiente en Dramatiq. El comportamiento del worker es idéntico al endpoint individual (`POST /market/products/{product_id}/refresh-market`).

**Worker**: `workers.market_scraping.refresh_market_prices_task`  
**Cola Dramatiq**: `market`

Las tareas se procesan en paralelo según la configuración del worker (número de threads/procesos).

#### Notas de Implementación

- **Tolerancia a fallos parciales**: Si un producto falla al encolar, los demás continúan procesándose
- **Validación temprana**: Se valida existencia de cada producto antes de encolar
- **Logging detallado**: Se registra cada producto procesado con su resultado
- **Idempotencia**: Enviar el mismo producto múltiples veces encola múltiples tareas (comportamiento esperado para re-scraping)

---
```bash
# Usar StubBroker (cola en memoria, sin persistencia)
set RUN_INLINE_JOBS=1
python services/main.py
```

**Variables de entorno requeridas**:
- `REDIS_URL`: URL de conexión a Redis (default: `redis://localhost:6379/0`)
- `DB_URL`: URL de conexión a la base de datos (requerida para el worker)

**Logs**:
- Worker market: `logs/worker_market.log`
- Worker multi-cola: `logs/worker_all.log`
- Logging detallado con prefijo `[scraping]` para filtrar con grep/findstr

#### Monitoreo del Proceso

Actualmente el endpoint retorna `202 Accepted` sin mecanismo de polling integrado. Opciones para la UI:

**Opción 1 - Polling simple**:
```javascript
// Llamar cada 5 segundos a GET /market/products/{id}/sources
// Verificar cambio en last_checked_at de las fuentes
setInterval(() => {
  fetchProductSources(productId);
}, 5000);
```

**Opción 2 - Optimistic update**:
```javascript
// Mostrar spinner inmediatamente
// Esperar 10-15 segundos y refrescar
await refreshMarketPrices(productId);
showSpinner();
setTimeout(() => {
  fetchProductSources(productId);
  hideSpinner();
}, 12000);
```

**Opción 3 - WebSockets** *(futuro)*:
```javascript
// Suscribirse a eventos de jobs específicos
socket.on(`job:${jobId}:completed`, (result) => {
  fetchProductSources(productId);
  showToast(`${result.sources_updated} fuentes actualizadas`);
});
```

#### Notas de Implementación

- **Asíncrono**: El endpoint no espera el resultado del scraping, retorna inmediatamente
- **Non-blocking**: La UI no se congela durante el proceso
- **Idempotente**: Se puede llamar múltiples veces sin efectos adversos (última ejecución prevalece)
- **Scraping placeholder**: La lógica actual de scraping es un placeholder, pendiente implementar parsers específicos por sitio
- **Cálculo de referencia**: El promedio puede reemplazarse por mediana u otra métrica según necesidad
- **Manejo de errores**: Si una fuente falla, las demás continúan procesándose
- **Redis requerido**: En producción requiere Redis para Dramatiq (en dev usa StubBroker)

#### Futuras Mejoras

- Implementar parsers específicos (MercadoLibre, Amazon, SantaPlanta, etc.)
- Integración con MCP Web Search para descubrimiento de precios
- Sistema de polling o WebSockets para notificar completitud
- Rate limiting por producto (evitar spam de actualizaciones)
- Cache de resultados recientes (no re-scrapear si < 1 hora)
- Métricas: latencia por fuente, tasa de éxito, precios históricos

---

### POST /market/products/{id}/sources

Agregar nueva fuente de precio de mercado a un producto.

**Roles permitidos**: `admin`, `colaborador`

**Descripción**:
Permite agregar una fuente de precio personalizada para un producto. La URL debe ser válida (formato http/https) y única por producto.

#### Parámetros Path

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `id` | int | Sí | ID del producto canónico |

#### Parámetros Body

```json
{
  "source_name": "MercadoLibre",
  "url": "https://mercadolibre.com.ar/producto-xyz",
  "is_mandatory": false
}
```

| Campo | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `source_name` | string | Sí | - | Nombre identificatorio (1-200 caracteres) |
| `url` | string | Sí | - | URL de la fuente (debe incluir esquema http/https, 1-500 caracteres) |
| `is_mandatory` | boolean | No | false | Si es fuente obligatoria para cálculo de precios |

#### Validaciones

- **URL formato**: Debe incluir esquema (http/https) y dominio válido
- **URL única**: No puede duplicarse la URL para el mismo producto (409 Conflict)
- **Producto existe**: El producto con `id` debe existir (404 Not Found)
- **Sanitización**: Longitudes mínimas/máximas para evitar inyección

#### Respuesta Exitosa (201 Created)

```json
{
  "id": 42,
  "product_id": 123,
  "source_name": "MercadoLibre",
  "url": "https://mercadolibre.com.ar/producto-xyz",
  "is_mandatory": false,
  "last_price": null,
  "last_checked_at": null,
  "created_at": "2025-11-12T10:30:00Z"
}
```

**Notas**:
- `last_price` y `last_checked_at` se crean como `null` (se poblan con `POST refresh-market`)
- `id` es el ID único de la fuente (usar para DELETE)
- `created_at` es timestamp de creación

#### Errores

| Código | Descripción | Ejemplo |
|--------|-------------|---------|
| 404 | Producto no encontrado | `"Producto con ID 999 no encontrado"` |
| 409 | URL duplicada | `"Ya existe una fuente con la URL ... para este producto"` |
| 422 | Validación falló | `"URL debe incluir esquema (http/https) y dominio"` |

#### Ejemplos

**Agregar fuente exitosamente**:
```bash
POST /market/products/123/sources
Content-Type: application/json
Authorization: Bearer <token_colaborador>

{
  "source_name": "Amazon",
  "url": "https://www.amazon.com/product/xyz",
  "is_mandatory": true
}

# Response 201 Created
{
  "id": 15,
  "product_id": 123,
  "source_name": "Amazon",
  "url": "https://www.amazon.com/product/xyz",
  "is_mandatory": true,
  "last_price": null,
  "last_checked_at": null,
  "created_at": "2025-11-12T10:35:00Z"
}
```

**Error: Producto no existe**:
```bash
POST /market/products/999999/sources

# Response 404 Not Found
{
  "detail": "Producto con ID 999999 no encontrado"
}
```

**Error: URL duplicada**:
```bash
POST /market/products/123/sources
{
  "source_name": "Otra Fuente",
  "url": "https://www.amazon.com/product/xyz"
}

# Response 409 Conflict
{
  "detail": "Ya existe una fuente con la URL https://www.amazon.com/product/xyz para este producto"
}
```

**Error: URL inválida (sin esquema)**:
```bash
POST /market/products/123/sources
{
  "source_name": "Fuente Inválida",
  "url": "example.com/producto"
}

# Response 422 Unprocessable Entity
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "url"],
      "msg": "URL debe incluir esquema (http/https) y dominio",
      "input": "example.com/producto"
    }
  ]
}
```

---

### DELETE /market/sources/{source_id}

Eliminar fuente de precio de mercado.

**Roles permitidos**: `admin`, `colaborador`

**Descripción**:
Elimina permanentemente una fuente de precio. No afecta otras fuentes del mismo producto. No hay recuperación posible (eliminación hard).

#### Parámetros Path

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `source_id` | int | Sí | ID de la fuente a eliminar |

#### Respuesta Exitosa (204 No Content)

```
(sin contenido)
```

**Notas**:
- Status code `204` indica eliminación exitosa
- No retorna body (sin contenido)
- La fuente se elimina permanentemente de la base de datos
- Otras fuentes del mismo producto no se ven afectadas

#### Errores

| Código | Descripción | Ejemplo |
|--------|-------------|---------|
| 404 | Fuente no encontrada | `"Fuente con ID 999 no encontrada"` |

#### Ejemplos

**Eliminar fuente exitosamente**:
```bash
DELETE /market/sources/42
Authorization: Bearer <token_colaborador>

# Response 204 No Content
(sin contenido)
```

**Error: Fuente no existe**:
```bash
DELETE /market/sources/999999

# Response 404 Not Found
{
  "detail": "Fuente con ID 999999 no encontrada"
}
```

#### Notas de Implementación

- **Eliminación permanente**: No hay soft delete, la fuente se borra de la tabla
- **Cascade**: Si el producto se elimina, sus fuentes se eliminan automáticamente (ON DELETE CASCADE)
- **No afecta producto**: Eliminar una fuente no modifica `market_price_reference` ni otros campos del producto
- **Re-cálculo manual**: Después de eliminar fuentes, considerar ejecutar `POST refresh-market` para actualizar precios
- **Confirmación en UI**: Recomendado mostrar diálogo de confirmación antes de eliminar

---

### POST /market/products/{id}/discover-sources

Descubre automáticamente nuevas fuentes de precios para un producto usando MCP Web Search.

**Roles permitidos**: `admin`, `colaborador`

**Descripción**:
Consulta el servicio MCP Web Search (DuckDuckGo) para encontrar automáticamente URLs de e-commerce donde aparece el producto. Filtra resultados para retornar solo sitios confiables con indicadores de precio.

#### Parámetros Path

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `id` | int | ID del producto canónico |

#### Parámetros Query

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `max_results` | int | No | 15 | Máximo de resultados a solicitar al buscador (5-30) |

#### Respuesta Exitosa (200 OK)

```json
{
  "success": true,
  "query": "Sustrato de coco 20L precio Sustratos comprar",
  "total_results": 12,
  "valid_sources": 3,
  "sources": [
    {
      "url": "https://www.santaplanta.com/shop/products/sustrato-coco-20l",
      "title": "Sustrato de Coco 20L - Santa Planta",
      "snippet": "Sustrato premium 100% fibra de coco. Precio: $2500. Envío gratis."
    },
    {
      "url": "https://articulo.mercadolibre.com.ar/MLA-123456-sustrato-coco",
      "title": "Sustrato De Coco 20 Litros Indoor",
      "snippet": "Comprar en cuotas sin interés. $2300. Stock disponible."
    }
  ],
  "error": null
}
```

#### Campos de Respuesta

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `success` | bool | Si el descubrimiento fue exitoso |
| `query` | string | Query de búsqueda utilizada (nombre + categoría + "precio comprar") |
| `total_results` | int | Total de resultados obtenidos del buscador |
| `valid_sources` | int | Cantidad de fuentes válidas filtradas |
| `sources` | array | Lista de fuentes descubiertas (máximo 10) |
| `sources[].url` | string | URL de la fuente descubierta |
| `sources[].title` | string | Título del resultado de búsqueda |
| `sources[].snippet` | string | Snippet con contexto (puede contener precio) |
| `error` | string\|null | Mensaje de error si hubo fallo |

#### Errores

| Código | Descripción | Ejemplo |
|--------|-------------|---------|
| 404 | Producto no encontrado | `"Producto con ID 999 no encontrado"` |
| 500 | Error del MCP Web Search | `{"success": false, "error": "network_failure"}` |

#### Proceso de Descubrimiento

1. **Construcción de query**:
   - Combina: nombre del producto + categoría + "precio" + "comprar"
   - Ejemplo: `"Sustrato de coco 20L precio Sustratos comprar"`

2. **Consulta MCP Web Search**:
   - Solicita hasta `max_results` resultados a DuckDuckGo HTML
   - Timeout: 10 segundos

3. **Filtrado de resultados**:
   - ✅ **Dominios confiables**: MercadoLibre, SantaPlanta, CultivarGrowShop, etc.
   - ✅ **Indicadores de precio**: `$`, "precio", "comprar", "ARS", etc.
   - ❌ **URLs excluidas**: imágenes (`.jpg`, `.png`), estáticas (`/static/`)
   - ❌ **Duplicados**: URLs ya existentes para el producto

4. **Límite de retorno**: Máximo 10 fuentes por respuesta

#### Dominios Reconocidos

**Marketplaces**:
- `mercadolibre.com.ar`, `mercadolibre.com`, `mlstatic.com`

**Growshops**:
- `santaplanta.com`, `cultivargrowshop.com`, `growbarato.net`
- `indoorgrow.com.ar`, `tricomas.com.ar`, `cannabisargento.com.ar`
- Cualquier dominio con "growshop" en la URL

**Retailers**:
- `easy.com.ar`, `sodimac.com.ar`, `farmacity.com`

#### Ejemplos

**Descubrir fuentes para producto**:
```bash
POST /market/products/123/discover-sources?max_results=20
Authorization: Bearer <token_admin>

# Response 200 OK
{
  "success": true,
  "query": "Sustrato de coco precio comprar",
  "total_results": 15,
  "valid_sources": 4,
  "sources": [
    {
      "url": "https://www.santaplanta.com/sustrato-coco",
      "title": "Sustrato Coco 20L",
      "snippet": "Precio $2500 con envío"
    }
  ]
}
```

**Producto sin fuentes válidas**:
```bash
POST /market/products/456/discover-sources

# Response 200 OK
{
  "success": true,
  "query": "Producto Especial precio comprar",
  "total_results": 8,
  "valid_sources": 0,
  "sources": [],
  "error": null
}
```

**Producto no existe**:
```bash
POST /market/products/999999/discover-sources

# Response 404 Not Found
{
  "detail": "Producto con ID 999999 no encontrado"
}
```

**Error del MCP Web Search**:
```bash
POST /market/products/123/discover-sources

# Response 200 OK (error en el resultado, no HTTP error)
{
  "success": false,
  "query": "Producto precio comprar",
  "total_results": 0,
  "valid_sources": 0,
  "sources": [],
  "error": "network_failure"
}
```

#### Notas de Implementación

- **Sugerencias**: Las fuentes descubiertas son **solo sugerencias**. El usuario debe:
  1. Revisar manualmente cada URL
  2. Verificar que contiene el precio del producto correcto
  3. Agregarla con `POST /market/products/{id}/sources/from-suggestion` si es válida
  
- **No agrega automáticamente**: El endpoint **no** crea registros de `MarketSource`. Solo retorna URLs sugeridas.

- **Dependencias**:
  - Requiere servicio `mcp_web_search` activo
  - Variable `MCP_WEB_SEARCH_URL` (default: `http://mcp_web_search:8002/invoke_tool`)
  
- **Rate limiting**: Considerar limitar llamadas por usuario/producto (ej. 1 descubrimiento cada 5 minutos)

- **Optimizaciones futuras**:
  - Cache de resultados por (producto_name, category) con TTL de 1 hora
  - Scoring por confiabilidad del dominio
  - Detección automática de `source_type` (static vs dynamic)
  - Pre-validación de URLs (HEAD request para verificar 200 OK)

- **UI recomendada**:
  ```
  [Botón: "Buscar fuentes automáticamente"]
  
  → Muestra loading...
  → Lista de URLs sugeridas con:
     - Checkbox para seleccionar
     - Vista previa del snippet
     - Botón "Agregar seleccionadas"
  ```

---

### POST /market/products/{id}/sources/from-suggestion

Agrega una fuente de precio desde una sugerencia del sistema con validación automática de precio.

**Roles permitidos**: `admin`, `colaborador`

**Descripción**:
Permite agregar una URL descubierta automáticamente como fuente de precio. Antes de persistir, el sistema valida que la URL efectivamente contenga un precio.

#### Parámetros Path

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `id` | int | ID del producto canónico |

#### Request Body

```json
{
  "url": "https://www.santaplanta.com/producto/sustrato-coco",
  "source_name": "Santa Planta",
  "validate_price": true,
  "source_type": "static",
  "is_mandatory": false
}
```

| Campo | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `url` | string | Sí | - | URL de la fuente sugerida |
| `source_name` | string | No | (auto) | Nombre de la fuente (se detecta del dominio si falta) |
| `validate_price` | bool | No | true | Si True, valida que exista precio antes de agregar |
| `source_type` | string | No | "static" | Tipo de fuente: "static" o "dynamic" |
| `is_mandatory` | bool | No | false | Si es fuente obligatoria para cálculo de rango |

#### Respuesta Exitosa (201 Created)

```json
{
  "success": true,
  "source_id": 42,
  "message": "Fuente 'Santa Planta' agregada exitosamente",
  "validation_result": {
    "is_valid": true,
    "reason": "price_found"
  }
}
```

#### Campos de Respuesta

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `success` | bool | Si la fuente se agregó exitosamente |
| `source_id` | int\|null | ID de la fuente creada (null si falló) |
| `message` | string | Mensaje descriptivo del resultado |
| `validation_result` | object\|null | Resultado de la validación de precio |
| `validation_result.is_valid` | bool | Si la validación fue exitosa |
| `validation_result.reason` | string | Razón de validación ("price_found", "high_confidence", etc.) |

#### Proceso de Validación

**1. Dominios de alta confianza** (aprobación automática):
- MercadoLibre (`.mercadolibre.com.ar`, `.mercadolibre.com`)
- SantaPlanta (`.santaplanta.com`)
- CultivarGrowShop (`.cultivargrowshop.com`)

**2. Otros dominios** (requieren detección de precio):
- Scraping rápido de la URL (timeout 10s)
- Búsqueda de patrones:
  - Símbolos: `$`, `ARS`
  - Palabras: "precio", "comprar", "oferta"
  - Meta tags: `<meta property="product:price:amount">`
  - Clases CSS: `.price`, `.precio`, `.valor`

**3. Validación rápida** (`validate_price=false`):
- Solo verifica disponibilidad (HEAD request)
- Útil para fuentes que requieren JS o login
- **Usar con precaución**: puede agregar URLs sin precio

#### Errores

| Código | Descripción | Ejemplo |
|--------|-------------|---------|
| 400 | URL duplicada o precio no detectado | `"No se pudo validar la fuente: price_not_found"` |
| 404 | Producto no encontrado | `"Producto con ID 999 no encontrado"` |
| 500 | Error de validación o red | `"Error al validar la fuente: Timeout"` |

#### Ejemplos

**Agregar fuente con validación**:
```bash
POST /market/products/123/sources/from-suggestion
Authorization: Bearer <token_admin>
Content-Type: application/json

{
  "url": "https://www.santaplanta.com/sustrato-coco",
  "validate_price": true
}

# Response 201 Created
{
  "success": true,
  "source_id": 42,
  "message": "Fuente 'Santaplanta.com' agregada exitosamente",
  "validation_result": {
    "is_valid": true,
    "reason": "high_confidence"
  }
}
```

**Fuente sin precio detectado**:
```bash
POST /market/products/123/sources/from-suggestion
Content-Type: application/json

{
  "url": "https://example.com/producto",
  "validate_price": true
}

# Response 201 Created (pero success=false)
{
  "success": false,
  "source_id": null,
  "message": "No se pudo validar la fuente: price_not_found",
  "validation_result": {
    "is_valid": false,
    "reason": "price_not_found"
  }
}
```

**Agregar sin validación (skip)**:
```bash
POST /market/products/123/sources/from-suggestion
Content-Type: application/json

{
  "url": "https://example.com/producto",
  "source_name": "Example Store",
  "validate_price": false,
  "source_type": "dynamic"
}

# Response 201 Created
{
  "success": true,
  "source_id": 43,
  "message": "Fuente 'Example Store' agregada exitosamente",
  "validation_result": null
}
```

#### Notas de Implementación

- **Timeouts**:
  - Verificación de disponibilidad (HEAD): 5 segundos
  - Detección de precio (GET + parsing): 10 segundos
  
- **Concurrencia**: Considerar limitar validaciones concurrentes (max 3 por usuario)

- **Cache**: Resultados de validación se pueden cachear por URL con TTL de 30 minutos

- **Logging**: Cada validación se registra con nivel INFO incluyendo:
  - URL validada
  - Resultado (válida/inválida)
  - Razón (reason)
  - Tiempo de ejecución

- **Flujo recomendado**:
  ```
  1. Usuario obtiene sugerencias con POST /discover-sources
  2. UI muestra lista con checkboxes
  3. Usuario selecciona URLs que parecen relevantes
  4. UI envía cada una a POST /sources/from-suggestion
  5. Backend valida precio automáticamente
  6. Solo se agregan las que tienen precio detectado
  ```

---

### POST /market/products/{id}/sources/batch-from-suggestions

Agrega múltiples fuentes de precio desde sugerencias con validación en paralelo.

**Roles permitidos**: `admin`, `colaborador`

**Descripción**:
Permite agregar múltiples URLs sugeridas en un solo request. Valida cada una en paralelo (limitado a 3 concurrentes) y retorna resumen con éxitos y fallos.

#### Parámetros Path

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `id` | int | ID del producto canónico |

#### Request Body

```json
{
  "sources": [
    {
      "url": "https://www.santaplanta.com/producto",
      "validate_price": true
    },
    {
      "url": "https://articulo.mercadolibre.com.ar/MLA-123456",
      "source_name": "MercadoLibre",
      "validate_price": true
    },
    {
      "url": "https://cultivargrowshop.com/producto",
      "validate_price": false
    }
  ],
  "stop_on_error": false
}
```

| Campo | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `sources` | array | Sí | - | Lista de fuentes a agregar (cada una con estructura de `AddSuggestedSourceRequest`) |
| `stop_on_error` | bool | No | false | Si True, detiene al primer error; si False, continúa con las demás |

#### Respuesta Exitosa (201 Created)

```json
{
  "total_requested": 3,
  "successful": 2,
  "failed": 1,
  "results": [
    {
      "url": "https://www.santaplanta.com/producto",
      "success": true,
      "source_id": 42,
      "message": "Fuente 'Santaplanta.com' agregada exitosamente",
      "validation_result": {
        "is_valid": true,
        "reason": "high_confidence"
      }
    },
    {
      "url": "https://articulo.mercadolibre.com.ar/MLA-123456",
      "success": true,
      "source_id": 43,
      "message": "Fuente 'MercadoLibre' agregada exitosamente",
      "validation_result": {
        "is_valid": true,
        "reason": "high_confidence"
      }
    },
    {
      "url": "https://example.com/producto",
      "success": false,
      "source_id": null,
      "message": "Validación fallida: price_not_found",
      "validation_result": {
        "is_valid": false,
        "reason": "price_not_found"
      }
    }
  ]
}
```

#### Campos de Respuesta

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `total_requested` | int | Total de fuentes solicitadas |
| `successful` | int | Cantidad de fuentes agregadas exitosamente |
| `failed` | int | Cantidad de fuentes que fallaron |
| `results` | array | Resultados individuales por cada fuente |
| `results[].url` | string | URL de la fuente |
| `results[].success` | bool | Si se agregó exitosamente |
| `results[].source_id` | int\|null | ID de la fuente creada (null si falló) |
| `results[].message` | string | Mensaje descriptivo |
| `results[].validation_result` | object\|null | Resultado de validación |

#### Errores

| Código | Descripción |
|--------|-------------|
| 404 | Producto no encontrado |
| 207 Multi-Status | Éxitos parciales (no lanza excepción, ver campo `results`) |

#### Ejemplos

**Agregar múltiples fuentes**:
```bash
POST /market/products/123/sources/batch-from-suggestions
Authorization: Bearer <token_admin>
Content-Type: application/json

{
  "sources": [
    {"url": "https://www.santaplanta.com/p1", "validate_price": true},
    {"url": "https://articulo.mercadolibre.com.ar/MLA-111", "validate_price": true},
    {"url": "https://example.com/p1", "validate_price": true}
  ],
  "stop_on_error": false
}

# Response 201 Created
{
  "total_requested": 3,
  "successful": 2,
  "failed": 1,
  "results": [...]
}
```

**Con stop_on_error=true**:
```bash
POST /market/products/123/sources/batch-from-suggestions
Content-Type: application/json

{
  "sources": [
    {"url": "https://example.com/sin-precio", "validate_price": true},
    {"url": "https://www.santaplanta.com/producto", "validate_price": true}
  ],
  "stop_on_error": true
}

# Response 201 Created (solo procesó primera URL)
{
  "total_requested": 2,
  "successful": 0,
  "failed": 1,
  "results": [
    {
      "url": "https://example.com/sin-precio",
      "success": false,
      "message": "Validación fallida: price_not_found",
      ...
    }
  ]
}
```

#### Notas de Implementación

- **Concurrencia**: Validaciones limitadas a 3 en paralelo para evitar sobrecarga

- **Transacciones**: Se usa `flush()` para obtener IDs sin commit completo hasta procesar todas

- **Commit final**: Solo se hace `commit()` si hubo al menos 1 éxito; si todas fallan, se hace `rollback()`

- **Deduplicación interna**: Si el batch incluye URLs duplicadas, solo se agrega la primera

- **UI recomendada**:
  ```
  [Modal "Agregar fuentes sugeridas"]
  
  ☑ https://santaplanta.com/... (Snippet con precio)
  ☑ https://mercadolibre.com.ar/... (Precio visible)
  ☐ https://example.com/... (Sin indicadores)
  
  [Botón: "Agregar seleccionadas (2)"]
  
  → Loading...
  → Resultado: "2 fuentes agregadas, 0 fallaron"
  ```

- **Optimización**: Considerar cachear resultados de `validate_source()` con TTL de 30 min para evitar re-validar la misma URL en requests repetidos




#### Flujo Recomendado en UI

```javascript
// 1. Usuario hace click en "Eliminar" de una fuente
async function handleDeleteSource(sourceId, sourceName) {
  // 2. Mostrar confirmación
  const confirmed = await showConfirmDialog(
    `¿Eliminar fuente "${sourceName}"?`,
    "Esta acción no se puede deshacer"
  );
  
  if (!confirmed) return;
  
  // 3. Llamar endpoint DELETE
  try {
    await deleteMarketSource(sourceId);
    
    // 4. Refrescar lista de fuentes
    await fetchProductSources(productId);
    
    // 5. Mostrar notificación
    showToast("Fuente eliminada correctamente", "success");
    
    // 6. (Opcional) Re-calcular precios automáticamente
    // await refreshMarketPrices(productId);
    
  } catch (error) {
    if (error.status === 404) {
      showToast("La fuente ya no existe", "warning");
    } else {
      showToast("Error al eliminar fuente", "error");
    }
  }
}
```

---

## Modelos de Base de Datos

### CanonicalProduct

Tabla principal para productos canónicos.

Campos relevantes:
- `id`: ID del producto
- `name`: Nombre base
- `ng_sku`: SKU generado automáticamente
- `sku_custom`: SKU personalizado (opcional)
- `sale_price`: Precio de venta
- `market_price_reference`: Valor de mercado manual
- `market_price_updated_at`: Fecha de última actualización del precio de mercado
- `category_id`: Categoría principal
- `subcategory_id`: Subcategoría (opcional)

### Category

Taxonomía de productos.

Campos:
- `id`: ID de categoría
- `name`: Nombre
- `parent_id`: Categoría padre (nullable)

### ProductEquivalence

Relaciona productos canónicos con productos de proveedores.

Campos relevantes:
- `canonical_product_id`: FK a `canonical_products`
- `supplier_id`: FK a `suppliers`
- `supplier_product_id`: FK a `supplier_products`

### MarketSource *(futuro - Etapa 2)*

Fuentes de precios de mercado.

Esquema propuesto:
```sql
CREATE TABLE market_sources (
  id SERIAL PRIMARY KEY,
  product_id INT REFERENCES canonical_products(id) ON DELETE CASCADE,
  source_name VARCHAR(200) NOT NULL,
  url TEXT NOT NULL,
  last_price NUMERIC(10,2),
  last_checked_at TIMESTAMP,
  is_mandatory BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(product_id, url)
);
```

## Tests

Los tests del endpoint se encuentran en `tests/test_market_api.py`.

### GET /market/products

Cobertura:
- ✅ Lista vacía
- ✅ Lista básica con múltiples productos
- ✅ Filtro por nombre (case-insensitive)
- ✅ Filtro por categoría
- ✅ Filtro por proveedor
- ✅ Paginación (múltiples páginas)
- ✅ Combinación de filtros
- ✅ Control de acceso (requiere auth, rechaza viewer)
- ✅ Preferred name con sku_custom
- ✅ Validación de schema completo

### GET /market/products/{id}/sources

Cobertura:
- ✅ 404 cuando producto no existe
- ✅ Producto sin fuentes (listas vacías)
- ✅ Producto con fuentes obligatorias y adicionales
- ✅ Separación correcta de fuentes (mandatory vs additional)
- ✅ Preferred name con sku_custom
- ✅ Validación de todos los campos requeridos
- ✅ Manejo de precios NULL
- ✅ Formato de timestamps ISO 8601

### PATCH /market/products/{id}/sale-price

Cobertura:
- ✅ Actualización exitosa con precio válido
- ✅ Rechazo de precio negativo (422)
- ✅ Rechazo de precio cero (422)
- ✅ 404 cuando producto no existe
- ✅ Rechazo de tipo inválido (string) (422)
- ✅ Actualización desde precio NULL
- ✅ Preferred name con sku_custom en respuesta

### PATCH /market/products/{id}/market-reference

Cobertura:
- ✅ Actualización exitosa con precio válido
- ✅ Rechazo de precio negativo (422)
- ✅ Aceptación de precio cero (válido para market_price_reference)
- ✅ 404 cuando producto no existe
- ✅ Rechazo de tipo inválido (string) (422)
- ✅ Actualización desde precio NULL
- ✅ Preferred name con sku_custom en respuesta
- ✅ Actualización de market_price_updated_at

### POST /market/products/{id}/refresh-market

Cobertura:
- ✅ Encolado exitoso de tarea de scraping (202)
- ✅ 404 cuando producto no existe
- ✅ Acepta producto sin fuentes (worker reportará 0 fuentes)
- ✅ Verificación de job_id en respuesta
- ✅ Mock de Dramatiq para evitar ejecución real en tests

### POST /market/products/{id}/sources

Cobertura:
- ✅ Agregar fuente exitosamente (201)
- ✅ 404 cuando producto no existe
- ✅ 409 cuando URL está duplicada
- ✅ 422 cuando URL es inválida (sin esquema)
- ✅ 422 cuando URL no tiene esquema http/https
- ✅ is_mandatory opcional (default false)
- ✅ Verificación de campos NULL (last_price, last_checked_at)

### DELETE /market/sources/{source_id}

Cobertura:
- ✅ Eliminar fuente exitosamente (204 No Content)
- ✅ 404 cuando fuente no existe
- ✅ Verificación de eliminación permanente en DB
- ✅ Otras fuentes del producto no afectadas

Ejecutar tests:
```bash
pytest tests/test_market_api.py -v
```

## Cambios Futuros (Roadmap)

### Etapa 2: Fuentes de Mercado

- [x] Crear tabla `market_sources` (migración `20251111_add_market_sources_table.py`)
- [x] Implementar `GET /market/products/{id}/sources` - Listar fuentes de un producto
- [x] Implementar `PATCH /market/products/{id}/sale-price` - Actualizar precio de venta
- [x] Agregar campo `market_price_updated_at` (migración `a219fcd042ea`)
- [x] Implementar `PATCH /market/products/{id}/market-reference` - Actualizar valor de mercado manual
- [x] Implementar `POST /market/products/{id}/refresh-market` - Iniciar scraping de precios
- [x] Implementar `POST /market/products/{id}/sources` - Agregar fuente
- [x] Implementar `DELETE /market/sources/{source_id}` - Eliminar fuente
- [ ] Implementar cálculo de `market_price_min` y `market_price_max`
- [ ] Agregar `last_market_update` desde fuentes
- [ ] Actualizar `GET /market/products` para incluir joins con `market_sources`

**Estado Etapa 2**: 8/11 items completados (73%)

### Etapa 3: Worker de Scraping

- [x] Crear worker `workers/market_scraping.py` con tarea Dramatiq
- [x] Estructura base: validación, query fuentes, actualización DB
- [ ] Implementar parsers específicos (MercadoLibre, SantaPlanta, etc.)
- [ ] Endpoint `POST /products/{id}/update-market` - Trigger manual de scraping (ya implementado como refresh-market)
- [ ] Integración con MCP Web Search
- [ ] Scraping programado (cron)

## Validaciones y Manejo de Errores

Todos los endpoints del módulo Mercado implementan validaciones exhaustivas y manejo controlado de errores para garantizar la integridad de los datos y la seguridad del sistema.

### Validaciones de Entrada

#### Precios

**Precio de Venta (`sale_price`)**:
- ✅ Debe ser un número decimal válido
- ✅ Debe ser mayor que cero (`> 0`)
- ✅ No puede exceder 999,999,999
- ❌ Rechaza valores negativos
- ❌ Rechaza cero (un producto sin precio debe usar `null`)
- ❌ Rechaza strings o tipos no numéricos

**Precio de Mercado de Referencia (`market_price_reference`)**:
- ✅ Debe ser un número decimal válido
- ✅ Debe ser mayor o igual a cero (`>= 0`)
- ✅ No puede exceder 999,999,999
- ✅ Acepta cero (indica "sin valor de referencia")
- ❌ Rechaza valores negativos
- ❌ Rechaza strings o tipos no numéricos

**Ejemplo de error de precio**:
```json
// Request
PATCH /market/products/123/sale-price
{"sale_price": -100}

// Response 422 Unprocessable Entity
{
  "detail": [
    {
      "type": "greater_than",
      "loc": ["body", "sale_price"],
      "msg": "Input should be greater than 0",
      "input": -100,
      "ctx": {"gt": 0}
    }
  ]
}
```

#### URLs de Fuentes

**Formato de URL**:
- ✅ Debe incluir esquema (`http://` o `https://`)
- ✅ Debe contener un dominio válido con al menos un punto (ej: `example.com`)
- ✅ Longitud mínima: 10 caracteres
- ✅ Longitud máxima: 500 caracteres
- ❌ Rechaza URLs sin esquema (ej: `example.com/producto`)
- ❌ Rechaza esquemas no permitidos (`ftp://`, `file://`)
- ❌ Rechaza dominios inválidos (ej: `https://localhost` sin TLD)

**Duplicados**:
- ✅ Valida que la URL no exista para el mismo producto
- ❌ Retorna `409 Conflict` si la URL ya está registrada

**Ejemplo de error de URL**:
```json
// Request
POST /market/products/123/sources
{
  "source_name": "Test Source",
  "url": "example.com/producto",
  "is_mandatory": false
}

// Response 422 Unprocessable Entity
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "url"],
      "msg": "Value error, URL debe incluir esquema (http/https) y dominio válido",
      "input": "example.com/producto"
    }
  ]
}
```

**Ejemplo de URL duplicada**:
```json
// Response 400 Bad Request o 409 Conflict
{
  "detail": "Ya existe una fuente con esta URL para el producto"
}
```

#### Nombre de Fuente

**Validaciones**:
- ✅ Longitud mínima: 3 caracteres (sin contar espacios)
- ✅ Longitud máxima: 200 caracteres
- ✅ Se elimina whitespace al inicio y final (`strip()`)
- ❌ Rechaza strings vacíos o solo espacios
- ❌ Rechaza nombres muy cortos (< 3 caracteres)

**Ejemplo**:
```json
// Request inválido
POST /market/products/123/sources
{
  "source_name": "ab",
  "url": "https://example.com/test",
  "is_mandatory": false
}

// Response 422
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "source_name"],
      "msg": "Value error, El nombre de la fuente debe tener al menos 3 caracteres",
      "input": "ab"
    }
  ]
}
```

#### Moneda

**Códigos válidos**:
- `ARS` (Peso Argentino) - **default**
- `USD` (Dólar Estadounidense)
- `EUR` (Euro)
- `BRL` (Real Brasileño)
- `CLP` (Peso Chileno)
- `UYU` (Peso Uruguayo)
- `PYG` (Guaraní Paraguayo)
- `BOB` (Boliviano)
- `MXN` (Peso Mexicano)
- `COP` (Peso Colombiano)
- `PEN` (Sol Peruano)

**Validaciones**:
- ✅ Códigos ISO 4217 comunes de Latinoamérica
- ✅ Case-insensitive (se convierte a mayúsculas automáticamente)
- ❌ Rechaza códigos no listados

**Ejemplo**:
```json
// Request inválido
POST /market/products/123/sources
{
  "source_name": "Test Source",
  "url": "https://example.com/test",
  "currency": "INVALID"
}

// Response 422
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "currency"],
      "msg": "Value error, Moneda 'INVALID' no soportada. Monedas válidas: ARS, USD, EUR, BRL, CLP, UYU, PYG, BOB, MXN, COP, PEN",
      "input": "INVALID"
    }
  ]
}
```

#### Tipo de Fuente

**Valores válidos**:
- `static` (default) - HTML estático, scraping con requests
- `dynamic` - Requiere JavaScript, scraping con Playwright

**Validaciones**:
- ✅ Solo acepta `"static"` o `"dynamic"`
- ❌ Rechaza cualquier otro valor

### Códigos de Error HTTP

El módulo Mercado utiliza códigos HTTP estándar para comunicar errores de forma clara:

| Código | Nombre | Uso |
|--------|--------|-----|
| `400` | Bad Request | Validación fallida (duplicados, lógica de negocio) |
| `401` | Unauthorized | Usuario no autenticado (falta token/session) |
| `403` | Forbidden | Usuario sin permisos para la operación (rol insuficiente) |
| `404` | Not Found | Recurso no existe (producto, fuente) |
| `409` | Conflict | Conflicto con estado actual (URL duplicada) |
| `422` | Unprocessable Entity | Validación Pydantic fallida (tipo incorrecto, rango inválido) |
| `500` | Internal Server Error | Error inesperado del servidor (sin detalles técnicos expuestos) |
| `502` | Bad Gateway | Servicio externo no disponible (worker, validador) |

### Manejo Seguro de Errores

#### Principios

1. **No exponer trazas internas**: Los clientes nunca reciben `traceback`, nombres de archivos Python o líneas de código
2. **Mensajes claros**: Errores describen el problema en lenguaje simple
3. **Logging detallado**: Errores técnicos se loguean en el servidor con contexto completo
4. **Códigos HTTP correctos**: Cada tipo de error usa el código apropiado

#### Ejemplos de Errores Seguros

**Error de validación (422)**:
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "sale_price"],
      "msg": "Value error, El precio de venta debe ser mayor a cero",
      "input": -50.0
    }
  ]
}
```
✅ Mensaje claro, sin traza Python  
✅ Indica campo específico (`sale_price`)  
✅ Incluye valor recibido para debugging

**Error de scraping (502)**:
```json
{
  "detail": "Servicio de validación de fuentes no disponible"
}
```
✅ No expone detalles de `ImportError` o stack trace  
✅ Mensaje entendible para el usuario  
❌ Detalles técnicos logueados en servidor:
```
[ERROR] [add_source_from_suggestion] Módulo de validación no disponible: No module named 'workers.discovery'
Traceback (most recent call last):
  File "services/routers/market.py", line 1172, in add_source_from_suggestion
    from workers.discovery.source_validator import validate_source
ImportError: No module named 'workers.discovery'
```

**Error inesperado (500)**:
```json
{
  "detail": "Error interno al validar la fuente"
}
```
✅ Mensaje genérico seguro  
❌ Excepción completa logueada con `exc_info=True`

#### Logging Estructurado

Todos los endpoints del módulo Mercado loguean eventos importantes:

**Formato de logs**:
```python
logger.info(f"[endpoint_name] Acción exitosa: detalles...")
logger.warning(f"[endpoint_name] Validación falló: razón...")
logger.error(f"[endpoint_name] Error inesperado: {str(e)}", exc_info=True)
```

**Niveles**:
- `INFO`: Operaciones exitosas (fuente agregada, precio actualizado)
- `WARNING`: Validaciones fallidas (URL duplicada, precio negativo detectado)
- `ERROR`: Errores inesperados (excepciones no controladas, servicios caídos)

**Contexto incluido**:
- Endpoint que falló (ej: `[refresh_market]`)
- IDs de recursos (producto, fuente)
- Parámetros recibidos (sin datos sensibles)
- Stack trace completo para `ERROR` level

**Ejemplo de log estructurado**:
```
2025-11-12 14:30:15 INFO [refresh_market] Encolando tarea para producto 123
2025-11-12 14:30:15 INFO [refresh_market] Tarea encolada exitosamente para producto 123, job_id=abc-123
2025-11-12 14:31:02 WARNING [add_source_from_suggestion] URL duplicada: https://example.com/test ya existe para producto 456
2025-11-12 14:32:10 ERROR [add_source_from_suggestion] Error inesperado al validar https://bad-url.com: HTTPError('500 Server Error')
Traceback (most recent call last):
  ...
```

### Tests de Validación

El módulo incluye suite completa de tests (`tests/test_market_validation.py`):

**Cobertura**:
- ✅ Precios negativos/cero/muy altos rechazados
- ✅ URLs sin esquema/dominio inválido rechazadas
- ✅ URLs duplicadas detectadas (409)
- ✅ Nombres muy cortos rechazados
- ✅ Monedas inválidas rechazadas
- ✅ Tipos de fuente inválidos rechazados
- ✅ Respuestas de error no exponen trazas
- ✅ Mensajes de error son claros y específicos

**Ejecutar tests de validación**:
```bash
pytest tests/test_market_validation.py -v
```

**Clases de tests**:
- `TestSalePriceValidation` - Validación de precio de venta
- `TestMarketReferenceValidation` - Validación de precio de mercado
- `TestURLValidation` - Validación de formato de URLs
- `TestDuplicateURLValidation` - Detección de duplicados
- `TestSourceNameValidation` - Validación de nombre de fuente
- `TestCurrencyValidation` - Validación de moneda
- `TestSourceTypeValidation` - Validación de tipo de fuente
- `TestErrorResponseFormat` - Formato seguro de respuestas de error

### Tests Unitarios de Lógica de Negocio

**Suite completa de tests**: Ver `docs/MARKET_UNIT_TESTS.md` para documentación detallada.

**Ejecutar**:
```bash
# Todos los tests unitarios de Market
pytest tests/unit/test_price_normalizer.py tests/unit/test_static_scraper.py tests/unit/test_dynamic_scraper.py -v

# Solo normalización de precios
pytest tests/unit/test_price_normalizer.py -v

# Con cobertura
pytest tests/unit/test_price_normalizer.py --cov=workers.scraping.price_normalizer --cov-report=html
```

**Tests implementados**:
- ✅ 89 tests de normalización de precios (formatos, monedas, separadores)
- ✅ 30 tests de scraping estático (extractores, errores de red)
- ✅ 24 tests de scraping dinámico (Playwright, selectores, async)
- **Total: 143 tests (137 passing, 6 skipped con razón documentada)**

### Optimizaciones Futuras

- [ ] Agregar índices en `canonical_products(category_id, name)`
- [ ] Cache de resultados frecuentes (Redis)
- [ ] Eager loading optimizado para proveedor principal
- [ ] Soporte para ordenamiento personalizado (`?sort=price_asc`)
- [ ] Exportar a CSV/Excel

## Referencias

**Documentos relacionados**:
- `docs/MERCADO.md` - Plan maestro de implementación
- `docs/MERCADO_IMPLEMENTACION.md` - Detalles técnicos
- `docs/MERCADO_EDICION_PRECIOS.md` - Funcionalidad de edición de precios
- `docs/MARKET_UNIT_TESTS.md` - **NUEVO**: Documentación completa de tests unitarios
- `docs/API_PRODUCTS.md` - Endpoints generales de productos

**Código fuente**:
- `services/routers/market.py` - Implementación del router
- `tests/test_market_api.py` - Tests del endpoint (integración)
- `tests/test_market_validation.py` - Tests de validaciones
- `tests/unit/test_price_normalizer.py` - Tests unitarios de normalización
- `tests/unit/test_static_scraper.py` - Tests unitarios de scraping estático
- `tests/unit/test_dynamic_scraper.py` - Tests unitarios de scraping dinámico
- `db/models.py` - Modelos ORM

---

**Última actualización**: 2025-01-10  
**Versión API**: 1.0  
**Estado**: Etapa 2 casi completa (8/11 items, 73%). CRUD de fuentes implementado con validaciones completas. Etapa 3 iniciada (worker base implementado, parsers pendientes). **Tests unitarios completados: 143 tests (95.8% passing)**.

