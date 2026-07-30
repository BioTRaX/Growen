<!-- NG-HEADER: Nombre de archivo: MERCADO.md -->
<!-- NG-HEADER: Ubicación: docs/MERCADO.md -->
<!-- NG-HEADER: Descripción: Plan de implementación de la funcionalidad "Mercado" -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

> Actualización 2026-07-26: la tabla `market_sources` descrita más abajo ya no existe. Mercado consume activos con etiqueta `market`, capacidad `price` y perfil `canonical_knowledge_market_profiles`. Ver `API_MARKET.md` y `CANONICAL_KNOWLEDGE.md`.

# Funcionalidad "Mercado" - Plan de Implementación

Este documento detalla el plan completo para implementar la sección "Mercado" en la aplicación Growen, que permitirá visualizar y comparar precios de productos con el mercado.

**Documentos relacionados**:
- `docs/MERCADO_IMPLEMENTACION.md` - Detalles técnicos completos
- `docs/MERCADO_FILTROS.md` - Sistema de filtros avanzado
- `docs/MERCADO_EDICION_PRECIOS.md` - Guía de edición de precios (nueva funcionalidad)
- `docs/MERCADO_INTEGRACION_FRONTEND.md` - Integración frontend-backend (GET /market/products)
- `docs/MERCADO_SOURCES_ENDPOINT.md` - Endpoint GET /market/products/{id}/sources (nueva funcionalidad)
- `docs/API_MARKET.md` - Documentación de API del módulo Mercado

## Etapa 0: Planificación y Diseño

### 1. Alcance Funcional y Objetivos

**Resumen**: La sección "Mercado" listará todos los productos en una tabla con su nombre, precio de venta actual y rango de precios en el mercado. Esto permite comparar rápidamente nuestros precios con los del mercado.

**Acciones del Usuario**: En esta sección, los administradores y colaboradores podrán:

- Ver el nombre del producto, su precio de venta actual y un rango estimado de precios del mercado (mínimo–máximo en ARS) basado en fuentes externas.
- Editar el precio de venta directamente desde la lista (con historial de modificaciones).
- Consultar el historial de precios de venta de cada producto.
- Filtrar y buscar productos por nombre o categoría (como en Productos/Stock).

**Control de Acceso**: Solo los usuarios con rol de administrador o colaborador pueden acceder a "Mercado".

**Objetivo**: Permitir decisiones de precios informadas al comparar rápidamente nuestros precios internos con los valores actuales del mercado, y ajustar si es necesario.

### 2. Diseño UI/UX

**Navegación**: Se agregará un nuevo botón "Mercado" en la barra de navegación principal, a la derecha del botón "Productos".

**Diseño**: Usar una tabla similar a la de Productos/Stock. Cada fila representa un producto y tendrá columnas para:

- Nombre del producto (usando `preferred_name` como en la lista de productos).
- Precio de venta actual (en ARS).
- Precio de mercado (mínimo–máximo).
- Acciones: Botón en cada fila (ej. "Detalles Mercado") para ver más opciones.

**Modal Detalles del Mercado**: Al hacer clic en el botón, se abrirá una vista detallada:

- Lista de fuentes: con formato "Precio – Fuente".
- Enlaces: cada fuente será clickeable para ver el precio en el sitio original.
- Configurar fuentes: se podrá agregar/editar fuentes obligatorias (nombre y URL).
- Botón de actualizar: para lanzar manualmente un scraping que obtenga precios actualizados desde las fuentes definidas y la búsqueda web.

**Filtros y Búsquedas**:

- Barra de búsqueda por nombre o SKU.
- Filtro por categoría (dropdown), ya que los productos tienen categorías.

**Sistema de filtros implementado** (Etapa 1):

- **Búsqueda por texto**: Campo de entrada para buscar productos por nombre o SKU
  - Debounce de 300ms para optimizar performance
  - Búsqueda case-insensitive
  - Reinicia paginación automáticamente
  
- **Filtro por proveedor**: Autocomplete con búsqueda dinámica
  - Reutiliza componente `SupplierAutocomplete` de Stock
  - Permite búsqueda incremental
  - Muestra nombre del proveedor seleccionado
  
- **Filtro por categoría**: Dropdown estático
  - Carga categorías desde el backend al montar
  - Opción "Todas" por defecto
  - Muestra jerarquía de categorías si existe
  
- **Filtros combinados**: 
  - Los tres filtros trabajan en simultáneo
  - Aplicación inmediata sin necesidad de botón "Buscar"
  - Actualización reactiva de la tabla
  
- **Limpieza de filtros**:
  - Botón "Limpiar filtros" visible cuando hay filtros activos
  - Badges visuales de filtros aplicados con opción de remover individualmente
  - Estado vacío mejorado con botón de limpieza cuando no hay resultados

