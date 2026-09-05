<!-- NG-HEADER: Nombre de archivo: 2026-08-27-siyuan-documentacion-design.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/specs/2026-08-27-siyuan-documentacion-design.md -->
<!-- NG-HEADER: Descripción: Diseño aprobado de integración documental entre Growen y SiYuan. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Diseño de SiYuan MCP y documentación centralizada

## Objetivo

Git conserva la autoridad sobre `/Growen` y SiYuan funciona como portal offline-first. `/Negocio` y `/Operación` alojan documentación privada no versionada. Los agentes autorizados pueden listar, buscar, leer, crear y actualizar sin exponer SQL libre, secretos ni operaciones de borrado, movimiento o renombrado.

## Arquitectura

Codex usa STDIO para evitar CORS y credenciales MCP expirables. El mismo paquete expone Streamable HTTP en `127.0.0.1:8104/mcp`, protegido con el JWT común de Growen. Ambos transportes consumen SiYuan mediante `http://localhost:6806` y `Authorization: Token <token>`.

SiYuan v3.8.1 se ejecuta mediante un perfil Compose opcional y guarda su workspace fuera del repositorio. STDIO local y `admin` acceden a `/Growen`, `/Negocio` y `/Operación`; `colaborador` sólo consulta `/Growen`. Las mutaciones MCP se limitan a las raíces privadas y la sincronización interna Git → SiYuan es el único escritor de `/Growen`.

## Contratos

- `list_siyuan_notebooks()` lista notebooks sin contenido.
- `search_siyuan_docs(query, limit=20)` ejecuta SQL fijo en modo `readonly`, incorpora las raíces autorizadas antes de consultar y devuelve documentos deduplicados.
- `read_siyuan_document(document_id)` valida notebook y ruta antes y después de exportar Markdown y devuelve `revision_sha256`.
- `create_siyuan_document(path, markdown)` valida ruta y tamaño, comprueba colisiones y crea sólo bajo `/Negocio` o `/Operación`.
- `update_siyuan_document(document_id, markdown, expected_revision_sha256)` crea historial, revalida ruta y revisión justo antes de escribir y reemplaza Markdown sólo si la revisión coincide.
- `create_siyuan_task_database(document_id)` crea o reconcilia una estructura fija de tareas en un documento privado; el modelo no controla DOM, SQL, vistas ni campos.

Las lecturas reintentan una vez únicamente ante fallos transitorios. Las escrituras no se reintentan. Los errores públicos distinguen autenticación, rate limit, timeout, red, respuesta inválida, conflicto, autoridad Git, acceso prohibido y resultado incierto sin incluir secretos o cuerpos completos.

## Documentación

`Roadmap.md` queda reservado para futuro y pendientes. `docs/README.md` clasifica gobernanza, referencia, operación, historia y archivo. El publicador mantiene fuera del repositorio un estado con hashes, bloquea ejecuciones concurrentes, guarda checkpoints atómicos, detecta divergencias, exige `--force-conflicts` para que Git prevalezca y reporta huérfanos sin eliminarlos. Manifiesto y estado nunca contienen Markdown.

## Seguridad y operación

Los secretos residen en `../growen-secrets`. STDIO no escribe logs en stdout y se considera un canal administrativo exclusivamente local. HTTP valida JWT, issuer, audience, expiración, rol y rate limit. SiYuan sólo publica `6806` sobre loopback y el MCP HTTP sólo publica `8104` sobre loopback. La auditoría registra actor e ID hasheados, raíz y revisiones, nunca contenido ni rutas privadas completas.

`updateBlock` no ofrece compare-and-swap. La revalidación inmediatamente anterior y el historial mitigan la carrera, pero una coedición directa desde la UI en el instante final puede competir con el agente; la operación exige relectura ante incertidumbre y coordinación para no editar simultáneamente el mismo documento.
