<!-- NG-HEADER: Nombre de archivo: SUPPLIERS.md -->
<!-- NG-HEADER: Ubicación: docs/SUPPLIERS.md -->
<!-- NG-HEADER: Descripción: Documentación de gestión de proveedores -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Gestión de Proveedores

Este documento describe el modelo extendido de proveedores, endpoints disponibles y el flujo de UI para crear y editar proveedores.

## Campos del modelo `Supplier`
Campo | Tipo | Descripción
----- | ---- | -----------
`id` | int | Identificador interno.
`slug` | str | Identificador único legible (p.e. `santaplanta`).
`name` | str | Nombre comercial.
`location` | str? | Ubicación / ciudad / referencia geográfica.
`contact_name` | str? | Nombre de contacto principal.
`contact_email` | str? | Email de contacto.
`contact_phone` | str? | Teléfono de contacto.
`notes` | text? | Notas libres internas.
`extra_json` | json? | Campo extensible para metadata futura.
`created_at` | datetime | Fecha de alta.

## Endpoints Backend

### Crear proveedor
```
POST /suppliers
Content-Type: application/json
Roles: admin
Body ejemplo:
{
  "slug": "santaplanta",
  "name": "Santa Planta",
  "location": "Buenos Aires",
  "contact_name": "Juan Pérez",
  "contact_email": "ventas@santaplanta.com",
  "contact_phone": "+54 11 5555-0000",
  "notes": "Condiciones: pago 30 días",
  "extra_json": {"priority": 1}
}
```

Respuesta (200 / 409 slug duplicado):
```jsonc
{
  "id": 12,
  "slug": "santaplanta",
  "name": "Santa Planta",
  "location": "Buenos Aires",
  "contact_name": "Juan Pérez",
  "contact_email": "ventas@santaplanta.com",
  "contact_phone": "+54 11 5555-0000",
  "notes": "Condiciones: pago 30 días",
  "extra_json": {"priority": 1},
  "created_at": "2025-09-13T17:05:00Z"
}
```

### Listar proveedores
```
GET /suppliers
Roles: cliente | proveedor | colaborador | admin
```
Devuelve listado con estadísticas (`files_count`, `last_upload_at`).

### Buscar proveedores (autocomplete)
```
GET /suppliers/search?q=<texto>&limit=20
Roles: cliente | proveedor | colaborador | admin
Respuesta 200 JSON: [{ id, name, slug }]
Notas:
- Busca por coincidencia en `name` o `slug` (ilike), ordenado por `name`.
- `limit` entre 1 y 50 (default 20).
```

### Obtener detalle
```
GET /suppliers/{id}
```
Devuelve todos los campos extendidos.

### Actualizar
```
PATCH /suppliers/{id}
Body parcial con los mismos campos (excepto `slug`). Rol: admin.
```

### Borrado masivo de proveedores
```
DELETE /suppliers
Roles: admin (requiere CSRF)
Body JSON:
{
  "ids": [1, 2, 3]
}
```
Respuesta 200 JSON:
```jsonc
{
  "requested": [1,2,3],
  "deleted": [1,3],
  "blocked": [
    { "id": 2, "reasons": ["has_purchases","has_files"], "counts": {"purchases": 2, "files": 1} }
  ],
  "not_found": []
}
```
Reglas de bloqueo por proveedor:
- `has_purchases`: existe alguna compra asociada al proveedor.
- `has_files`: existen archivos cargados del proveedor.
- `has_purchase_lines`: existen líneas de compra que referencian SKUs del proveedor.

Si no hay bloqueos, se elimina en cascada segura: equivalencias, historial de precios y `supplier_products` del proveedor, y luego el proveedor.

Ejemplo (PowerShell):
```powershell
curl -Method DELETE "http://localhost:8000/suppliers" `
  -Headers @{ 'X-CSRF-Token' = '<token>'; 'Content-Type' = 'application/json' } `
  -Body '{"ids":[10,11,12]}'
```