**Edición del Precio de Venta**:

- El precio será editable (icono lápiz o edición en línea).
- Validar y actualizar el precio vía endpoint correspondiente.
- Confirmar el cambio, actualizar la UI y registrar en historial.

**Diseño Visual**:

- Mantener coherencia con el estilo actual de la app.
- Resaltar discrepancias importantes entre nuestro precio y el mercado.
- Distinguir fuentes obligatorias de adicionales (con subtítulos o etiquetas).

### 3. Modelo de Datos y Almacenamiento

**Campos del Producto**:

- Ya existe `market_price_reference`, que puede mantenerse como promedio/referencia rápida.
- El rango (mín–máx) se obtendrá desde múltiples fuentes.

**Nuevo Modelo "Source"**:

- **Campos**: `id`, `product_id`, `source_name`, `url`, `last_price`, `last_checked_at`, `is_mandatory`.
- Permite definir fuentes obligatorias.
- También guarda la última consulta y precio.

**Historial de Precios** (opcional):

- Venta: ya hay logs de auditoría (`product_update.price`).
- Competencia: considerar una tabla de historial si hay cambios significativos en precios.

**Almacenamiento del Rango**:

- Se puede calcular dinámicamente (min–max de `last_price`).
- Opcionalmente cachear en el producto si se requiere rendimiento.

**Integración con Enriquecimiento**:

- El sistema de enriquecimiento por IA puede coexistir con este mecanismo.
- Las fuentes pueden almacenarse en la DB en vez de texto.

### 4. Fuentes de Datos

**Fuentes Obligatorias** (por producto):

- MercadoLibre, tiendas competidoras como SantaPlanta, fabricante directo si aplica.
- Cada producto puede tener varias fuentes obligatorias.

**Fuentes Adicionales vía Búsqueda Web**:

- Usar servicio MCP Web Search existente (DuckDuckGo scraping).
- Limitar resultados a sitios conocidos y con términos como "precio", "comprar".
- Mostrar como "extra" en la UI con el nombre de la tienda y el precio.

**Prioridad de Fuentes**:

- Las obligatorias son primordiales.
- Las extra son de apoyo. El usuario puede validarlas y promoverlas a obligatorias.

**Enfoque de Retail**:

- Enfocarse en precios minoristas (MercadoLibre, growshops, fabricante).

**Moneda y Formato**:

- Detectar ARS (símbolo $), evitar precios en USD si no se pueden convertir.
- Usar formato consistente y comprensible.

### 5. Implementación del Worker de Scraping

**Arquitectura**:

- Worker de scraping como tarea en segundo plano o microservicio MCP.
- Endpoint tipo `POST /products/{id}/update-market`.

**Estrategia de Scraping**:

- Requests + BeautifulSoup para sitios estáticos.
- Playwright para sitios con JavaScript.
- Parsers específicos para cada fuente (MercadoLibre, SantaPlanta, etc.).

**Manejo de Errores**:

- Si una fuente falla, mostrar mensaje y continuar.
- Loggear errores y eventos.

**Actualización de Datos**:

- Actualizar `last_price` y `last_checked_at`.
- Calcular y actualizar el rango.
- Retornar datos al frontend.

**Actualizaciones Programadas** (futuro):

- Cron o botón "Actualizar todos".
- Agregar controles para evitar sobrecargas a sitios externos.

### 6. Uso de Infraestructura Existente

**Servicio MCP Web Search**:

- Reutilizar para buscar fuentes adicionales.

**Código del Crawler de Imágenes**:

- Reusar lógica de Playwright e imágenes para scraping de precios.

**Enriquecimiento por IA**:

- El scraping puede proveer datos a la IA para mayor precisión.

**Separación del Servicio**:

- Puede implementarse internamente con Dramatiq o como microservicio aparte.

**Gestión de Dependencias**:

- Asegurar que Playwright esté instalado en el contenedor.
- Agregar a `requirements.txt` lo necesario.

### 7. Evaluación de Herramientas Open Source

- **Playwright (Python)**: Ideal para JS, ya parcialmente integrado.
- **Requests + BeautifulSoup**: Primera opción por rapidez y familiaridad.
- **Scrapy**: Excesivo para este caso, se descarta.
- **SerpAPI/Google**: Se descartan por ser pagos.
- **Alternativas como Huginn/n8n**: Muy pesadas para nuestro caso.

**Normalización de Precios**:

- Cuidar formatos regionales (puntos, comas, símbolos).

### 8. Seguridad y Permisos

- Solo Admins y Colaboradores acceden a "Mercado".
- Validar URLs de fuentes ingresadas.
- Controlar uso razonable (scraping ético).
- No almacenar credenciales.
- UI debe manejar errores de scraping.

### 9. Testing y QA

