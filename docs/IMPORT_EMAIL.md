<!-- NG-HEADER: Nombre de archivo: IMPORT_EMAIL.md -->
<!-- NG-HEADER: Ubicación: docs/IMPORT_EMAIL.md -->
<!-- NG-HEADER: Descripción: Notas de importación por email (POP) y heurísticas del parser -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Importación por Email (POP)

Este documento resume el flujo de importación de remitos/correos de POP y las heurísticas del parser.

## Flujo

- Endpoint backend: `POST /purchases/import/pop-email?supplier_id={id}&kind=eml|html|text`.
- UI: Modal “POP (Email)” permite subir `.eml` o pegar HTML/TEXT del correo.
- Resultado: Se crea una Compra en estado `BORRADOR` con líneas y SKU sintético `POP-YYYYMMDD-###` (editable en UI).

## Heurísticas del parser

- Preferencia de HTML si está disponible; fallback a texto plano.
- Extracción de número de remito/pedido desde `Subject` o desde el cuerpo (patrón: `Pedido|Remito|Orden <número>`).
- Detección de tabla con encabezados comerciales (Producto/Descripción, Cantidad, Precio/Subtotal/Total). Si el encabezado es débil, se elige la columna de título por mayor densidad de letras.
- Cantidad: se toma el primer número plausible de la celda (no se concatenan todos los dígitos). Se aplica clamp de seguridad: `qty <= 0` o `qty >= 100000` → `qty = 1`.
- Precio unitario: tolerante a formatos `es-AR` (`$1.234,56`). Clamp: `< 0` o `> 10.000.000` → `0`.
- Filtrado de ruido: se descartan filas típicas de disclaimers o contacto (por ejemplo: “WhatsApp de Atención al cliente…”, “Distribuidora Pop … Todos Derechos Reservados”).
- Si no se identifica cantidad/precio, se crea la línea con `qty=1` y `unit_cost=0` (editable en la app).
 - Estimación de cantidad de líneas por símbolos `$`: se cuenta el total de `$` en el cuerpo (HTML convertido a texto) y se resta 3 por los sumarios estándar (`Subtotal`, `Total`, `Ahorro`). Si el parser detecta menos líneas que esta estimación, se aplica un fallback que extrae líneas basadas en renglones que contienen `$` y texto, para no subcontar. Esta estimación se expone en `parse_debug` como `dollar_signs` y `estimated_product_lines`.

### Reglas específicas POP para títulos
- Limpieza de ruido en títulos: se eliminan tokens “Comprar por:x N”, “Tamaño:…”, y sufijos “- x N” cuando son solo empaque.
- Validación mínima: los títulos deben tener al menos 2 palabras con letras y totalizar al menos 5 letras (evita títulos puramente numéricos o ruido).
- No confundir “pack x N” con cantidad comprada: la cantidad se toma de su columna/celda si existe; la pista de pack no altera qty y solo se registra en debug.

## iAVaL (validación asistida) – reglas POP en el prompt
- Títulos descriptivos: al menos 2 palabras con letras y ≥5 letras totales. Evitar títulos puramente numéricos.
- Limpiar tokens de ruido: “Comprar por:x N”, “Tamaño:…”, sufijos “- x N”.
- No confundir “pack x N” con cantidad comprada; priorizar columna/celda “Cantidad”. No inferir qty desde pack si ya hay columna cantidad.
- Preferir columnas/segmentos con mayor densidad de letras y descartar disclaimers/contacto o sumarios (Subtotal/Total/Ahorro).
- El importador estima renglones por símbolos “$” y resta 3 por sumarios; no proponer eliminar líneas únicamente por desbalance con esa estimación.
- El importador puede haber aplicado un “segundo pase” uniendo celdas por fila cuando la tabla está fragmentada; considerar títulos más largos como válidos si cumplen las reglas de POP y no son ruido.

## Pruebas rápidas

- Unit tests: `tests/test_pop_email_overflow.py` valida el filtrado de disclaimers y los clamps de cantidad.
- E2E (UI): ver tests Playwright en `tests/e2e` para el modal de POP.

## Notas

- Unicidad: el backend evita compras duplicadas por `(supplier_id, remito_number)`. Si el remito no puede extraerse, el fallback es derivarlo del archivo `.eml`; evitar subir el mismo archivo dos veces.
- iAVaL: la validación acepta `PDF` o `EML` adjuntos para proponer correcciones (preferencia por PDF si existe).
<!-- NG-HEADER: Nombre de archivo: IMPORT_EMAIL.md -->
<!-- NG-HEADER: Ubicación: docs/IMPORT_EMAIL.md -->
<!-- NG-HEADER: Descripción: Guía para importar compras desde correos (.eml) extrayendo adjuntos PDF -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
## Pruebas E2E del modal POP (Playwright)

Para validar desde la UI el flujo de “POP (Email)” se añadieron pruebas E2E con Playwright:

- Ubicación: `tests/e2e/`
	- `test_pop_modal_eml.py`: sube un `.eml` y verifica la creación de la compra y SKUs sintéticos.
	- `test_pop_modal_text.py`: pega HTML/TEXTO y verifica el mismo resultado.

