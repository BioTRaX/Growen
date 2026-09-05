<!-- NG-HEADER: Nombre de archivo: SECURITY.md -->
<!-- NG-HEADER: Ubicación: docs/SECURITY.md -->
<!-- NG-HEADER: Descripción: Política de seguridad del proyecto -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Seguridad

## Mercado Libre y Cloudflare Tunnel

`MELI_APP_ID`, `MELI_CLIENT_SECRET`, `MELI_TOKEN_ENCRYPTION_KEY` y el token del túnel se cargan por archivos externos o secretos Swarm; producción rechaza valores directos. Access token, refresh token y PKCE se cifran con AES-256-GCM y AAD por propósito/cuenta. No se registran URLs OAuth completas, headers Authorization, payloads de recursos ni secretos. El webhook valida tamaño, tipo, aplicación, topic y path, pero se trata siempre como aviso no autenticado: el worker consulta MeLi con Bearer y verifica seller antes de actuar.

`meli_cloudflared` sólo está conectado a `meli_ingress` y `cloudflare_egress`; la última regla ingress es `http_status:404`. La configuración no permite alcanzar otros servicios Docker. Ver rotación y operación en `docs/MELI_INTEGRATION.md`.

## Secretos y rollout Chat (2026-08-16)

Producción usa exclusivamente `TELEGRAM_BOT_TOKEN_FILE`, `TELEGRAM_IDENTITY_ENCRYPTION_KEY_FILE`, `TELEGRAM_IDENTITY_HMAC_KEY_FILE`, `TELEGRAM_CANARY_USER_ID_FILE` y, si se habilita OpenAI, `OPENAI_API_KEY_FILE`. El lector rechaza valor+archivo, rutas relativas, symlinks, archivos no regulares y secretos directos fuera de desarrollo/tests. `scripts/generate_chat_keys.py --output-dir <ruta-externa>` rechaza destinos dentro del workspace y nunca imprime valores.

El token del bot se monta únicamente en `telegram_worker` y en runtimes del
dominio que lo requieran explícitamente. `dramatiq`, `market_worker`,
`enrichment_worker` y `knowledge_worker` sobrescriben los flags Telegram a `0`
y eliminan `TELEGRAM_BOT_TOKEN_FILE` de su entorno efectivo. No ampliar sus
montajes de secretos como solución a errores de configuración.

El archivo OpenAI sigue el mismo principio de mínimo privilegio:
`enrichment_worker` y `knowledge_worker` lo reciben como bind mount de sólo
lectura; `dramatiq` y `market_worker` fuerzan vacíos `OPENAI_API_KEY` y
`OPENAI_API_KEY_FILE`. La ruta del host no debe aparecer en logs operativos.

El token y el canary se capturan sin eco mediante `--interactive-bot-token` y
`--interactive-canary`. No pasarlos como argumentos, no exponerlos en salidas
de consola ni consultarlos mediante bots de terceros. La opción recomendada
para el canary es `--capture-canary`:
exige un `/canary` privado y persiste `from.id` sin imprimirlo. OpenAI puede
capturarse con `--interactive-openai-key`; almacenar la clave no habilita el
proveedor mientras `AI_ALLOW_EXTERNAL=false`.
Restringir la ACL del directorio al usuario operativo.

El rollout nace `disabled/paused`. Fuga RAG/PII, mutación Telegram o violación de rol fuerza el retorno inmediato a ese estado. No existe endpoint para forzar avance; pause, resume y rollback requieren admin, sesión y CSRF.

## Identidad y autorización de Chat/Telegram (2026-07-22)

- `message.from.id` es la identidad personal; `chat.id` sólo representa destino y conversación.
- Los IDs externos se cifran con AES-GCM y se buscan con HMAC-SHA256 usando claves separadas. UI y APIs administrativas sólo muestran valores enmascarados.
- Los desconocidos son `guest`. El rol de cuenta se consulta desde `User.role` en cada mensaje y Telegram aplica techo `colaborador`; en grupos no se aplican roles vinculados.
- Admin exige reautenticación web, código privado de cinco minutos y aprobación de otro admin. La autoaprobación está prohibida.
- Telegram es sólo lectura. Tools desconocidas, canales no declarados y capacidades ausentes se deniegan por defecto.
- `AI_ALLOW_EXTERNAL=false` impide seleccionar OpenAI como fallback.
- Logs y trazas no deben contener IDs, tokens, códigos, URLs de DB, prompts, respuestas ni argumentos/results de tools.
- Las sesiones se archivan a los 90 días; no existe borrado automático. La eliminación o anonimización es manual y auditable.

