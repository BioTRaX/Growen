<!-- NG-HEADER: Nombre de archivo: MERCADO_EDICION_PRECIOS.md -->
<!-- NG-HEADER: Ubicación: docs/features/MERCADO_EDICION_PRECIOS.md -->
<!-- NG-HEADER: Descripción: Guía de funcionalidad de edición de precios en módulo Mercado -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Edición de Precios en Módulo Mercado

**Fecha de implementación**: 2025-11-11  
**Autor**: Extensión de Etapa 4 del módulo Mercado

## Resumen

Esta funcionalidad permite a usuarios autorizados (admin y colaboradores) editar directamente desde la UI del módulo Mercado:
1. **Precio de venta** del producto
2. **Valor de mercado de referencia** (manual)

Ambos campos se encuentran en el modal de detalles del producto, con validaciones robustas y feedback visual inmediato.

## Casos de Uso

### 1. Actualización rápida de precio de venta
**Escenario**: Un colaborador necesita ajustar el precio de venta de un producto después de revisar los precios del mercado.

**Flujo**:
1. Abrir página Mercado (`/mercado`)
2. Clic en botón "👁️ Ver" del producto deseado
3. En la sección "Gestión de Precios", clic en el campo "Precio de Venta"
4. Ingresar nuevo valor (ej. 1500.00)
5. Presionar Enter o clic en ✓
6. Ver confirmación "Precio de venta actualizado correctamente"
7. La tabla principal se refresca automáticamente

### 2. Corrección manual de valor de mercado
**Escenario**: El scraping automático falló o se requiere ingresar un valor conocido de otra fuente no automatizada.

**Flujo**:
1. Abrir modal de detalles del producto
2. Clic en campo "Valor Mercado (Referencia)"
3. Ingresar valor manual (ej. 1200.00)
4. Presionar Enter
5. Ver confirmación "Valor de mercado de referencia actualizado"

### 3. Cancelación de edición
**Escenario**: Usuario se arrepiente del cambio o ingresó valor incorrecto.

**Flujo**:
1. Iniciar edición de precio
2. Presionar Esc o clic en ✕
3. Campo vuelve a modo lectura sin guardar cambios

## Componentes Implementados

### 1. `EditablePriceField.tsx`

Componente reutilizable para editar campos de precio.

**Características**:
- **Dual mode**: Lectura (con ícono ✏️) y edición (input + botones)
- **Validación**: Números positivos, máximo 999,999,999
- **Atajos**: Enter (guardar), Esc (cancelar)
- **Loading**: Estados visuales durante guardado
- **Formato**: Prefijo personalizable (default: `$`)
- **Accesibilidad**: Focus automático, select del texto, hints visuales

**Props**:
```typescript
{
  label: string              // Etiqueta del campo
  value: number | null       // Valor actual
  onSave: (n: number) => Promise<void>  // Callback async al guardar
  disabled?: boolean         // Deshabilita edición
  placeholder?: string       // Texto cuando value es null
  formatPrefix?: string      // Prefijo de formato (default: '$')
}
```

**Ejemplo de uso**:
```tsx
<EditablePriceField
  label="Precio de Venta"
  value={salePrice}
  onSave={async (newPrice) => {
    await updatePrice(productId, newPrice)
    setSalePrice(newPrice)
  }}
/>
```

### 2. Funciones en `market.ts`

#### `updateProductSalePrice(productId, salePrice, note?)`
- Actualiza precio de venta del producto
- **Endpoint esperado**: `PATCH /products-ex/products/{id}/sale-price`
- Parámetro opcional `note` para auditoría
- Retorna: `{ id: number, sale_price: number }`

#### `updateMarketReference(productId, marketReference)`
- Actualiza valor de mercado de referencia manual
- **Endpoint esperado**: `PATCH /products/{id}/market-reference`
- Retorna: `{ id: number, market_price_reference: number }`

#### `validatePrice(value)`
- Valida que el valor sea número positivo
- Máximo: 999,999,999
- Retorna: `{ valid: boolean, error?: string }`
- Mensajes de error específicos