Requisitos previos:
- Backend encendido (`start.bat` levanta backend y sirve el frontend compilado).
- Playwright instalado (el `start.bat` ya intenta `python -m playwright install chromium`).

Ejecución (Windows PowerShell):

```powershell
cd C:\Proyectos\NiceGrow\Growen
.\.venv\Scripts\python.exe -m pytest -q tests\e2e
```

Variables opcionales:
- `E2E_BASE_URL`: cambiar la URL base si no es `http://127.0.0.1:8000`.
- `E2E_POP_EML`: ruta del `.eml` para la prueba (por defecto usa `Devs/Pedido 488344 Completado.eml`).

Notas:
- Las pruebas asumen que el botón “Cargar compra” y el menú “POP (Email)” están visibles en Compras.
- Si la lista de proveedores está vacía, el test intenta crear `POP` (slug `pop`) vía fetch.


# Importación de compras desde Email (.eml)

Cuando un proveedor (por ejemplo, POP) envía los remitos por correo, la forma más simple y robusta de incorporarlos al flujo existente es:

1) Extraer los adjuntos PDF del correo (.eml).
2) Usar el importador de PDF actual (Compras → Importar PDF) para crear el BORRADOR y líneas.

Esta guía muestra el camino mínimo viable y deja la puerta abierta a automatizar luego por IMAP.

## Opción A: Manual mínima (recomendada para empezar)

- Guardá el email como .eml (por ejemplo: "Pedido 488344 Completado.eml").
- Ejecutá el script de extracción para guardar los PDF en `data/inbox/pop`:

```bash
python scripts/extract_eml_attachments.py --eml "C:/Users/<usuario>/Downloads/Pedido 488344 Completado.eml"
```

- Abrí la app → Compras → Importar PDF, seleccioná el proveedor POP y subí el PDF extraído.

Ventajas:
- Cero cambios en backend. Reutiliza OCR/IA/heurísticas existentes.
- Permite probar ya, con baja fricción.

## Opción B: Importación directa de Email POP (sin PDF)

Cuando POP no adjunta PDF y discrimina productos en el cuerpo del mail:

- Endpoint nuevo: `POST /purchases/import/pop-email`
	- Modo .eml: subir el archivo del correo (adjuntar en `file`, `kind=eml`).
	- Modo HTML/TEXT: enviar el contenido en el body (`{ text: "..." }`) y `kind=html|text`.
	- Genera un BORRADOR con líneas y crea SKU sintético si falta (formato `POP-YYYYMMDD-###`). Este SKU es editable desde la pantalla de compra para sincronizar con el catálogo.

Notas:
- El `remito_number` se toma del Asunto si es posible (p. ej. "Pedido 488344"). Si no, usa un valor por defecto (p. ej. nombre de archivo o "POP").
- Las líneas quedan en estado `SIN_VINCULAR` para que las vincules (buscador por título o completando SKU luego).
- El iAVaL puede ayudar a ajustar cantidades y precios si hay ambigüedad.

Ejemplo (PowerShell) con .eml:
```powershell
# Enviar .eml (vía cliente HTTP o desde UI futura)
# Aquí ilustrativo con curl; en la app habrá un modal/acción específica.
curl -F "file=@C:\Users\<usuario>\Downloads\POP_mail.eml" "http://localhost:8000/purchases/import/pop-email?supplier_id=ID_POP&kind=eml"
```

---

## Opción C: Automatización futura (IMAP watcher)

Si más adelante se desea, se puede agregar un proceso que:
- Conecte a la casilla IMAP (ej. `compras@tu-dominio`),
- Filtre correos de POP por remitente/asunto,
- Descargue adjuntos PDF y los guarde en `data/inbox/pop`,
- Opcional: consuma el endpoint `/purchases/import/santaplanta` (o uno específico si se crea `/purchases/import/pop`).

Requisitos a definir:
- Casilla dedicada o reglas de reenvío.
- Variables de entorno seguras: `IMAP_HOST`, `IMAP_USER`, `IMAP_PASS`, `IMAP_FOLDER`.
- Política anti-duplicados (ya existe por hash + (supplier, remito)).

## Notas y mejores prácticas

- El importador ya deduplica por `(supplier_id, remito_number)` y por hash del PDF.
- Si el pipeline no detecta líneas y `IMPORT_ALLOW_EMPTY_DRAFT=true`, se crea BORRADOR con el PDF adjunto (útil para validación posterior con iAVaL).
- iAVaL (botón en Detalle de compra) permite corregir header/líneas comparando el PDF.

## Troubleshooting

- Si el adjunto viene como `application/octet-stream` sin extensión, el extractor agrega `.pdf` por defecto.
- Si al importar falla OCR, activá "Forzar OCR" en el modal.
- Revisá `logs/backend.log` y los logs de importación en la pantalla de la compra (pestaña Logs).
 - Para POP-email: si no se detectan bien las columnas HTML, el parser cae a heurísticas de texto. Podés editar cantidades/precios en la UI.

---
Actualizado: 2025-09-23.
