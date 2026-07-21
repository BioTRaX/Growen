<!-- NG-HEADER: Nombre de archivo: ADMIN_VUE_OPERATIONS.md -->
<!-- NG-HEADER: Ubicación: docs/ADMIN_VUE_OPERATIONS.md -->
<!-- NG-HEADER: Descripción: Operación y rollback de los módulos administrativos migrados a Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Operación del panel administrativo Vue

## Contexto

Drive Sync, Scheduler, Conocimiento, Imágenes, Diagnóstico de catálogos, Dashboard técnico y Chat Inbox se registran como módulos Vue independientes. Las revisiones `20260718_admin_operations_v1` y `20260718_admin_jsonb_v2` agregan y alinean la persistencia operativa; deben aplicarse antes de activar estas rutas.

## Observaciones

- Drive Sync, Scheduler, Conocimiento y Operación de imágenes son exclusivos de `admin`.
- Revisión/procesamiento de imágenes y Chat Inbox admiten `admin` y `colaborador`.
- Dashboard técnico es de solo lectura. Las acciones de procesos permanecen en Servicios.
- PostgreSQL conserva configuraciones, ejecuciones, eventos, tareas, feedback y versiones de prompt. Redis transporta colas y eventos en vivo.
- Toda mutación usa la cookie de sesión y `X-CSRF-Token`. El WebSocket de Drive valida la sesión antes de aceptar.

## Errores y/u outputs

- `403 Forbidden`: rol sin capacidad o sesión ausente.
- `403 CSRF invalid`: falta la cookie o el encabezado CSRF correspondiente.
- `409`: existe una ejecución activa, el recurso no puede cancelarse, no se alcanzó el umbral RLHF o el prompt no superó su evaluación.
- WebSocket cerrado con `4403`: sesión ausente, vencida o sin rol `admin`.

## Objetivo

Operar cada dominio desde Vue sin depender de estados críticos en memoria y conservar un rollback de runtime que no revierta datos ni migraciones.

## Propuesta de código o pasos

1. Aplicar `alembic upgrade head` y comprobar un único head.
2. Iniciar DB, API, Redis, workers y Vue con `scripts/start-dev.ps1`.
3. Validar `/auth/me` y una mutación CSRF con el rol correspondiente.
4. Ejecutar el smoke del módulo: refresh directo, lista vacía/error, descarga y streaming cuando aplique.
5. Para rollback, cambiar solamente `runtime`/`state` en `frontend-vue/config/modules.json`, regenerar Nginx y conservar las tablas.

### Flujos relevantes

- Logs: Servicios previsualiza y elimina archivos físicos y carpetas dev antiguas; Workers elimina sólo `ServiceLog` y la acción de Imágenes elimina `ImageJobLog`, NDJSON y snapshots. Ver `docs/LOG_CLEANUP.md`.
- Drive: una cancelación se atiende entre archivos; el reintento crea una ejecución hija.
- Scheduler: la fila singleton `scheduler_settings.id=1` es la fuente de verdad; las variables de entorno sólo siembran el primer valor.
- Conocimiento: `/admin/conocimiento` reemplaza visualmente a Cerebro; `/admin/cerebro` queda como alias. Eliminar una fuente conserva el archivo y eliminar el archivo es una acción separada.
- Catálogos: los eventos se descargan desde `/catalogs/diagnostics/runs/{run_id}/download`; no existe purga automática.
- Chat: un prompt debe ser evaluado, superar al activo al menos 5 % y no tener regresión de seguridad. Sólo un admin puede aprobarlo o activarlo; una versión retirada puede reactivarse como rollback.

## Criterios de aceptación

- Reiniciar API/worker no elimina historial ni configuración.
- Los permisos coinciden en manifiesto, UI y backend.
- Typecheck, pruebas, build y generación Nginx finalizan correctamente.
- Los cambios se documentan y se actualiza cualquier instrucción desactualizada en Roadmap, README, CHANGELOG y `docs/`.
