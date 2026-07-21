<!-- NG-HEADER: Nombre de archivo: FRONTEND_MIGRATION_OPERATIONS.md -->
<!-- NG-HEADER: Ubicación: docs/FRONTEND_MIGRATION_OPERATIONS.md -->
<!-- NG-HEADER: Descripción: Operación, activación y rollback de la convivencia React/Vue bajo Nginx. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Operación de la migración React/Vue

## 1. Contexto

El contenedor `frontend` compila ambas SPAs y Nginx decide el runtime por ruta. React conserva `/assets/`; Vue publica bundles bajo `/vue-assets/`. FastAPI queda detrás de `/api/` y los medios detrás de `/media/`, todos bajo el mismo origen.
`/health` se proxifica al healthcheck de FastAPI y también alimenta el `HEALTHCHECK` del contenedor frontend.

## 2. Observaciones

La fuente de verdad es `frontend-vue/config/modules.json`. De ella se generan Vue Router, el sidebar y `frontend-vue/generated/nginx-spa-routes.conf`. Un módulo declara identidad, grupo, rutas, aliases, roles, capacidades, estado y runtime.

Reglas invariantes:

- `runtime: "vue"` solo es válido con `state: "active"`.
- Una ruta pública mantiene el mismo path al cambiar de runtime.
- Navegar desde Vue hacia una ruta legacy fuerza carga completa; Nginx selecciona React.
- Los aliases `/admin/imagenes` y `/admin/imagenes-productos` redirigen a `/imagenes-productos`.
- Las guardas frontend mejoran UX; FastAPI continúa siendo la autoridad.

Variables públicas Vue:

```env
VITE_API_BASE_URL=/api
VITE_API_TARGET=http://127.0.0.1:8000
VITE_RELEASE=local
VITE_REQUEST_TIMEOUT_MS=30000
```

`VITE_API_URL` se acepta solo como alias temporal. En producción debe usarse una base relativa. `NGINX_CLIENT_MAX_BODY_SIZE` vale `25m` por defecto.

## 3. Errores y/u outputs

- Si el generador informa que un módulo Vue no está activo, corregir el manifiesto; no editar el archivo Nginx generado.
- Un refresh que entrega la SPA incorrecta indica que el manifiesto no fue regenerado o que la imagen no se reconstruyó.
- Un 404 bajo `/api/` suele indicar una ruta backend incorrecta: Nginx elimina `/api` antes de proxificar.
- Un WebSocket sin upgrade requiere revisar los headers `Upgrade` y `Connection` del proxy.
- SSE debe conservar `proxy_buffering off` y timeout extendido.
- No agregar el puerto 5176 a CORS para desarrollo normal: Vite proxifica `/api` y `/media` bajo el mismo origen.
- Si `/api/health` en 5176 devuelve HTML, una respuesta distinta de JSON o un error de conexión mientras `/health` funciona directo en 8000, comprobar el PID y la hora de inicio de Vite. Reiniciar Vite después de cambiar `vite.config.ts`, variables `VITE_*` o scripts de arranque.

## 4. Objetivo

Permitir activación y rollback por dominio con un cambio declarativo, sin modificar FastAPI, contratos públicos ni datos.

## 5. Propuesta de código o pasos

### Desarrollo y validación

```powershell
cd frontend-vue
npm ci
npm run generate:nginx
npm run typecheck
npm test
npm run test:e2e
npm run build
npm audit --audit-level=high
```

El E2E inicia una instancia aislada de Vite en el puerto 5186. Playwright Chromium debe instalarse una vez con `npm exec playwright install chromium`.
Mientras React sea el fallback, el quality gate también compila y audita `frontend/`; ambas auditorías deben quedar sin vulnerabilidades altas.

Antes de un smoke manual, verificar que no se esté reutilizando un proceso anterior a la configuración que se prueba:

```powershell
Get-NetTCPConnection -LocalPort 5176 -State Listen | Select-Object OwningProcess
Get-Process -Id <PID> | Select-Object Id, StartTime, Path
Invoke-WebRequest http://127.0.0.1:5176/api/health -UseBasicParsing
```

La última respuesta debe ser JSON de FastAPI. Para reiniciar el entorno completo usar `scripts/stop-dev.ps1` y luego `scripts/start-dev.ps1`; no finalizar procesos ajenos sin identificar primero el PID propietario del puerto.

### Activar un dominio

1. Confirmar paridad por rol, capacidad y acción, pruebas aprobadas y smoke productivo.
2. Cambiar el módulo a `state: "active"` y `runtime: "vue"` en el manifiesto.
3. Ejecutar el generador y el quality gate.
4. Reconstruir y desplegar la imagen `frontend`.
5. Validar `/health`, `/auth/me`, una lectura, una mutación CSRF, refresh directo y navegación Vue/React.

### Rollback

1. Cambiar el runtime del módulo a `legacy` y su estado a `ready` o `partial`.
2. Regenerar reglas, reconstruir y desplegar frontend.
3. Repetir smoke de sesión y dominio. No se revierten base de datos ni backend.

### Retiro de React

React se elimina solo después de dos releases exitosos y siete días sin incidentes críticos atribuibles a Vue. El cambio final debe retirar el builder React, el fallback Nginx y la dependencia productiva de `frontend/dist` en una entrega separada.

## 6. Criterios de aceptación

- Router, sidebar y Nginx derivan del mismo manifiesto.
- Los assets React y Vue no colisionan.
- HTTP, blobs, WebSocket y SSE usan transportes compartidos.
- Cada dominio puede activarse y revertirse sin cambios backend ni datos.
- El quality gate valida tipos, unitarias, E2E, build y auditoría.
- Todo cambio de estado se documenta y actualiza README, Roadmap y troubleshooting si quedan desactualizados.
