<!-- NG-HEADER: Nombre de archivo: 2026-08-27-siyuan-documentacion.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/plans/2026-08-27-siyuan-documentacion.md -->
<!-- NG-HEADER: Descripción: Plan ejecutable para integrar SiYuan y sanear la documentación de Growen. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# SiYuan MCP y saneamiento documental - Plan de implementación

> **Para agentes:** ejecutar en línea con `superpowers:executing-plans`; no usar subagentes sin pedido explícito. Seguir TDD y la venv de Growen.

**Objetivo:** integrar SiYuan v3.8.1 con Codex y consolidar la documentación vigente.

**Arquitectura:** cliente HTTP tipado compartido por MCP STDIO y HTTP; SiYuan y el MCP HTTP se ofrecen como perfil Docker opcional. Git continúa como fuente de verdad y la publicación inicial es create-only.

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
- [ ] Agregar Compose, Dockerfile, bootstrap, smoke y publicación create-only. Código listo; bootstrap real bloqueado por compatibilidad PowerShell 5.1.
- [ ] Configurar Codex y los launchers locales.
- [ ] Consolidar, clasificar y corregir la documentación relevada.
- [ ] Ejecutar auditoría, tests, Compose config y smoke real.

## Checkpoint 2026-08-27

- Evidencia focal: 24 pruebas del paquete MCP, 4 del publicador, 1 del smoke y 1 del contrato `start.bat` pasaron en sus últimas ejecuciones.
- `docker compose --profile siyuan config --quiet` terminó correctamente.
- `scripts/start-dev.ps1 -CheckOnly` terminó correctamente sin habilitar SiYuan.
- El primer bootstrap real falló antes de iniciar contenedores porque Windows PowerShell 5.1 no admite `Set-Content -Encoding utf8NoBOM`.
- No quedaron contenedores SiYuan activos ni archivos secretos SiYuan creados.
- Próximo ciclo obligatorio: aplicar `superpowers:systematic-debugging`, agregar una prueba de compatibilidad para PowerShell 5.1, reemplazar la escritura UTF-8 sin BOM por una implementación compatible y volver a ejecutar `scripts/setup-siyuan.ps1 -StartHttpMcp`.
- Después: configurar `C:\Users\alete\.codex\config.toml`, publicar documentación, ejecutar el smoke real y completar el saneamiento documental.
