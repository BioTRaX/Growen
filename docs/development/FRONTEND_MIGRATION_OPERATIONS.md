<!-- NG-HEADER: Nombre de archivo: FRONTEND_MIGRATION_OPERATIONS.md -->
<!-- NG-HEADER: Ubicación: docs/development/FRONTEND_MIGRATION_OPERATIONS.md -->
<!-- NG-HEADER: Descripción: Operación y gobernanza del frontend unificado en Vue 3 y Vuetify 3 bajo Nginx. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Operación del frontend unificado Vue 3

## 1. Contexto

La migración a Vue 3 y Vuetify 3 se encuentra formalmente concluida. El código de React 19 legado (`frontend/`, ~23.400 líneas) fue desmantelado y retirado en su totalidad el 15 de septiembre de 2026.
El contenedor `frontend` compila de forma exclusiva la SPA de Vue 3 (`frontend-vue`) mediante un builder único (`infra/Dockerfile.frontend`). Nginx atiende el 100% de las rutas operativas y administrativas bajo `/vue/index.html` y publica los bundles bajo `/vue-assets/`. FastAPI queda detrás de `/api/` y los archivos multimedia detrás de `/media/`, todos unificados bajo el mismo origen.
`/health` se proxifica al healthcheck de FastAPI y también alimenta el `HEALTHCHECK` del contenedor frontend.

## 2. Observaciones

La fuente de verdad continúa siendo `frontend-vue/config/modules.json`. De ella se generan Vue Router, el sidebar y `frontend-vue/generated/nginx-spa-routes.conf`. Un módulo declara identidad, grupo, rutas, aliases, roles, capacidades, estado y runtime.

Reglas invariantes:

- Todos los módulos de negocio y administración operan en `state: "active"` y `runtime: "vue"`.
- Los aliases `/admin/imagenes` y `/admin/imagenes-productos` redirigen a `/imagenes-productos`.
- Las rutas no mapeadas bajo `/admin/*` y páginas inexistentes son canalizadas a `NotFoundView.vue` (404) dentro del shell.
- Las guardas frontend mejoran UX; FastAPI continúa siendo la autoridad final de permisos.

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
El quality gate y las auditorías de dependencias operan exclusivamente sobre `frontend-vue`.

Antes de un smoke manual, verificar que no se esté reutilizando un proceso anterior a la configuración que se prueba:

```powershell
Get-NetTCPConnection -LocalPort 5176 -State Listen | Select-Object OwningProcess
Get-Process -Id <PID> | Select-Object Id, StartTime, Path
Invoke-WebRequest http://127.0.0.1:5176/api/health -UseBasicParsing
```

La última respuesta debe ser JSON de FastAPI. Para reiniciar el entorno completo usar `scripts/stop-dev.ps1` y luego `scripts/start-dev.ps1`; no finalizar procesos ajenos sin identificar primero el PID propietario del puerto.

### Incorporación de nuevas rutas o módulos

1. Declarar el nuevo módulo en `frontend-vue/config/modules.json` con `state: "active"` y `runtime: "vue"`.
2. Asignar el componente en `frontend-vue/src/app/router/index.ts` bajo la carpeta modular respectiva (`src/modules/<dominio>/views/`).
3. Ejecutar `npm run generate:nginx` para actualizar las directivas de Nginx.
4. Validar tipos con `npm run typecheck`, suite unitaria con `npm test` y build con `npm run build`.
5. Reconstruir y desplegar la imagen `frontend`.

### Rollback y contingencias

Al haberse retirado la imagen dual y el código fuente de React, cualquier rollback de emergencia sobre la capa de presentación opera a nivel de infraestructura y versionado:
1. Desplegar el tag previo de la imagen Docker de `frontend` o revertir el commit respectivo en Git.
2. No se requieren cambios en base de datos ni migraciones reversivas a menos que el cambio involucre esquema.

### Retiro consumado de React (2026-09-15)

El 15 de septiembre de 2026 se ejecutó el retiro definitivo de React 19 tras completarse la paridad de Proveedores y con la dispensa expresa de la ventana de estabilidad de 7 días autorizada por el usuario. Se eliminó la carpeta `frontend/`, se unificó el Dockerfile a un builder único y se sanearon las rutas de fallback.

## 6. Criterios de aceptación

- Router, sidebar y Nginx derivan del mismo manifiesto.
- Los assets React y Vue no colisionan.
- HTTP, blobs, WebSocket y SSE usan transportes compartidos.
- Cada dominio puede activarse y revertirse sin cambios backend ni datos.
- El quality gate valida tipos, unitarias, E2E, build y auditoría.
- Todo cambio de estado se documenta y actualiza README, Roadmap y troubleshooting si quedan desactualizados.
