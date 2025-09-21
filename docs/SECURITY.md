<!-- NG-HEADER: Nombre de archivo: SECURITY.md -->
<!-- NG-HEADER: Ubicación: docs/SECURITY.md -->
<!-- NG-HEADER: Descripción: Política de seguridad del proyecto -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Seguridad

## Manejo de secretos
- Nunca versionar archivos `.env` ni credenciales.
- Utilizar gestores de secretos cuando sea posible.

## Política de scraping
- Solo se permiten fuentes en la whitelist del proyecto.
- Respetar términos de uso y legislaciones vigentes.

## Permisos por rol
- Asignar el mínimo de permisos necesarios a cada rol.
- Consultar documentación funcional para detalles específicos.

## Cifrado y PDFs (Plan ARC4)
Durante la importación de remitos PDF (ej. proveedor Santa Planta) se observó un `CryptographyDeprecationWarning` relacionado con ARC4. Aunque la aplicación no solicita explícitamente RC4/ARC4, algunas librerías pueden intentar compatibilidad retro.

### Riesgo
- ARC4 (RC4) es un cifrado considerado inseguro y está en proceso de eliminación en futuras versiones de `cryptography`.
- Riesgo de ruptura futura al actualizar dependencias si se remueve soporte.

### Medidas adoptadas
1. Script `scripts/check_pdf_crypto.py` para auditar PDFs y detectar uso de RC4.
2. No se detecta uso directo de ARC4 en el código (`grep` sin coincidencias `ARC4|RC4`).
3. Se planificará upgrade de librerías PDF priorizando versiones que eviten fallback RC4.
4. Se mantendrá registro de hashes SHA256 para integridad básica (script).

### Plan de acción
| Paso | Acción | Éxito | Rollback |
|------|--------|-------|----------|
| 1 | Ejecutar `python scripts/check_pdf_crypto.py data/purchases --recursive --json` | Sin PDFs ARC4 | N/A |
| 2 | Fijar versión explícita segura de `pypdf` (añadir a requirements si procede) | No warnings | Revertir pin |
| 3 | Actualizar `cryptography` a última minor soportada y correr suite de importación | Import OK, sin warnings | Volver a versión previa en lock |
| 4 | A?adir test que falla si aparece warning ARC4 (pytest filterwarnings) | Implementado (`pytest.ini` + `tests/test_pytest_filter_arc4.py`) | Ajustar filtro si surge falso positivo |

### Próximos pasos
- Crear issue: "Deprecación ARC4 / Auditoría PDFs" con checklist anterior.
- Añadir verificación periódica en pipeline (QA) usando el script.

## Logging
- Evitar duplicación de handlers (pendiente refactor). Cada request debe loguearse una sola vez.
- Normalizar encoding UTF-8 (`PYTHONUTF8=1`) para evitar caracteres reemplazados.

## Manejo de errores de integridad
- Los errores de unicidad (p.ej. SKU duplicado) ahora se mapean a HTTP 409 mediante handler global `IntegrityError`.
- Respuesta estandarizada para conflictos conocidos:

	```json
	{"detail": "SKU ya existe", "code": "duplicate_sku", "field": "sku"}
	```

	Para otros constraints se retorna `code: conflict` con detalle genérico.
- Validación temprana en `POST /catalog/products` verifica formato y existencia del SKU antes de intentar insertar (reduce volumen de excepciones).
- Próximo (mejora): unificar todos los errores de validación bajo un esquema común `{detail, code, field?}` y agregar correlación (`request_id`).

## Validación de entradas
- Asegurar sanitización de parámetros para consultas / regex.
- Se agregó validación de formato SKU `[A-Za-z0-9._-]{2,50}` y trimming.
- Se añadió campo opcional `sku` en creación mínima (`POST /catalog/products`), derivando de `supplier_sku` o `title` si falta.
- Próximo: reforzar validaciones en `POST /products` (rol y formato de SKU) y centralizar regex en constante reutilizable.

## Excepciones CSRF controladas
- `POST /bug-report` no requiere CSRF por diseño para permitir reportes sin sesión. Solo escribe en un log local (`logs/BugReport.log`) sin tocar datos de negocio.
- El frontend advierte no incluir datos sensibles en el comentario. Se envían como contexto la URL actual, el User-Agent y hora local en GMT-3.

