<!-- NG-HEADER: Nombre de archivo: 2026-08-27-siyuan-documentacion.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/plans/2026-08-27-siyuan-documentacion.md -->
<!-- NG-HEADER: Descripción: Plan ejecutable para integrar SiYuan y sanear la documentación de Growen. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# SiYuan MCP y saneamiento documental - Plan de implementación

> **Para agentes:** ejecutar en línea con `superpowers:executing-plans`; no usar subagentes sin pedido explícito. Seguir TDD y la venv de Growen.

**Objetivo:** integrar SiYuan v3.8.1 con Codex y consolidar la documentación vigente.

**Arquitectura:** cliente HTTP tipado compartido por MCP STDIO y HTTP; SiYuan y el MCP HTTP se ofrecen como perfil Docker opcional. Git continúa como fuente de verdad para `/Growen`; las raíces privadas son canónicas en SiYuan y admiten edición con hash e historial.

**Stack:** Python 3.14.6, FastMCP, FastAPI, httpx, pytest, PowerShell y Docker Compose.

**Especificación:** `docs/superpowers/specs/2026-08-27-siyuan-documentacion-design.md`.

## Restricciones globales

- No registrar ni versionar secretos.
- Usar exclusivamente `.venv\Scripts\python.exe` o Docker para Python.
- No ejecutar commit o push sin autorización explícita.
- Preservar cambios preexistentes del worktree.

## Tareas

- [x] Implementar cliente y tools con ciclos RED/GREEN.
- [x] Implementar transportes STDIO y HTTP, autorización y contratos MCP.
- [ ] Agregar Compose, Dockerfile, bootstrap, smoke y sincronización Git → SiYuan. Código listo; el smoke mutante sigue pendiente sobre un workspace desechable.
- [ ] Configurar Codex y los launchers locales.
- [ ] Consolidar, clasificar y corregir la documentación relevada.
- [ ] Ejecutar auditoría, tests, Compose config y smoke real.

## Extensión aprobada: edición segura

- [x] Separar `/Growen`, `/Negocio` y `/Operación` por autoridad y rol.
- [x] Restringir búsqueda y lectura antes de exportar contenido.
- [x] Incorporar revisión SHA-256, historial y actualización privada sin reintentos.
- [x] Extender el publicador a creación, actualización, conflicto, forzado y huérfanos.
- [x] Bloquear publicadores concurrentes y persistir checkpoints atómicos por operación confirmada.
- [x] Añadir una tool MCP acotada para bases privadas de tareas y validarla sobre `/Operación` mediante STDIO y Chrome.
- [x] Agregar auditoría anonimizada y smoke de actualización/conflicto.
- [ ] Ejecutar el smoke real sobre un workspace desechable y completar la ventana de estabilidad local.

## Checkpoint 2026-08-27

- Evidencia focal: 24 pruebas del paquete MCP, 4 del publicador, 1 del smoke y 1 del contrato `start.bat` pasaron en sus últimas ejecuciones.
- `docker compose --profile siyuan config --quiet` terminó correctamente.
- `scripts/start-dev.ps1 -CheckOnly` terminó correctamente sin habilitar SiYuan.
- El primer bootstrap real falló antes de iniciar contenedores porque Windows PowerShell 5.1 no admite `Set-Content -Encoding utf8NoBOM`.
- No quedaron contenedores SiYuan activos ni archivos secretos SiYuan creados.
- Próximo ciclo obligatorio: aplicar `superpowers:systematic-debugging`, agregar una prueba de compatibilidad para PowerShell 5.1, reemplazar la escritura UTF-8 sin BOM por una implementación compatible y volver a ejecutar `scripts/setup-siyuan.ps1 -StartHttpMcp`.
- Después: configurar `C:\Users\alete\.codex\config.toml`, publicar documentación, ejecutar el smoke real y completar el saneamiento documental.

## Checkpoint 2026-08-28

- La extensión de edición segura y sincronización Git → SiYuan quedó implementada en la rama `dev`.
- La batería focal actual reúne 68 pruebas: cliente, autorización MCP, aislamiento de raíces, concurrencia optimista, bases de tareas, auditoría, publicador y smoke simulado.
- El publicador bloquea ejecuciones concurrentes y guarda checkpoints atómicos después de cada operación confirmada.
- La revisión técnica motivó revalidación de ruta después de leer y justo antes de escribir, detección de escrituras sin efecto y clasificación conservadora de resultados inciertos.
- Sigue pendiente únicamente el smoke mutante sobre un workspace SiYuan desechable; no debe ejecutarse contra el notebook real porque esta versión no elimina documentos de prueba.
