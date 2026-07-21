<!-- NG-HEADER: Nombre de archivo: SECURITY.md -->
<!-- NG-HEADER: Ubicación: docs/SECURITY.md -->
<!-- NG-HEADER: Descripción: Política de seguridad del proyecto -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Seguridad

## Manejo de secretos
- Nunca versionar archivos `.env` ni credenciales.
- Utilizar gestores de secretos cuando sea posible.

## Publicación Git y auditoría previa

- Antes de un push, revisar archivos sensibles y patrones de alta confianza en el contenido final y en las líneas agregadas.
- Los reportes de auditoría deben mostrar solo archivo, línea, variable y categoría. No imprimir valores coincidentes, incluso al investigar falsos positivos.
- Confirmar que los archivos de entorno versionados sean exclusivamente ejemplos. Un valor de ejemplo no debe parecer una credencial real ni reutilizarse en despliegues.
- Los fragmentos con forma de token dentro de `package-lock.json` deben validarse por contexto; una coincidencia dentro de `integrity` es un hash de cadena de suministro, no una credencial.
- La credencial PostgreSQL de desarrollo expuesta por el script legacy de Mercado fue rotada e invalidada el 2026-07-21. `scripts/rotate_dev_db_password.ps1` actualiza `POSTGRES_PASSWORD`, `DB_PASS` y la credencial embebida en `DB_URL` sin imprimir valores; luego deben recrearse los consumidores y reiniciarse la API, nunca el volumen.
- Resolver la URL del remoto antes de publicar. Si el destino externo no puede verificarse como confiable o privado, informar el alcance y obtener aprobación explícita.
- Después del push, verificar que el SHA local coincida con la referencia remota esperada.

## Política de scraping
- Solo se permiten fuentes en la whitelist del proyecto.
- Respetar términos de uso y legislaciones vigentes.

## Permisos por rol
- Asignar el mínimo de permisos necesarios a cada rol.
- Consultar documentación funcional para detalles específicos.

## Contrato de sesión y CSRF

- `create_session()` genera un SID aleatorio crudo, persiste únicamente `hash_session_id(sid)` y devuelve ambos valores por separado.
- La cookie `growen_session` contiene el SID crudo; `current_session()` lo hashea una sola vez para consultar la base.
- Nunca enviar `Session.id` al navegador: ese campo ya contiene el hash persistido.
- `csrf_token` es legible por el frontend y debe coincidir con `X-CSRF-Token` en toda mutación protegida.
- Todo cambio en este ciclo requiere una prueba con `@pytest.mark.no_auth_override`; los overrides globales de tests no prueban cookies, resolución de rol ni CSRF reales.

## Salida a Internet (IA y MCP Web Search)
- Las llamadas externas de IA están controladas por flags de entorno:
	- `ai_allow_external` (configuración global): si es `false`, se bloquean integraciones externas.
	- `AI_USE_WEB_SEARCH`: habilita la búsqueda web MCP durante el enriquecimiento de productos.
- La búsqueda web MCP (MVP) consulta un motor público (DuckDuckGo HTML por defecto) y retorna títulos/URLs/snippets. Recomendación para producción: usar un proveedor con SLA y caching.
- Products y Web Search exigen `Authorization: Bearer <JWT>` con issuer, audience, sujeto, rol, expiración y JTI.
- El rol procede de la sesión autenticada y no se acepta como argumento de la tool.
- El cliente filtra el catálogo por rol y cada servidor vuelve a autorizar la invocación.
- Los logs MCP no incluyen tokens, prompts completos ni argumentos sensibles.
- El rate limiter MCP usa Redis en Compose; el modo por proceso queda reservado a desarrollo y tests.
- Solo roles `admin` y `colaborador` pueden invocar el enriquecimiento IA y, por ende, la búsqueda web cuando la flag está activa.
- Auditoría: se registran `web_search_query_hash` y `web_search_hits` por cada enriquecimiento, además del `prompt_hash`; no se persiste el texto completo de la consulta.

## Cifrado y PDFs (Plan ARC4)
Durante la importación de remitos PDF (ej. proveedor Santa Planta) se observó un `CryptographyDeprecationWarning` relacionado con ARC4. Aunque la aplicación no solicita explícitamente RC4/ARC4, algunas librerías pueden intentar compatibilidad retro.

### Riesgo
- ARC4 (RC4) es un cifrado considerado inseguro y está en proceso de eliminación en futuras versiones de `cryptography`.
- Riesgo de ruptura futura al actualizar dependencias si se remueve soporte.

### Medidas adoptadas
1. Script `scripts/check_pdf_crypto.py` para auditar PDFs y detectar uso de RC4.
2. No se detecta uso directo de ARC4 en el código (`grep` sin coincidencias `ARC4|RC4`).
3. Upgrade aplicado: dependencias fijadas a `pypdf>=4.3` y `pdfplumber>=0.11` (ver `requirements.txt`) que eliminan el warning por ARC4 en `cryptography`.
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
 - Ejecutar suite `tests/test_parse_remito_sample_pdf.py` y `tests/test_santaplanta_*` tras cambios de dependencia.

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

## Endurecimiento agéntico y MCP

- Las cabeceras `X-User-Roles` y `X-User-Id` solo se aceptan con `ENV=test`; fuera de tests no otorgan identidad.
- No existen claves MCP predecibles. Products y Web Search usan claves, audiences y `kid` independientes, TTL máximo y revocación por `jti`.
- El catálogo de tools aplica deny-by-default. Una tool nueva no se entrega al modelo hasta contar con una política de roles explícita.
- Los resultados de Web Search se consideran contenido externo no confiable: se limitan tamaño, profundidad, caracteres invisibles, esquemas URL y hosts de salida.
- Las consultas con patrones de secretos no se envían a buscadores externos. `trust_env` y redirects están deshabilitados.
- Las tools actuales son de lectura. Toda futura tool con escritura debe requerir política explícita, autorización de servidor y confirmación humana para efectos materiales.
- Los SID se almacenan hasheados. Los logs no incluyen SID, JWT, parámetros MCP ni prompts completos.
- El rate limiting MCP y la revocación usan Redis en Compose y fallan cerrados. El modo memoria solo se admite en desarrollo y tests.
- La autenticación JWT interna no sustituye OAuth para acceso remoto; los puertos de desarrollo se publican solo en loopback.

## Dependencias y cadena de suministro

- Python soportado: 3.14.6 o revisión de seguridad posterior de la serie 3.14.
- Los locks por servicio incluyen hashes y las imágenes usan `pip --require-hashes`.
- `scripts/check-quality.ps1` ejecuta Ruff, Bandit, `pip-audit`, pruebas, detección básica de secretos y genera un SBOM CycloneDX reproducible.
- `python-jose/ecdsa` y `PyPDF2` fueron retirados al detectarse vulnerabilidades; JWT usa PyJWT y PDF usa `pypdf`.
- La clave OpenAI local detectada durante la auditoría fue eliminada y debe rotarse antes de configurar un valor nuevo.

