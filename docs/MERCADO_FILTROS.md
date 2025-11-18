<!-- NG-HEADER: Nombre de archivo: MERCADO_FILTROS.md -->
<!-- NG-HEADER: Ubicación: docs/MERCADO_FILTROS.md -->
<!-- NG-HEADER: Descripción: Guía de uso del sistema de filtros de la página Mercado -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Sistema de Filtros - Página Mercado

## Contexto

La página "Mercado" permite comparar precios de venta internos con rangos de mercado. Dado que el volumen de productos puede crecer considerablemente, se implementó un sistema de filtros avanzado para facilitar la navegación y segmentación.

## Filtros Disponibles

### 1. Búsqueda por Nombre o SKU

**Tipo**: Input de texto  
**Ubicación**: Primera columna de la barra de filtros  
**Placeholder**: "Nombre o SKU..."

**Comportamiento**:
- Búsqueda incremental con debounce de 300ms
- Busca coincidencias en:
  - Nombre del producto (`name`)
  - Nombre preferido (`preferred_name`)
  - SKU interno
- Case-insensitive (no distingue mayúsculas/minúsculas)
- Reinicia automáticamente la paginación a página 1

**Ejemplo de uso**:
```
"fertilizante" → Encuentra "Fertilizante NPK 10-10-10", "fertilizante orgánico", etc.
"NPK" → Encuentra productos con NPK en el nombre
"12345" → Busca por SKU exacto o parcial
```

### 2. Filtro por Proveedor

**Tipo**: Autocomplete  
**Ubicación**: Segunda columna de la barra de filtros  
**Placeholder**: "Todos los proveedores"

**Comportamiento**:
- Autocomplete dinámico con búsqueda al backend
- Carga inicial de proveedores más usados
- Búsqueda incremental al escribir
- Muestra nombre del proveedor en el selector
- Limitable a proveedores activos

**Ejemplo de uso**:
```
Escribir "Santa" → Sugiere "SantaPlanta", "Santa Rosa Viveros", etc.
Seleccionar → Filtra solo productos de ese proveedor
```

### 3. Filtro por Categoría

**Tipo**: Dropdown (select)  
**Ubicación**: Tercera columna de la barra de filtros  
**Valor por defecto**: "Todas"

**Comportamiento**:
- Lista estática cargada al montar el componente
- Muestra todas las categorías del sistema
- Opción "Todas" para quitar filtro
- Soporta jerarquía de categorías (si aplica)

**Ejemplo de uso**:
```
Seleccionar "Fertilizantes" → Muestra solo productos de esa categoría
Seleccionar "Todas" → Quita el filtro
```

## Filtros Combinados

Los tres filtros trabajan simultáneamente. Ejemplos de combinaciones:

### Caso 1: Búsqueda + Categoría
```
Búsqueda: "orgánico"
Categoría: "Fertilizantes"
Resultado: Solo fertilizantes orgánicos
```

### Caso 2: Proveedor + Búsqueda
```
Proveedor: "SantaPlanta"
Búsqueda: "LED"
Resultado: Solo productos LED del proveedor SantaPlanta
```

### Caso 3: Todos los filtros
```
Búsqueda: "NPK"
Proveedor: "Proveedor A"
Categoría: "Fertilizantes"
Resultado: Fertilizantes NPK del Proveedor A
```

## Badges de Filtros Activos

Cuando hay filtros aplicados, se muestran badges visuales debajo de la barra de filtros:

**Formato**:
```
[Búsqueda: "texto" ✕] [Proveedor: Nombre ✕] [Categoría: Nombre ✕]
```

**Características**:
- Fondo azul (color primario del tema)
- Texto blanco
- Botón "✕" para remover filtro individual
- Se ocultan automáticamente cuando no hay filtros

**Interacción**:
- Clic en "✕" → Remueve ese filtro específico
- Automáticamente actualiza la tabla

## Botón "Limpiar Filtros"

**Ubicación**: A la derecha de la barra de filtros  
**Visible**: Solo cuando hay al menos un filtro activo  
**Icono**: 🗑️

**Comportamiento**:
- Un clic limpia todos los filtros simultáneamente
- Reinicia la paginación
- Recarga la tabla con todos los productos
- Se oculta cuando no hay filtros activos

