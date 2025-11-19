<!-- NG-HEADER: Nombre de archivo: MARKET_QUERY_OPTIMIZATION.md -->
<!-- NG-HEADER: Ubicación: docs/MARKET_QUERY_OPTIMIZATION.md -->
<!-- NG-HEADER: Descripción: Optimización de queries de búsqueda para descubrimiento de fuentes -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Optimización de Queries de Búsqueda - Market Discovery

## Problema Identificado

**Fecha**: 2025-11-18

**Síntoma**: El endpoint `/market/products/{id}/discover-sources` generaba queries de búsqueda con **demasiados términos**, reduciendo la efectividad:

```
Query antigua: "Filtros Libella Slim Parafernalia precio comprar"
                                      ^^^^^^^^^^^^^ ^^^^^^
                                      Categoría     Redundante
```

**Resultado**: 
- Búsquedas poco efectivas
- Posibles resultados irrelevantes
- 0 fuentes válidas en algunos casos

## Análisis

### Composición de Query Antigua

```python
# workers/discovery/source_finder.py (versión anterior)
parts = [product_name, sku, category, "precio", "comprar"]
query = " ".join(parts)
```

**Problemas**:
1. **Categoría**: Términos genéricos o poco útiles (ej: "Parafernalia")
2. **"precio"**: Redundante (ya está implícito en "comprar")
3. **SKU interno**: SKUs como "CAMP_0001_CAR" no aportan valor en búsqueda pública
4. **Ruido**: Más keywords ≠ mejores resultados

### Ejemplo Real

**Producto**: Filtros Libella Slim  
**Categoría**: Parafernalia

| Componente | Aporte | Decisión |
|------------|--------|----------|
| `"Filtros Libella Slim"` | ✅ Nombre canónico | Mantener |
| `"Parafernalia"` | ❌ Genérico, ruido | Eliminar |
| `"precio"` | ❌ Redundante | Eliminar |
| `"comprar"` | ✅ Contexto de compra | Mantener |

## Solución Implementada

### Nueva Función `build_search_query()`

```python
def build_search_query(product_name: str, category: str = "", sku: str = "") -> str:
    """
    Construye query de búsqueda simple y efectiva.
    
    Returns:
        Query optimizada: "{nombre_canonico} comprar"
    """
    if not product_name:
        raise ValueError("product_name es obligatorio")
    
    return f"{product_name.strip()} comprar"
```

### Cambios Clave

**ANTES**:
```python
parts = [product_name, sku, category, "precio", "comprar"]
return " ".join(parts).strip()
```

**DESPUÉS**:
```python
return f"{product_name.strip()} comprar"
```

### Beneficios

1. **Simplicidad**: Solo nombre canónico + "comprar"
2. **Precisión**: Sin ruido de categorías genéricas
3. **Relevancia**: Mejores resultados del buscador
4. **Mantenibilidad**: Menos complejidad en el código

## Testing

### Test Unitario

```bash
$ python test_query_builder.py

Test 1 - Solo nombre:
  Input:  product_name='Filtros Libella Slim'
  Output: 'Filtros Libella Slim comprar'
  ✅ OK

Test 2 - Con categoría (debe ignorarse):
  Input:  product_name='Filtros Libella Slim', category='Parafernalia'
  Output: 'Filtros Libella Slim comprar'
  ✅ OK
```

### Test de Integración

```bash
$ python test_discover_improved.py

Query nueva:    10 resultados
Query antigua:  10 resultados

Top resultados query nueva:
  1. MercadoLibre (marketplace)
  2. Libella Productos (fabricante oficial) ⭐
  3. Mercado de Tabacos (tienda)
  4. Mosby Tabaquería (tienda)
  5. Tabaquería Horus (tienda)
```

**Observación**: La query simplificada encuentra el **sitio oficial del fabricante** en 2º lugar.

## Casos de Uso

### Producto Estándar

```python
# Producto: "Carpa Indoor 80x80"
# Categoría: "Camping"
# SKU: "CAMP_0001_CAR"

query = build_search_query("Carpa Indoor 80x80", "Camping", "CAMP_0001_CAR")
# Resultado: "Carpa Indoor 80x80 comprar"
```

### Producto con Espacios Extra

```python
query = build_search_query("  Fertilizante Top Crop   ")
# Resultado: "Fertilizante Top Crop comprar"
```

### Nombre Vacío (Error Esperado)

```python
try:
    query = build_search_query("")
except ValueError as e:
    # "product_name es obligatorio para construir query de búsqueda"
```

## Impacto en Endpoints

### `/market/products/{id}/discover-sources`

**Flujo**:
1. Obtiene `product.name` (nombre canónico)
2. ~~Obtiene `category.name`~~ (ignorado)
3. ~~Obtiene `product.ng_sku`~~ (ignorado)
4. Construye query: `"{product.name} comprar"`
5. Llama MCP Web Search con query simplificada
6. Filtra y retorna fuentes válidas

**Antes**:
```
POST /market/products/23/discover-sources
Query: "Filtros Libella Slim Parafernalia precio comprar"
Resultados: Variable, a veces 0
```

**Después**:
```
POST /market/products/23/discover-sources
Query: "Filtros Libella Slim comprar"
Resultados: 10 fuentes válidas
```

## Criterios de Aceptación

- [x] Query simplificada a: `"{nombre} comprar"`
- [x] Categoría y SKU ignorados
- [x] "precio" eliminado
- [x] Tests unitarios pasando (5/5)
- [x] Test de integración exitoso
- [x] API actualizada y corriendo
- [x] Documentación creada

## Próximos Pasos

### Opcional: Variantes Contextuales

Si en el futuro necesitamos **contexto adicional** para productos ambiguos:

```python
# Ejemplo: productos genéricos que requieren marca
def build_search_query_advanced(product_name: str, brand: str = "") -> str:
    base = product_name.strip()
    
    # Agregar marca solo si el nombre es muy genérico
    if brand and len(base.split()) <= 2:
        base = f"{brand} {base}"
    
    return f"{base} comprar"

# Ejemplo:
# build_search_query_advanced("Filtros", brand="Libella")
# → "Libella Filtros comprar"
```

**Criterio**: Solo agregar contexto si el nombre canónico tiene ≤2 palabras.

### Monitoring

Agregar logs para analizar efectividad:

```python
logger.info(
    f"[discovery] Query: '{query}' | "
    f"Resultados MCP: {total_results} | "
    f"Fuentes válidas: {valid_sources}"
)
```

**Métricas sugeridas**:
- Promedio de fuentes válidas por producto
- Tasa de éxito (>0 fuentes vs total)
- Queries sin resultados (investigar por qué)

## Referencias

- **Archivo modificado**: `workers/discovery/source_finder.py`
- **Función**: `build_search_query()`
- **Tests**: `test_query_builder.py`, `test_discover_improved.py`
- **Endpoint**: `/market/products/{id}/discover-sources`

---

**Última actualización**: 2025-11-18  
**Autor**: Sistema de optimización de queries