- **Tests Unitarios**: Parsers por fuente con HTML guardado.
- **Tests de Integración**: Llamadas reales desde staging.
- **Tests UI**: Filtrado, edición, modal, botón de actualizar.
- **Performance**: Considerar lazy load o caché.
- **Verificación Manual**: Comparar valores en producción vs sitios reales.
- **Manejo de Casos Límite**: "Sin datos" debe mostrarse correctamente.

### 10. Futuras Mejoras

- **Actualización Automática**: Programar scraping.
- **Alertas**: Precio fuera de rango o cambios abruptos.
- **Mejorar Calidad de Datos**: Precios actualizados, correcto elemento.
- **Ampliar Biblioteca de Fuentes**: Parsers por dominio.
- **Monitoreo de Herramientas Open Source**: Estar atentos a Firecrawl y similares.
- **Documentación**: Actualizar archivos de documentación y uso.

---

## Estado de Implementación

- **Etapa 0**: ✅ Completada (Planificación documentada - 2025-11-11)
- **Etapa 1**: ✅ Completada (Componente de tabla UI - 2025-11-11)
  - Componente `Market.tsx` con tabla completa
  - **Sistema de filtros avanzado** (mejorado 2025-11-11):
    - Filtro por nombre/SKU con debounce (300ms)
    - Filtro por proveedor (autocomplete dinámico)
    - Filtro por categoría (dropdown)
    - Filtros combinados simultáneos
    - Badges de filtros activos con remoción individual
    - Botón "Limpiar filtros" contextual
    - Estados vacíos mejorados con feedback específico
  - Indicadores visuales de comparación de precios
  - Navegación agregada en `AppToolbar` y rutas configuradas
  - Acceso restringido a admin/colaborador
  - **Documentación detallada** en `docs/MERCADO_FILTROS.md`
- **Etapa 2**: 🔄 En Progreso (Modelo de datos y endpoints backend)
  - ✅ **Endpoint `GET /market/products`** implementado (2025-11-11):
    - Lista productos con precios para la UI
    - Soporta filtros: `q` (nombre), `category_id`, `supplier_id`
    - Paginación configurable
    - Protegido con roles (admin/colaborador)
    - Tests completos en `tests/test_market_api.py`
    - Documentación en `docs/API_MARKET.md`
  - ✅ **Frontend sincronizado con backend** (2025-11-11):
    - Función `listMarketProducts()` en `frontend/src/services/market.ts`
    - `Market.tsx` actualizado para consumir endpoint real
    - Manejo de estados de carga y errores HTTP
    - Paginación sincronizada con `total_pages` del servidor
    - Interfaces TypeScript: `MarketProductItem`, `MarketProductsResponse`
  - ✅ **Tabla `market_sources` creada** (2025-11-11):
    - Migración: `db/migrations/versions/20251111_add_market_sources_table.py`
    - Modelo ORM: `MarketSource` en `db/models.py`
    - Campos: id, product_id, source_name, url, last_price, last_checked_at, is_mandatory
    - Índice en product_id y constraint unique(product_id, url)
  - ✅ **Endpoint `GET /market/products/{id}/sources`** implementado (2025-11-11):
    - Retorna fuentes separadas en obligatorias y adicionales
    - Maneja 404 para productos inexistentes
    - Tests completos (6 casos)
    - Frontend sincronizado: `getProductSources()` consume endpoint real
  - ⏳ Endpoint `POST /market/products/{id}/sources` para agregar fuente
  - ⏳ Endpoint `DELETE /market/products/{id}/sources/{source_id}` para eliminar fuente
  - ⏳ **Endpoint `PATCH /market/products/{id}/market-reference`** para actualizar valor de mercado manual
  - ⏳ Cálculo de `market_price_min` y `market_price_max` desde fuentes
  - ⏳ Campo `last_market_update` con timestamp real
- **Etapa 3**: ⏳ Pendiente (Worker de scraping)
  - Parser genérico + específicos por dominio (MercadoLibre, SantaPlanta, etc.)
  - Integración con MCP Web Search para fuentes adicionales
  - Endpoint `POST /products/{id}/update-market`
  - Manejo robusto de errores y logging
