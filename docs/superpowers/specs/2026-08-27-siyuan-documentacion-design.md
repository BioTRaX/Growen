<!-- NG-HEADER: Nombre de archivo: 2026-08-27-siyuan-documentacion-design.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/specs/2026-08-27-siyuan-documentacion-design.md -->
<!-- NG-HEADER: Descripción: Diseño aprobado de integración documental entre Growen y SiYuan. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Diseño de SiYuan MCP y documentación centralizada

## Objetivo

Git conserva la autoridad sobre contratos técnicos y SiYuan funciona como portal offline-first. El agente puede listar, buscar, leer y crear documentación sin exponer SQL libre, secretos ni operaciones destructivas.

## Arquitectura

Codex usa STDIO para evitar CORS y credenciales MCP expirables. El mismo paquete expone Streamable HTTP en `127.0.0.1:8104/mcp`, protegido con el JWT común de Growen. Ambos transportes consumen SiYuan mediante `http://localhost:6806` y `Authorization: Token <token>`.

SiYuan v3.8.1 se ejecuta mediante un perfil Compose opcional, guarda su workspace fuera del repositorio y limita escrituras al notebook `Nice Grow` y al prefijo `/Growen`.

## Contratos

- `list_siyuan_notebooks()` lista notebooks sin contenido.
- `search_siyuan_docs(query, limit=20)` ejecuta SQL fijo en modo `readonly` y devuelve documentos deduplicados.
- `read_siyuan_document(document_id)` exporta Markdown por ID.
- `create_siyuan_document(path, markdown)` valida ruta y tamaño, comprueba colisiones y nunca sobrescribe.

Las lecturas reintentan una vez únicamente ante fallos transitorios. Las escrituras no se reintentan. Los errores públicos distinguen autenticación, rate limit, timeout, red, respuesta inválida y documento existente sin incluir secretos o cuerpos completos.

## Documentación

`Roadmap.md` queda reservado para futuro y pendientes. `docs/README.md` clasifica gobernanza, referencia, operación, historia y archivo. La publicación inicial en SiYuan es create-only y produce un manifiesto sin contenido documental.

## Seguridad y operación

Los secretos residen en `../growen-secrets`. STDIO no escribe logs en stdout. HTTP valida JWT, issuer, audience, expiración, rol y rate limit. SiYuan sólo publica `6806` sobre loopback y el MCP HTTP sólo publica `8104` sobre loopback.