### 3. Integración en `MarketDetailModal.tsx`

**Nueva sección "Gestión de Precios"**:
- Grid de 3 columnas
- 2 campos editables + 1 campo solo lectura (rango)
- Ubicada entre header y lista de fuentes
- Tip explicativo al final

**Handlers agregados**:
- `handleSaveSalePrice`: Actualiza precio, refresca estado local, notifica padre
- `handleSaveMarketReference`: Similar para valor de mercado

**Interfaz extendida `ProductSourcesResponse`**:
```typescript
{
  product_id: number
  product_name: string
  sale_price: number | null               // ⬅️ nuevo
  market_price_reference: number | null   // ⬅️ nuevo
  market_price_min: number | null         // ⬅️ nuevo
  market_price_max: number | null         // ⬅️ nuevo
  mandatory: MarketSource[]
  additional: MarketSource[]
}
```

## Validaciones

### Cliente (JavaScript)

Función `validatePrice` en `market.ts`:

1. **Tipo**: Debe ser número válido
   - `isNaN()` → "Debe ingresar un número válido"

2. **Rango mínimo**: Mayor a cero
   - `value <= 0` → "El precio debe ser mayor a cero"

3. **Rango máximo**: Menor a mil millones
   - `value > 999999999` → "El precio es demasiado alto"

### Servidor (Backend - Pendiente Etapa 2)

Recomendaciones para validación backend:

```python
# Pseudo-código
def validate_price(price: float):
    if price <= 0:
        raise ValueError("El precio debe ser mayor a cero")
    if price > 999999999:
        raise ValueError("El precio excede el límite permitido")
    # Validar decimales (máximo 2)
    if round(price, 2) != price:
        raise ValueError("Máximo 2 decimales permitidos")
```

## Feedback Visual

### Toasts (Notificaciones)

**Éxito**:
- ✓ "Precio de venta actualizado correctamente"
- ✓ "Valor de mercado de referencia actualizado"

**Error**:
- ⚠ "Error actualizando precio de venta"
- ⚠ "Error actualizando valor de mercado"
- ⚠ Mensaje de validación específico (ej. "Debe ingresar un número válido")

### Estados del Campo

1. **Lectura**: Hover con cursor pointer, fondo sutil
2. **Edición**: Border destacado, botones visibles
3. **Loading**: Cursor wait, opacidad 60%, botones deshabilitados
4. **Error**: Border rojo, mensaje bajo el input

### Hints

- Texto pequeño bajo el input: "Enter para guardar, Esc para cancelar"
- Tip en la sección: "💡 **Tip:** Haz clic en los campos con ✏️ para editar"

## Control de Acceso

**Roles permitidos**:
- ✅ `admin`
- ✅ `colaborador`
- ❌ `viewer` (no tiene acceso a página Market)

**Implementación actual**:
- Control a nivel de ruta: `/mercado` protegida con `useAuth()`
- Si el usuario no tiene rol apropiado, no puede acceder a la página

**Mejora futura** (opcional):
- Agregar prop `disabled` a `EditablePriceField` basado en rol específico
- Permitir que `viewer` vea la página pero no edite precios

## Sincronización de Datos

### Flujo de actualización

```
Usuario edita → Validación cliente → Llamada API →
Backend actualiza DB → Response OK →
Actualiza estado local del modal → Toast éxito →
Callback onPricesUpdated() → Tabla principal refresca
```

### Prevención de inconsistencias

1. **Actualización optimista del estado local**:
   ```typescript
   setSources({ ...sources, sale_price: newPrice })
   ```
   
2. **Callback al padre**:
   ```typescript
   onPricesUpdated?.()  // Refresca tabla Market.tsx
   ```

3. **En caso de error**: Re-lanzar excepción para que el componente maneje el rollback

### Refresh automático

Después de guardar exitosamente:
- Estado local del modal se actualiza inmediatamente
- Tabla principal (`Market.tsx`) ejecuta `loadProducts()`
- Usuario ve valores actualizados sin cerrar el modal

