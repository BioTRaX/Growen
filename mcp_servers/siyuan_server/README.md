<!-- NG-HEADER: Nombre de archivo: README.md -->
<!-- NG-HEADER: Ubicación: mcp_servers/siyuan_server/README.md -->
<!-- NG-HEADER: Descripción: Operación y contratos del MCP documental de SiYuan. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# MCP SiYuan

Integra el notebook `Nice Grow` mediante la API local de SiYuan. Codex usa STDIO local y los consumidores HTTP usan `http://127.0.0.1:8104/mcp` con JWT de Growen.

La autoridad documental se divide por raíz:

- `/Growen`: Git es canónico; sólo `scripts/publish_docs_to_siyuan.py` puede crear o actualizar su réplica.
- `/Negocio` y `/Operación`: SiYuan es canónico; `admin` y agentes STDIO locales pueden crear y editar.
- `colaborador`: sólo puede buscar y leer `/Growen`; las consultas no incluyen snippets privados.

## Tools

- `list_siyuan_notebooks`: lectura.
- `search_siyuan_docs`: búsqueda SQL fija y `readonly`, acotada a las raíces del actor.
- `read_siyuan_document`: exportación Markdown con `revision_sha256`.
- `create_siyuan_document`: creación sin sobrescritura en áreas privadas.
- `update_siyuan_document`: reemplazo Markdown privado con historial y concurrencia optimista.
- `create_siyuan_task_database`: añade o reconcilia una sección `Tareas` con una base table, fila inicial y campos `Fecha`, `Estado` y `Última modificación`.

La actualización exige el `revision_sha256` obtenido en la lectura anterior. La ruta y la revisión se vuelven a validar inmediatamente antes de escribir. Un hash obsoleto produce `document_conflict`; un error o una escritura sin efecto observable produce `document_write_status_unknown` y obliga a releer. No existen tools de borrado, movimiento o renombrado.

La base de tareas sólo se crea en documentos privados. La operación genera historial y puede reejecutarse para retirar la columna `Select` vacía que SiYuan 3.8.1 agrega al inicializar una base. No acepta IDs de vistas ni definiciones de columnas aportadas por el modelo.

SiYuan no ofrece CAS sobre `updateBlock`: las revalidaciones reducen la ventana de carrera, pero una edición directa desde la UI en el instante final aún puede competir con la escritura. El historial previo conserva recuperación; los operadores deben releer ante cualquier resultado incierto y evitar editar simultáneamente el mismo documento.

## Sincronización desde Git

```powershell
# Plan sin escrituras
.\.venv\Scripts\python.exe scripts\publish_docs_to_siyuan.py

# Aplica creaciones y actualizaciones sin divergencia
.\.venv\Scripts\python.exe scripts\publish_docs_to_siyuan.py --apply

# Git prevalece sobre conflictos revisados explícitamente
.\.venv\Scripts\python.exe scripts\publish_docs_to_siyuan.py --apply --force-conflicts
```

El estado vive por defecto fuera del repositorio en `../growen-siyuan/publish-state.json`. El ciclo carga–sincronización–persistencia mantiene un bloqueo exclusivo y crea checkpoints atómicos después de cada escritura confirmada. Manifiesto y estado contienen rutas, IDs, hashes y estados, nunca Markdown. Los documentos retirados de Git se reportan como `orphaned` y no se eliminan.

## Inicio

```powershell
.\scripts\setup-siyuan.ps1 -StartHttpMcp
.\scripts\start-dev.ps1 -WithSiyuanMcp
```

El token se lee desde `SIYUAN_API_TOKEN_FILE`; no debe copiarse al repositorio ni mostrarse en logs. Configurar las áreas privadas con `SIYUAN_PRIVATE_PATH_PREFIXES=/Negocio,/Operación`.
