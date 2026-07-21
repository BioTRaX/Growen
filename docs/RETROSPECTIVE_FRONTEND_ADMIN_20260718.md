<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_FRONTEND_ADMIN_20260718.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_FRONTEND_ADMIN_20260718.md -->
<!-- NG-HEADER: Descripción: Retrospectiva técnica y handoff de la migración Vue y del panel administrativo. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva técnica — Migración Vue y panel administrativo

Fecha de corte: 2026-07-18.

## 1. Contexto

La sesión relevó el portal administrativo React, definió la configuración de convivencia React/Vue y completó un primer corte administrativo en Vue 3. Este documento conserva el estado comprobado para continuar el trabajo en un nuevo chat sin inferir resultados a partir de mensajes anteriores.

La fuente de verdad del runtime es `frontend-vue/config/modules.json`. Al cierre están activos en Vue `customers`, `sales`, `admin-users`, `admin-backups` y `admin-services`. El wildcard `admin` continúa en React y cubre los plugins administrativos todavía no migrados.

## 2. Observaciones

### Tareas implementadas y verificadas

- Relevamiento funcional, de rutas, acciones, roles y endpoints en `docs/relevamiento_admin.md`.
- Manifiesto modular único para router, sidebar y reglas Nginx, con estados y runtime por dominio.
- Cliente HTTP común con base `/api`, cookies, CSRF, normalización de errores, correlation ID y transportes para blobs, WebSocket y SSE.
- Proxy Vite único para `/api` y `/media`, y build dual React/Vue con assets separados.
- Nginx generado con fallback React y rutas Vue exactas para Clientes, Ventas y los módulos administrativos activos.
- Servicios administrativos Vue: resumen, Workers, health, start/stop, panic stop, auto-start, dependencias, logs, SSE y MCP.
- Usuarios Vue: listado, filtros, alta, edición, asociación de proveedor, reset de contraseña y eliminación con confirmación.
- Backups Vue: listado, ejecución y descarga autenticada como blob.
- Roles y capacidades aplicados como UX: Usuarios, Backups y MCP sólo para `admin`; Servicios y Workers para `colaborador` y `admin`; instalación de dependencias sólo con capacidad administrativa.
- Documentación actualizada en README, Roadmap, guía de migración, operación, roles y relevamiento.

### Estado comprobado del quality gate

- `npm.cmd test`: 19 archivos y 54 pruebas aprobadas.
- `npm.cmd run typecheck`: aprobado.
- `npm.cmd run test:e2e`: 5 pruebas Playwright aprobadas en Chromium.
- `npm.cmd run build`: aprobado; 522 módulos transformados.
- `npm.cmd audit --audit-level=high`: 0 vulnerabilidades.
- Las reglas generadas contienen `/admin/usuarios`, `/admin/backups`, `/admin/servicios`, `/admin/servicios/workers` y `/admin/servicios/mcp-tools` como rutas Vue exactas.

### Alcance pendiente

- Drive Sync.
- Diagnóstico de catálogos.
- Scheduler.
- Conocimiento.
- Chat Inbox.
- Dashboard técnico e imágenes administrativas.

Estas rutas no deben activarse en Vue hasta implementar paridad por rol, acción y transporte. El fallback React actual es deliberado.

## 3. Errores y/u outputs

### HTTP 500 informado durante la prueba de las 21:23/21:24

Se informó `Failed to load resource: the server responded with a status of 500`, pero no quedó registrado el método, URL, response body, correlation ID, rol, release ni stack trace. Tampoco se encontró una entrada coincidente en los logs disponibles. Por lo tanto, no existe evidencia suficiente para asignar una causa raíz o afirmar que ese 500 fue corregido.

Acción para una recurrencia: capturar la request exacta desde Network, `X-Correlation-ID`, cuerpo de respuesta y logs de API del mismo instante. Luego reproducir primero contra `http://127.0.0.1:8000/<ruta>` y después mediante `http://127.0.0.1:5176/api/<ruta>` para separar backend de proxy.

### Proceso Vite desactualizado

Durante la sesión se comprobó que un proceso Vite iniciado antes de los cambios de configuración seguía atendiendo 5176. La consulta `/api/health` devolvía HTML en lugar de JSON, evidencia de que el proceso no estaba usando el proxy esperado. Los cambios de `vite.config.ts`, variables de entorno y scripts de arranque requieren reiniciar Vite; HMR no es un mecanismo de validación suficiente para configuración de infraestructura.

Solución operativa indicada: identificar el PID propietario de 5176, detener únicamente ese proceso y reiniciar con `scripts/start-dev.ps1 -McpMode All`. Al cierre de esta retrospectiva no hay listeners en 8000, 5176 ni 5186; el próximo chat debe iniciar el stack antes de un smoke manual.