## Endpoints Backend Requeridos

### 1. Actualizar precio de venta (ya existe)

```http
PATCH /products-ex/products/{id}/sale-price
Content-Type: application/json

{
  "sale_price": 1500.00,
  "note": "Ajuste manual desde Mercado" (opcional)
}
```

**Response**:
```json
{
  "id": 123,
  "sale_price": 1500.00
}
```

### 2. Actualizar valor de mercado (nuevo)

```http
PATCH /products/{id}/market-reference
Content-Type: application/json

{
  "market_price_reference": 1200.00
}
```

**Response**:
```json
{
  "id": 123,
  "market_price_reference": 1200.00
}
```

### 3. Actualizar GET /products/{id}/market/sources

Debe incluir campos adicionales en la respuesta:

```json
{
  "product_id": 123,
  "product_name": "Producto X",
  "sale_price": 1500.00,              // ⬅️ agregar
  "market_price_reference": 1200.00,  // ⬅️ agregar
  "market_price_min": 1180.00,        // ⬅️ agregar
  "market_price_max": 1300.00,        // ⬅️ agregar
  "mandatory": [...],
  "additional": [...]
}
```

## Migración de Base de Datos

Campo nuevo requerido en tabla `products`:

```sql
ALTER TABLE products 
ADD COLUMN market_price_reference NUMERIC(10,2) DEFAULT NULL;

COMMENT ON COLUMN products.market_price_reference IS 
  'Valor de mercado de referencia ingresado manualmente. 
   Usado cuando scraping falla o se requiere valor específico.';
```

**Índice** (opcional, para queries futuras):
```sql
CREATE INDEX idx_products_market_ref 
ON products(market_price_reference) 
WHERE market_price_reference IS NOT NULL;
```

## Testing

### Unit Tests (Componentes)

```typescript
// tests/EditablePriceField.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import EditablePriceField from '../EditablePriceField'

describe('EditablePriceField', () => {
  it('permite editar y guardar valor', async () => {
    const onSave = jest.fn().mockResolvedValue(undefined)
    
    render(<EditablePriceField label="Precio" value={100} onSave={onSave} />)
    
    // Clic para entrar en modo edición
    fireEvent.click(screen.getByText('$ 100.00'))
    
    // Cambiar valor
    const input = screen.getByRole('spinbutton')
    fireEvent.change(input, { target: { value: '150' } })
    
    // Guardar con Enter
    fireEvent.keyDown(input, { key: 'Enter' })
    
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(150))
  })
  
  it('muestra error con valor inválido', async () => {
    const onSave = jest.fn()
    
    render(<EditablePriceField label="Precio" value={100} onSave={onSave} />)
    
    fireEvent.click(screen.getByText('$ 100.00'))
    
    const input = screen.getByRole('spinbutton')
    fireEvent.change(input, { target: { value: '-50' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    
    expect(await screen.findByText(/debe ser mayor a cero/i)).toBeInTheDocument()
    expect(onSave).not.toHaveBeenCalled()
  })
})
```

### Integration Tests (Modal)

```typescript
// tests/MarketDetailModal.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import MarketDetailModal from '../MarketDetailModal'
import * as marketService from '../../services/market'

jest.mock('../../services/market')

describe('MarketDetailModal - Edición de precios', () => {
  it('actualiza precio de venta correctamente', async () => {
    const mockUpdate = jest.spyOn(marketService, 'updateProductSalePrice')
      .mockResolvedValue({ id: 1, sale_price: 1500 })
    
    const mockSources = {
      product_id: 1,
      product_name: 'Test',
      sale_price: 1000,
      market_price_reference: 900,
      mandatory: [],
      additional: []
    }
    
    jest.spyOn(marketService, 'getProductSources').mockResolvedValue(mockSources)
    
    render(<MarketDetailModal productId={1} open onClose={jest.fn()} />)
    
    await waitFor(() => screen.getByText('$ 1,000.00'))
    
    // Editar precio de venta
    fireEvent.click(screen.getByText('$ 1,000.00'))
    const input = screen.getByDisplayValue('1000')
    fireEvent.change(input, { target: { value: '1500' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    
    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(1, 1500)
      expect(screen.getByText(/actualizado correctamente/i)).toBeInTheDocument()
    })
  })
})
```