La rotación de cifrado admite temporalmente `TELEGRAM_IDENTITY_ENCRYPTION_KEY_PREVIOUS`; la clave HMAC no debe rotarse sin una migración de reindexación. Las migraciones ya están aplicadas localmente, pero las banderas Telegram siguen apagadas hasta configurar claves efímeras, clasificar RAG y completar el smoke.

Auditoría histórica 2026-08-15: sólo PostgreSQL estaba activo; no había worker
Telegram, identidades, updates ni trazas Chat. Desde el rollout local posterior,
los flags pueden declararse en `.env`, pero cada servicio debe reducirlos según
su dominio. Polling es el único transporte admitido; la API no monta el router
webhook y la presencia de un secreto no habilita por sí sola un proveedor.

## Manejo de secretos
- Nunca versionar archivos `.env` ni credenciales.
- Utilizar gestores de secretos cuando sea posible.

## Incidente Telegram confirmado (2026-07-30)

- GitHub Secret Scanning confirmó como `Public leak` el token operativo de
  Telegram publicado en `workers/telegram_polling.py:56` por el commit
  `b4bf96907f05cc772f265400f7d8d60ba3dcf3ac`.
- El literal fue retirado en
  `590ef3b8598b6434d7a8474d9a5b02f721cb1bdf`. El 2026-07-30 se reescribieron y
  publicaron `main` (`1e117589d8547e07d12d30c94ddc0513a6452695`) y `dev`
  (`5eaf36a42771c0a3ed7104b60a08a9f488fd75af`), y se eliminaron las cuatro
  ramas Dependabot afectadas. El token fue revocado y no debe reutilizarse.
- Diez referencias internas `refs/pull/*` de GitHub todavía alcanzan el objeto
  histórico. No pueden modificarse mediante `git push`; su purga debe
  solicitarse a GitHub Support antes de declarar completa la erradicación.
- Un comentario, fixture o ejemplo jamás puede usar una credencial real ni una
  cadena que cumpla el formato válido del proveedor.
- No copiar tokens dentro de URLs de navegador, logs, tickets, capturas o
  comandos persistidos en el historial de la terminal.
- Todo secreto detectado en Git se considera comprometido: primero se revoca,
  luego se preserva evidencia redactada y finalmente se sanea el historial en
  una ventana coordinada.
- Informe, alcance y plan de erradicación:
  `docs/SECURITY_INCIDENT_TELEGRAM_20260730.md`.

La clave OpenAI local detectada durante la auditoría fue rotada. El entorno no
conserva API keys y debe permanecer así hasta el rollout controlado mediante el
gestor de secretos; nunca documentar ni registrar el valor nuevo.

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

## Documentación privada en SiYuan

- `/Growen` es una réplica gobernada por Git. Las tools MCP de creación y actualización rechazan esa raíz; sólo el publicador local puede sincronizarla.
- `/Negocio` y `/Operación` son privadas y canónicas en SiYuan. Sólo `admin` y agentes STDIO ejecutados localmente pueden leerlas o mutarlas.
- `colaborador` consulta únicamente `/Growen`. La raíz permitida forma parte del SQL fijo y los IDs se autorizan antes de exportar Markdown, evitando filtraciones por snippets o acceso directo.
- Toda actualización privada exige el SHA-256 devuelto por la lectura anterior, crea historial, revalida ruta y revisión inmediatamente antes de escribir y no se reintenta. Los conflictos se rechazan y un resultado incierto o sin efecto observable obliga a releer.
- La creación de bases de tareas está fijada por contrato: el modelo sólo aporta el ID documental; no controla SQL, IDs de vistas, tipos de columnas ni DOM. La tool vuelve a autorizar la raíz privada y crea historial antes de mutar.
- La auditoría de escritura conserva actor e ID hasheados, raíz, resultado y hashes de revisión. Nunca registra Markdown, ruta privada completa, token ni parámetros sensibles.
- El estado del publicador se almacena fuera del repositorio y no contiene contenido documental. El publicador usa bloqueo exclusivo y checkpoints atómicos para evitar pérdida de baseline entre procesos. `--force-conflicts` requiere `--apply` y constituye la confirmación explícita para que Git prevalezca.
- La API `updateBlock` de SiYuan no ofrece compare-and-swap. La doble revalidación y el historial reducen el riesgo, pero no eliminan una edición simultánea desde la UI en el último instante; debe evitarse la coedición del mismo documento y releerse ante incertidumbre.
- STDIO se considera un canal local administrativo y no debe exponerse por red; HTTP continúa exigiendo JWT, audience, issuer, expiración, rol, JTI y rate limit.

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
- Los secretos detectados durante la auditoría fueron rotados. El entorno permanece sin API keys y cualquier futura credencial debe inyectarse desde el gestor de secretos, sin aparecer en documentación, logs ni evidencia de cierre.