### Auditoría npm sin acceso al registry

La primera ejecución de `npm audit` falló al consultar `registry.npmjs.org`; typecheck, E2E y build sí habían finalizado correctamente. Se repitió sólo la auditoría con acceso de red autorizado y finalizó con 0 vulnerabilidades. No fue un defecto del código ni requirió cambios de dependencias.

### Documentación desactualizada

`docs/FRONTEND_MIGRATION_VUE.md` conservaba el baseline anterior de 43 unitarias y 2 E2E. Se actualizó a 54 unitarias en 19 archivos y 5 E2E. Este hallazgo confirma que las cifras de pruebas deben actualizarse en el mismo cambio que amplía el quality gate.

### Outputs de diagnóstico demasiado amplios

Una lectura conjunta de documentos extensos fue truncada por volumen. La comprobación se completó acotando búsquedas por archivo, ruta y patrón. Para próximas auditorías conviene consultar primero el manifiesto y luego los archivos del dominio activo, evitando volcados globales.

## 4. Objetivo

Mantener una migración reversible y verificable, donde el manifiesto determine el runtime, FastAPI siga siendo autoridad de permisos y cada activación administrativa tenga evidencia de paridad, pruebas y smoke. El siguiente chat debe continuar con los módulos pendientes, sin reimplementar la fundación ni asumir que el HTTP 500 informado ya tiene causa raíz.

## 5. Propuesta de código o pasos

### Handoff para el siguiente chat

1. Iniciar el entorno con `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -McpMode All`.
2. Confirmar JSON y HTTP 200 en `/health`, `/auth/me` y `/api/health` desde 5176 antes de abrir una vista.
3. Elegir un único plugin pendiente y contrastar React, router backend, `docs/relevamiento_admin.md` y `docs/roles-endpoints.md`.
4. Implementar servicio tipado, vista, pruebas unitarias y E2E por rol.
5. Mantener el módulo en `legacy` hasta completar paridad; activarlo mediante el manifiesto, regenerar Nginx y ejecutar el quality gate.
6. Actualizar README, Roadmap y documentos de migración en el mismo corte.

Orden sugerido: Scheduler y Diagnóstico de catálogos; luego Conocimiento; después Chat Inbox y Drive Sync. El orden se basa en complejidad de transporte y permisos: Drive Sync incorpora WebSocket y requiere mayor validación operativa.

### Mejoras de arquitectura agéntica basadas en esta sesión

- **Nueva skill propuesta: `frontend-migration-qa`.** Debe exigir lectura del manifiesto, matriz ruta/runtime/rol/capacidad, comprobación del contenido de `/api/health`, detección de procesos Vite anteriores a la configuración, regeneración Nginx, quality gate y actualización documental. Habría detectado antes el servidor 5176 desactualizado y las cifras de pruebas obsoletas.
- **Extensión de `scripts/status_stack.ps1`.** Mostrar PID y hora de inicio de API/Vite, target efectivo del proxy, release frontend y validación de que `/api/health` responde JSON. Esto convierte el problema observado en un chequeo automatizable sin crear otro servicio.
- **Prompt mínimo para incidentes frontend.** Solicitar URL, método, hora con zona, status, response body, correlation ID, rol, `VITE_RELEASE` y pasos de reproducción. Ese contexto habría permitido investigar el 500; sin él sólo fue posible registrar el incidente.
- **Nuevo agente separado: no recomendado para este incidente.** El diagnóstico dependía de un único estado local de puertos, procesos y logs. Delegarlo habría aumentado el riesgo de observar procesos distintos. La división por agentes sí puede ser útil para relevamientos de dominios independientes, pero no para una reproducción stateful.

No se creó la skill en esta sesión: primero se documenta el patrón y se recomienda implementarla si vuelve a repetirse durante los próximos cortes administrativos.

## 6. Criterios de aceptación

- Las tareas implementadas están enumeradas y contrastadas con archivos y pruebas actuales.
- El HTTP 500 se registra como incidente sin causa raíz, sin inventar una corrección.
- El proceso Vite desactualizado, el fallo de red de `npm audit` y la documentación obsoleta tienen solución o acción precisa.
- El próximo chat dispone de estado de runtime, pendientes, orden sugerido y procedimiento de arranque.
- Las propuestas de skill, script y prompt derivan exclusivamente de obstáculos observados en esta sesión.
- Se documentaron los cambios y se actualizaron README, Roadmap y guías relacionadas cuando estaban desactualizadas.
- No se incluyeron secretos, cookies ni credenciales.