### E2E Tests (Playwright/Cypress)

```typescript
// e2e/market-edit-prices.spec.ts
test('usuario puede editar precio de venta desde modal', async ({ page }) => {
  await page.goto('/mercado')
  
  // Abrir modal del primer producto
  await page.click('button:has-text("👁️ Ver")')
  
  // Esperar que cargue el modal
  await page.waitForSelector('text=Gestión de Precios')
  
  // Editar precio de venta
  await page.click('text=Precio de Venta >> .. >> text=/\\$ [0-9,]+\\.[0-9]{2}/')
  await page.fill('input[type="number"]', '1500')
  await page.press('input[type="number"]', 'Enter')
  
  // Verificar toast de éxito
  await expect(page.locator('text=actualizado correctamente')).toBeVisible()
  
  // Verificar que el valor cambió en el modal
  await expect(page.locator('text=$ 1,500.00')).toBeVisible()
})
```

## Auditoría y Historial (Futuro)

### Registro de cambios

Tabla recomendada: `product_price_history`

```sql
CREATE TABLE product_price_history (
  id SERIAL PRIMARY KEY,
  product_id INT REFERENCES products(id) ON DELETE CASCADE,
  field_name VARCHAR(50) NOT NULL, -- 'sale_price' o 'market_price_reference'
  old_value NUMERIC(10,2),
  new_value NUMERIC(10,2),
  changed_by INT REFERENCES users(id),
  changed_at TIMESTAMP DEFAULT NOW(),
  note TEXT
);

CREATE INDEX idx_price_history_product ON product_price_history(product_id, changed_at DESC);
CREATE INDEX idx_price_history_user ON product_price_history(changed_by);
```

### Visualización en UI (próxima iteración)

Agregar pestaña "Historial" en `MarketDetailModal`:
- Tabla con columnas: Fecha, Campo, Valor anterior, Valor nuevo, Usuario, Nota
- Filtros: Últimos 7/30/90 días
- Exportar a CSV

## Preguntas Frecuentes

### ¿Qué pasa si edito el precio mientras está actualizando las fuentes?

El botón de guardar se deshabilita durante operaciones async. Si ya hay una actualización en curso, el usuario debe esperar.

### ¿Puedo editar múltiples campos a la vez?

Cada campo se edita individualmente. Para edición masiva, usar la funcionalidad de actualización masiva en la tabla principal (fuera de alcance de este módulo).

### ¿El valor de mercado de referencia afecta el rango automático?

No. El rango (`market_price_min` - `market_price_max`) se calcula exclusivamente desde las fuentes configuradas. El valor de referencia es un campo separado para uso manual.

### ¿Se puede deshacer un cambio?

No hay función "deshacer" en la UI actual. Sin embargo, si se implementa auditoría, un administrador puede revisar el historial y revertir manualmente.

### ¿Qué sucede si el backend está caído?

El componente muestra un toast de error: "Error actualizando precio de venta". El valor en la UI no cambia. El usuario puede reintentar.

## Conclusión

Esta funcionalidad completa el flujo de gestión de precios en el módulo Mercado, permitiendo ajustes rápidos y manuales sin salir de la interfaz. La implementación es robusta, con validaciones en múltiples niveles y feedback claro al usuario.

**Próximos pasos sugeridos**:
1. Implementar endpoints backend (Etapa 2)
2. Agregar auditoría de cambios
3. Agregar historial visual en el modal
4. Tests automatizados (unit + integration + e2e)

---

**Última actualización**: 2025-11-11  
**Documentos relacionados**:
- `docs/features/MERCADO.md` - Plan maestro
- `docs/MERCADO_IMPLEMENTACION.md` - Detalles técnicos completos
- `docs/features/MERCADO_FILTROS.md` - Sistema de filtros