## Contador de Resultados

**Ubicación**: Debajo de la barra de filtros  
**Formato**: "X producto(s) encontrado(s)"

**Estados**:
- Cargando: "Cargando..."
- Con resultados: "25 productos encontrados"
- Sin resultados: "0 productos encontrados"

**Pluralización automática**:
- 1 producto → "1 producto encontrado"
- 2+ productos → "X productos encontrados"

## Estados Vacíos

### Sin Filtros Activos

Cuando no hay datos y no hay filtros:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  Endpoint /market/products pendiente de         │
│  implementación (ver docs/MERCADO.md Etapa 2)   │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Con Filtros Sin Resultados

Cuando hay filtros pero no hay coincidencias:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  No se encontraron productos que coincidan      │
│  con los filtros aplicados                      │
│                                                 │
│          [Limpiar filtros]                      │
│                                                 │
└─────────────────────────────────────────────────┘
```

El botón "Limpiar filtros" dentro del estado vacío facilita la recuperación de la vista completa.

## Performance y Optimización

### Debounce de Búsqueda

**Problema**: Sin debounce, cada tecla presionada genera una llamada al backend (10 teclas = 10 requests).

**Solución**: Debounce de 300ms.

```typescript
useEffect(() => {
  const timer = setTimeout(() => {
    loadProducts() // Solo se ejecuta 300ms después del último cambio
  }, 300)
  return () => clearTimeout(timer) // Limpia timer anterior
}, [q, supplierId, categoryId, page])
```

**Resultado**: Si el usuario escribe "fertilizante" (11 teclas) en 2 segundos, solo se genera 1 request.

### Reinicio de Paginación

Cada vez que cambia un filtro, la paginación se reinicia a página 1:

```typescript
function resetAndSearch() {
  setPage(1)        // Volver a primera página
  setItems([])      // Limpiar items actuales
}
```

Esto evita confusiones (ej: estar en página 5 de "todos" y aplicar filtro que solo tiene 1 página).

### Caché de Categorías

Las categorías se cargan una sola vez al montar el componente:

```typescript
useEffect(() => {
  listCategories().then(setCategories).catch(() => {})
}, []) // Array vacío = solo al montar
```

No se recargan en cada filtrado, optimizando performance.

## Implementación Técnica

### Estados Gestionados

```typescript
const [q, setQ] = useState('')                    // Búsqueda texto
const [categoryId, setCategoryId] = useState('')  // ID categoría
const [supplierId, setSupplierId] = useState('')  // ID proveedor
const [supplierSel, setSupplierSel] = useState<SupplierSearchItem | null>(null) // Objeto proveedor
```

### Funciones Auxiliares

```typescript
// Limpia todos los filtros
function clearAllFilters() {
  setQ('')
  setCategoryId('')
  setSupplierId('')
  setSupplierSel(null)
  resetAndSearch()
}

// Verifica si hay filtros activos
function hasActiveFilters(): boolean {
  return !!(q || categoryId || supplierId)
}

// Reinicia búsqueda
function resetAndSearch() {
  setPage(1)
  setItems([])
}
```

### Llamada al Backend (Pendiente Etapa 2)

Cuando se implemente el endpoint, los filtros se enviarán así:

```typescript
const params = new URLSearchParams()
if (q) params.set('q', q)
if (supplierId) params.set('supplier_id', supplierId)
if (categoryId) params.set('category_id', categoryId)
params.set('page', String(page))
params.set('page_size', '50')