- **Etapa 4**: ✅ Completada (Modal de detalles y gestión de fuentes - 2025-11-11)
  - **Servicio frontend** (`frontend/src/services/market.ts`):
    - Interfaces: `MarketSource`, `ProductSourcesResponse`, `UpdateMarketPricesResponse`, `AddSourcePayload`
    - Funciones: `getProductSources()`, `updateProductMarketPrices()`, `addProductSource()`, `deleteProductSource()`, `validateSourceUrl()`
    - **Funciones de edición** (2025-11-11): `updateProductSalePrice()`, `updateMarketReference()`, `validatePrice()`
    - Mock data implementado para desarrollo desacoplado del backend
  - **Modal principal** (`frontend/src/components/MarketDetailModal.tsx`):
    - **Sección "Gestión de Precios"** (2025-11-11): campos editables para precio de venta y valor de mercado de referencia
    - Lista de fuentes obligatorias y adicionales
    - Botón "Actualizar Precios" con feedback de éxito/error
    - Botón "Agregar Nueva Fuente" (abre sub-modal)
    - Eliminación de fuentes con confirmación
    - Indicadores de frescura de precios (fresh <24h, stale 1-7 días, never >7 días)
    - Sub-componente `SourceCard` para renderizar cada fuente
  - **Componente reutilizable** (`frontend/src/components/EditablePriceField.tsx` - 2025-11-11):
    - Campo editable con modo lectura/edición
    - Validación en tiempo real (número positivo, máximo 999M)
    - Atajos de teclado: Enter (guardar), Esc (cancelar)
    - Loading states y mensajes de error
    - Formateo automático de valores
  - **Sub-modal de agregar fuente** (`frontend/src/components/AddSourceModal.tsx`):
    - Formulario con validación de nombre (3-200 chars) y URL (HTTP/HTTPS)
    - Checkbox para marcar como obligatoria
    - Validación en tiempo real con mensajes de error específicos
    - Ejemplos de uso incluidos en el modal
  - **Integración en Market.tsx**:
    - Estado para producto seleccionado (id + nombre)
    - Handlers: `handleOpenDetail()`, `handleCloseDetail()`, `handlePricesUpdated()`
    - Callback para refrescar tabla después de actualizar precios
- **Etapa 5**: ⏳ Pendiente (Tests y QA)
  - Unit tests de parsers
  - Integration tests con respx
  - Tests UI completos (React Testing Library para modales)
  - Tests de validación de formularios

---

## Archivos Creados/Modificados (Etapas 0 + 1 + 2 + 4)

### Documentación
- `docs/MERCADO.md` - Plan completo de implementación (este archivo)
- `docs/MERCADO_IMPLEMENTACION.md` - Detalles técnicos de implementación
- `docs/MERCADO_FILTROS.md` - Guía detallada del sistema de filtros
- `docs/MERCADO_FILTROS_CHANGELOG.md` - Changelog de mejoras de filtros
- `docs/MERCADO_EDICION_PRECIOS.md` - Guía de edición de precios
- **`docs/API_MARKET.md`** - Documentación de API del módulo Mercado (nuevo - 2025-11-11)
- **`docs/MERCADO_INTEGRACION_FRONTEND.md`** - Integración frontend-backend GET /market/products (nuevo - 2025-11-11)
- `Roadmap.md` - Agregada sección Hito 5.1

### Frontend
- `frontend/src/pages/Market.tsx` - Componente principal (actualizado con endpoint real - 2025-11-11)
- `frontend/src/routes/paths.ts` - Agregada ruta `/mercado`
- `frontend/src/App.tsx` - Configurada ruta protegida para Market
- `frontend/src/components/AppToolbar.tsx` - Agregado botón "Mercado"
- **`frontend/src/services/market.ts`** - Servicio HTTP (actualizado: `listMarketProducts()`, `getProductSources()` real - 2025-11-11)
- **`frontend/src/components/MarketDetailModal.tsx`** - Modal de detalles del producto (nuevo - Etapa 4)
- **`frontend/src/components/AddSourceModal.tsx`** - Sub-modal para agregar fuentes (nuevo - Etapa 4)
- **`frontend/src/components/EditablePriceField.tsx`** - Campo editable reutilizable (nuevo - 2025-11-11)

### Backend
- **`db/models.py`** - Agregado modelo `MarketSource` y relación con `CanonicalProduct` (modificado - 2025-11-11)
- **`db/migrations/versions/20251111_add_market_sources_table.py`** - Migración para tabla market_sources (nuevo - 2025-11-11)
- **`services/routers/market.py`** - Router con endpoints GET /market/products y GET /market/products/{id}/sources (actualizado - 2025-11-11)
- **`services/api.py`** - Registrado router de market (modificado - 2025-11-11)
- **`tests/test_market_api.py`** - Tests de endpoints de mercado (actualizado con 6 tests nuevos - 2025-11-11)

### Próximos Archivos (Etapas 2-3-5)
- `services/routers/market.py` - Extender con POST /market/products/{id}/sources, DELETE /market/products/{id}/sources/{source_id}, PATCH /market/products/{id}/market-reference
- `workers/scraping/market_prices.py` - Worker de scraping
- `workers/scraping/parsers/*.py` - Parsers específicos por fuente
- `tests/test_market_scraping.py` - Tests de scraping
- `tests/test_market_endpoints.py` - Tests de endpoints CRUD de fuentes (extender test_market_api.py)
- `tests/test_market_modal.test.tsx` - Tests UI de modales

---

Actualizado: 2025-11-11