### Crear ítem de proveedor (oferta / SKU externo)
```
POST /suppliers/{supplier_id}/items
Roles: colaborador | admin
Body:
{
  "supplier_product_id": "SKU123",
  "title": "Sustrato Premium 5L",
  "product_id": 321,          // opcional: enlaza a producto interno
  "purchase_price": 1200.50,  // opcional
  "sale_price": 1890          // opcional
}
```
Conflicto: 409 `supplier_item_exists`.

### Vincular SKU de proveedor a variante interna (upsert)
```
POST /supplier-products/link
Roles: colaborador | admin (requiere CSRF)
Body:
{
  "supplier_id": 12,
  "supplier_product_id": "SKU123",
  "internal_variant_id": 456,
  "title": "Sustrato Premium 5L" // opcional
}
```
Comportamiento: si existe `(supplier_id, supplier_product_id)` se actualiza el vínculo a la variante indicada y el `title` si viene; si no existe, crea un `SupplierProduct` nuevo. Devuelve el registro resultante.

### Listar variantes de un producto interno
```
GET /products/{product_id}/variants
Roles: cliente | proveedor | colaborador | admin
Respuesta: [{ id, sku, name, value }]
```

## Flujo UI
1. Vista `Proveedores`: tabla con ID, Nombre, Slug, Ubicación, Contacto, Archivos.
2. Botón “Nuevo proveedor”: abre modal con campos básicos + contacto opcional.
3. Al crear, se redirige al detalle `/proveedores/:id`.
4. Detalle permite editar (modo edición) y guardar vía PATCH.
5. Notas se guardan junto con los demás campos (sin endpoint separado).
6. Se reservaron secciones futuras para listar documentos/facturas.
7. Ficha de producto: botón “Agregar SKU de proveedor” abre modal con:
  - Autocompletado de proveedor (GET /suppliers/search)
  - Campo `SKU proveedor`
  - Selector de variante interna (GET /products/{product_id}/variants)
  - Campo `Título` opcional
  Al guardar, invoca `POST /supplier-products/link` y refresca la tabla de ofertas de ese producto.

### Notas sobre SKUs en la ficha de producto

- SKU propio (interno): se edita a nivel variante mediante `PUT /variants/{variant_id}/sku` desde la ficha. Valida formato y unicidad y registra auditoría.
- SKU proveedor: se agrega/vincula usando el modal “Agregar SKU de proveedor” que invoca `POST /supplier-products/link`. Si el SKU ya existía para ese proveedor, el vínculo se actualiza a la variante seleccionada.

## Migración
Revisión: `extend_supplier_fields_20250913` (depende de `20250901_merge_images_and_import_logs`). Añade columnas sin valores obligatorios: operación segura para despliegue incremental.

## Consideraciones / Próximos pasos sugeridos
- Index opcional futuro sobre `contact_email` si se usa para búsqueda.
- Endpoint de subida/listado de archivos específicos del proveedor.
- Auditoría: actualmente sólo se registra alta de supplier_item; se puede ampliar para cambios de proveedor.
- Validaciones adicionales de formato (email / teléfono) pendientes.

## Ejemplo rápido de creación vía curl
```bash
curl -X POST http://localhost:8000/suppliers \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <token>" \
  -d '{"slug":"santaplanta","name":"Santa Planta"}'
```

## Checklist de esta entrega
- [x] Modelo extendido
- [x] Migración con `down_revision` correcto
- [x] Endpoints GET/POST/PATCH actualizados
- [x] Página listado + modal creación
- [x] Página detalle + edición + notas
- [x] Documentación (este archivo)

---

# Archivos de Proveedor

Se implementó una primera versión de gestión de archivos asociados al proveedor (facturas escaneadas, listas de precios, imágenes de referencia, spreadsheets). Los archivos se almacenan en disco bajo `data/suppliers/<supplier_id>/` y se registran metadatos en la tabla `supplier_files`.