const response = await fetch(`/market/products?${params}`)
```

## Flujo Completo de Usuario

### Caso de Uso: Buscar producto específico

1. Usuario abre página "Mercado"
2. Tabla muestra mensaje de backend pendiente
3. Usuario escribe "LED" en búsqueda
4. Espera 300ms (debounce)
5. Badge "Búsqueda: LED" aparece
6. Tabla se actualiza (cuando backend esté listo)
7. Contador muestra "15 productos encontrados"
8. Usuario ve solo productos con "LED" en el nombre

### Caso de Uso: Productos de proveedor en categoría específica

1. Usuario selecciona "Fertilizantes" en categoría
2. Badge "Categoría: Fertilizantes" aparece
3. Usuario empieza a escribir "Santa" en proveedor
4. Autocomplete sugiere "SantaPlanta"
5. Usuario selecciona "SantaPlanta"
6. Badge "Proveedor: SantaPlanta" aparece
7. Tabla muestra solo fertilizantes de SantaPlanta
8. Contador muestra "8 productos encontrados"

### Caso de Uso: Limpiar filtros después de búsqueda

1. Usuario tiene 3 filtros activos
2. Badges muestran los 3 filtros
3. Contador muestra "2 productos encontrados"
4. Usuario hace clic en "Limpiar filtros"
5. Todos los badges desaparecen
6. Botón "Limpiar filtros" se oculta
7. Tabla vuelve a mostrar todos los productos
8. Contador muestra total de productos

## Accesibilidad

### Labels Visibles

Cada filtro tiene un label descriptivo:
- "Buscar producto"
- "Proveedor"
- "Categoría"

### Atributos Title

Elementos interactivos tienen tooltips:
```html
<input title="Buscar por nombre de producto o SKU" />
<select title="Filtrar por categoría de producto" />
<button title="Limpiar todos los filtros" />
```

### Navegación por Teclado

- ✅ Input de búsqueda: navegable con Tab
- ✅ Autocomplete proveedor: navegable con flechas
- ✅ Select categoría: navegable con flechas
- ✅ Botón limpiar: activable con Enter/Space

## Casos Límite

### 1. Usuario escribe muy rápido
**Comportamiento**: Debounce de 300ms asegura que solo se ejecute 1 request al terminar de escribir.

### 2. Sin categorías en el sistema
**Comportamiento**: Dropdown solo muestra "Todas", filtro no genera error.

### 3. Filtros sin resultados
**Comportamiento**: Mensaje específico + botón de limpieza, evita confusión.

### 4. Cambio de filtro mientras carga
**Comportamiento**: Timeout anterior se cancela, nueva búsqueda comienza.

### 5. Proveedor eliminado después de selección
**Comportamiento**: (Futuro) Validación en backend + mensaje de error.

## Testing

### Tests Unitarios

```typescript
test('clearAllFilters limpia todos los estados', () => {
  // Setup: filtros con valores
  setQ('test')
  setCategoryId('1')
  setSupplierId('5')
  
  // Action
  clearAllFilters()
  
  // Assert
  expect(q).toBe('')
  expect(categoryId).toBe('')
  expect(supplierId).toBe('')
})

test('hasActiveFilters detecta filtros activos', () => {
  setQ('test')
  expect(hasActiveFilters()).toBe(true)
  
  clearAllFilters()
  expect(hasActiveFilters()).toBe(false)
})
```

### Tests de Integración

```typescript
test('filtro por búsqueda actualiza tabla', async () => {
  render(<Market />)
  const searchInput = screen.getByPlaceholderText('Nombre o SKU...')
  
  await userEvent.type(searchInput, 'fertilizante')
  
  await waitFor(() => {
    expect(mockLoadProducts).toHaveBeenCalledWith(
      expect.objectContaining({ q: 'fertilizante' })
    )
  })
})
```

## Mejoras Futuras

### Corto Plazo
- [ ] Persistir filtros en URL (query params) para compartir enlaces
- [ ] Guardar últimos filtros en localStorage
- [ ] Filtro por rango de precio
- [ ] Ordenamiento de columnas (nombre, precio, fecha)

### Mediano Plazo
- [ ] Filtros avanzados en modal (múltiples categorías, rangos, etc.)
- [ ] Autocompletado con historial de búsquedas recientes
- [ ] Filtro por diferencial de precio (ej: solo precios muy desalineados)
- [ ] Exportar resultados filtrados a Excel/CSV

### Largo Plazo
- [ ] Búsqueda fuzzy (tolerante a errores de tipeo)
- [ ] Filtros guardados como "vistas" (ej: "Productos desactualizados")
- [ ] Sugerencias de búsqueda basadas en IA
- [ ] Filtrado por múltiples criterios con operadores AND/OR

---

**Versión**: 1.0  
**Última actualización**: 2025-11-11  
**Estado**: Etapa 1 completada, backend pendiente (Etapa 2)