## Campos del modelo `SupplierFile` (relevantes en API)
Campo | Tipo | Descripción
----- | ---- | -----------
`id` | int | Identificador del registro.
`supplier_id` | int | FK al proveedor.
`filename` | str | Nombre interno (hash recortado + extensión).
`original_name` | str | Nombre original cargado por el usuario.
`content_type` | str? | MIME detectado por el navegador.
`size_bytes` | int? | Tamaño del archivo.
`sha256` | str | Hash de contenido para detectar duplicados.
`rows` | int | Reservado (futuras importaciones estructuradas). Siempre 0 inicial.
`processed` | bool | Reservado (pipeline posterior). Inicial false.
`dry_run` | bool | Reservado. Inicial true.
`uploaded_at` | datetime | Timestamp de carga.
`notes` | text? | Notas opcionales enviadas en el formulario.

## Extensiones permitidas
`pdf, txt, csv, xls, xlsx, ods, png, jpg, jpeg, webp`

Variable de entorno para límite de tamaño: `SUPPLIER_FILE_MAX_BYTES` (default 10MB).

## Listar archivos
```
GET /suppliers/{supplier_id}/files
Roles: cliente | proveedor | colaborador | admin
Response 200 JSON:
[
  {
    "id": 5,
    "filename": "4ecce7ea6082.pdf",
    "original_name": "lista_precios_agosto.pdf",
    "sha256": "4ecce7ea6082e8bc3e2fbf9930f8206e03b94a0673804e9e2dc2e6663a48ae1b",
    "rows": 0,
    "processed": false,
    "dry_run": true,
    "uploaded_at": "2025-09-14T14:10:12.123456",
    "content_type": "application/pdf",
    "size_bytes": 123842
  }
]
```

## Subir archivo
```
POST /suppliers/{supplier_id}/files/upload
Roles: admin | colaborador
Headers: X-CSRF-Token
Content-Type: multipart/form-data
Campos:
  file: (obligatorio) archivo a subir
  notes: (opcional) texto breve
```
Respuestas:
* 200: JSON con metadatos. Si el hash ya existía para ese proveedor incluye `"duplicate": true`.
* 400: `{ "detail": "Tipo de archivo no permitido" }`.
* 404: Proveedor inexistente.
* 413: Archivo excede límite configurado.

Ejemplo (PowerShell):
```powershell
curl -X POST "http://localhost:8000/suppliers/1/files/upload" ^
  -H "X-CSRF-Token: <token>" ^
  -F "file=@C:/ruta/lista_precios.pdf" ^
  -F "notes=Lista agosto"
```

## Descargar archivo
```
GET /suppliers/files/{file_id}/download
Roles: cliente | proveedor | colaborador | admin
Descarga el binario con cabecera Content-Disposition.
```

## Idempotencia
Dos cargas del mismo contenido (independientemente del nombre original) retornan el primer registro con `duplicate: true` sin crear un segundo.

## Errores y códigos
Código | Motivo | Acción sugerida
------ | ------ | ---------------
400 | Extensión inválida | Validar extensión antes de enviar.
404 | Proveedor o archivo inexistente | Refrescar listado / verificar ID.
410 | Archivo perdido en disco | Re-subir; investigar limpieza manual.
413 | Tamaño excedido | Comprimir o aumentar `SUPPLIER_FILE_MAX_BYTES`.

## Seguridad / Riesgos
* Validación de extensión basada en nombre (pendiente: verificación MIME real con `python-magic`).
* Directorios aislados por proveedor.
* Hash previene duplicados silenciosos y facilita integridad.

## Próximos pasos sugeridos
1. Endpoint para eliminar archivo (soft delete + mover a `trash/`).
2. Procesamiento OCR / parsing de planillas (rellenar `rows`, `processed`).
3. Auditoría en `audit_log` para subidas/descargas sensibles.
4. Validación MIME real.

## Checklist archivos
- [x] Endpoints listar / subir / descargar
- [x] Metadata documentada
- [x] Límite y extensiones
- [x] Ejemplos curl
- [x] Errores comunes
- [x] Próximos pasos
