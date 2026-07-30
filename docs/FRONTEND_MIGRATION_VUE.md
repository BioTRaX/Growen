<!-- NG-HEADER: Nombre de archivo: FRONTEND_MIGRATION_VUE.md -->
<!-- NG-HEADER: Ubicación: docs/FRONTEND_MIGRATION_VUE.md -->
<!-- NG-HEADER: Descripción: Plan, estado y operación de la migración incremental a Vue 3 y Vuetify 3. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Migración del frontend a Vue 3 y Vuetify 3

## Chat 😎 — módulo independiente (2026-07-22)

`frontend-vue/src/modules/chat/` implementa `/chat` para todos los roles con HTTP/WebSocket compartido, reconexión, fallback HTTP, streaming compatible, cancelación, cards por perfil, citas, feedback, estado de conexión y errores tipados. El borrador permanece sólo en memoria.

El manifiesto queda deliberadamente en `state: ready`, `runtime: legacy`: Vue debe pasar typecheck/build, smoke autenticado por rol y paridad funcional antes de activarse. React se conserva durante dos releases estables y siete días sin incidentes críticos. Rollback: restaurar `legacy` sin revertir datos ni migraciones.

## Mercado — runtime Vue activo (verificado 2026-07-25)

`/mercado` está en `state: active` y `runtime: vue` para `colaborador|admin`. Nginx sirve la SPA Vue. El módulo conserva backend autoritativo, CSRF, filtros URL, actualización individual y batch, fuentes, descubrimiento, observaciones manuales, revalidación, histórico SVG y polling cancelable hasta estado terminal.

React conserva compatibilidad temporal para rollback. Su retiro sigue pendiente de smoke visual autenticado y una ventana estable. El contrato vigente está en `docs/API_MARKET.md`; `docs/MERCADO_INTEGRACION_FRONTEND.md` describe únicamente la integración React histórica.

## Stock y Faltantes — runtime Vue activo (verificado 2026-07-25)

Las rutas `/stock` y `/stock/shortages` están en `state: active` y `runtime: vue`. Stock ofrece pestañas con/sin stock, filtros persistidos en URL, búsqueda con debounce/cancelación, edición decimal de stock y precios, exportaciones XLSX/CSV/PDF y TiendaNegocio sólo para staff. Faltantes incorpora métricas, filtro por motivo, búsqueda remota limitada a 50 productos, alta decimal y confirmación de saldo negativo.

El backend usa `Decimal(14,2)`, bloqueo de fila, ledger y auditoría transaccional; `expected_stock` devuelve 409 ante una lectura desactualizada. XLSX, CSV y PDF comparten la misma consulta. Las acciones de enriquecimiento, completar precios y catálogos se reubicaron en Productos Vue.

Estado de despliegue: el manifiesto y las reglas Nginx generadas dirigen ambas rutas a Vue. El rollback consiste en volver el módulo a `legacy`, regenerar Nginx y desplegar sin revertir datos ni ledger.

Validación documental del corte actual: el 2026-07-25 aprobaron 82 pruebas Vue, `vue-tsc` y build Vue. Se conserva como evidencia histórica la validación backend focal del corte original. Quedan pendientes smoke visual autenticado y prueba de concurrencia real sobre PostgreSQL; SQLite no demuestra el bloqueo pesimista. El contrato vigente está en `docs/STOCK.md`.

## Productos: taxonomía plana y tags — 2026-07-18

Vue alcanza paridad para categoría/subcategoría creables y gestión de tags: alta individual, asignación masiva aditiva, detalle editable y tags comunes/particulares del wizard. Los autocompletes se validan montando Vuetify real. El fallback React se conserva hasta completar el smoke visual por rol.

## Corte administrativo — 2026-07-18

Drive Sync, Scheduler, Conocimiento, Operación y Revisión de Imágenes, Diagnóstico de catálogos, Dashboard técnico y Chat Inbox están activos en el manifiesto Vue. Usan los transportes compartidos para Axios, blobs, SSE y WebSockets; no incorporan `fetch` directo ni URLs absolutas.

React sólo podrá retirarse luego de dos releases estables y siete días sin incidentes críticos. Ver `docs/ADMIN_VUE_OPERATIONS.md` para smoke y rollback.

## Productos: alta masiva canónica — 2026-07-17

La segunda capacidad operativa de Productos migra a Vue la creación de canónicos desde filas de proveedor. Incluye wizard de cuatro pasos, borradores recuperables por usuario, SKU provisional, envío idempotente, polling y resultados parciales. Categorías y subcategorías pueden crearse en línea al escribir un nombre inexistente; el mismo selector se reutiliza en el alta individual del catálogo. El backend conserva `POST /canonical-products/batch-job` para React, pero Vue no envía el SKU provisional: la secuencia definitiva se asigna dentro del worker.

Próximas fases, en orden: equivalencias, imágenes avanzadas, smoke de los módulos activos y retiro selectivo de sus fallbacks React.

## Corte funcional Compras/Productos — 2026-07-16

- `/compras`, `/compras/nueva` y `/compras/:id` ya no usan `MigrationPendingView`.
- Compras permite importar Santa Planta, revisar líneas, validar, confirmar y consultar impacto.
- El detalle de compra prioriza el nombre original, compacta las columnas numéricas y muestra el total neto reactivo de cada línea.
- Compras usa un selector buscable de proveedores con alta rápida para administradores; ya no solicita IDs internos.
- `/proveedores` queda activo con listado, búsqueda y creación básica.
- `/productos` ofrece un catálogo operativo con filtros, búsqueda diferida, paginación y estado persistido en la URL.
- Productos recupera alta con proveedor y categoría creable desde el buscador, edición de stock, edición de precio efectivo y borrado protegido individual o masivo para staff.
- El menú lateral agrupa Catálogo, Stock e Imágenes bajo Productos; los tres módulos tienen runtime Vue propio.
- El listado admite usuarios autenticados. `/productos/:id` ofrece detalle básico a invitados y suma historial de compras para `colaborador` y `admin`.
- Equivalencias, detalle enriquecido y preferencias de tabla continúan temporalmente en React; las operaciones masivas de enriquecimiento, precios y catálogos ya están en Productos Vue.

Última actualización: 2026-07-25.

## 1. Contexto

Growen mantiene una imagen frontend dual: React 19 continúa como fallback general y Vue 3 recibe las rutas activadas por dominio desde `frontend-vue/config/modules.json`.

La arquitectura objetivo sigue las decisiones de `frontend/brainstorming_Growen.md`: Composition API con `script setup`, Vuetify, SASS, shell con navegación lateral y módulos cargados de forma diferida.

## 2. Observaciones

Inventario inicial del frontend React:

- 120 archivos TypeScript/TSX y aproximadamente 23.405 líneas.
- 32 páginas, 44 componentes, 23 servicios y 6 archivos de pruebas.
- Los componentes más complejos siguen siendo `ProductsDrawer.tsx` y `ProductDetail.tsx`; la migración Vue los divide por capacidades en lugar de replicarlos como componentes monolíticos.
- Autenticación, rutas, tema, notificaciones y el contexto de canonización masiva son dependencias transversales.
- El baseline exhaustivo de rutas, roles, inputs, acciones, endpoints y mapeo Plugin-based UI está en `docs/relevamiento_admin.md`; debe usarse como checklist de paridad funcional.

La primera base Vue incluye:

- Vue 3, Vuetify 3, Vue Router 4, Pinia, Axios y SASS.
- Shell responsive, tema claro/oscuro, rutas lazy y navegación filtrada por rol.
- Sesión contra `/auth/login`, `/auth/guest`, `/auth/me` y `/auth/logout`.
- Protección CSRF para mutaciones.
- Contratos de las rutas React actuales; los módulos aún no migrados muestran un estado explícito.

## 3. Errores y/u outputs

- Vue `npm test`: 82 pruebas aprobadas en 23 archivos el 2026-07-25.
- Vue `npm run test:e2e`: 5 smokes Playwright aprobados para sesión, guardas, Servicios/Workers, MCP, Usuarios y Backups.
- `pytest` focalizado: 4 pruebas aprobadas para reglas y autorización real del borrado de productos.
- La validación de Compras prioriza errores bloqueantes sobre advertencias, resalta bonificaciones inválidas y ofrece feedback al intentar confirmar un borrador.
- `npm run build`: builds React y Vue aprobados; la imagen dual `growen-frontend` también construye y `nginx -t` valida correctamente.
- `npm audit`: 0 vulnerabilidades tanto en Vue como en el fallback React luego de actualizar el lock legacy dentro de sus rangos semver.
- La suite React legacy mantiene 53 pruebas aprobadas y 2 fallas previas al corte (`Market.test.tsx` y `ProductsDrawer.refresh.test.tsx`); no bloquean el quality gate Vue, pero deben corregirse antes de convertir React en gate obligatorio.
- La toolchain se mantiene en TypeScript 5 porque `vue-tsc` no fue compatible con la exportación interna de TypeScript 7 durante este corte.
- La carga completa de Material Design Icons agrega fuentes grandes al build; se registra como optimización futura.

## 4. Objetivo

Reemplazar React por Vue sin interrumpir operación, conservando rutas, roles, contratos HTTP y comportamiento observable. React se retirará sólo cuando los módulos críticos alcancen paridad y el build Vue pase las validaciones de integración.

## 5. Propuesta de código o pasos

1. **Base transversal (completada):** toolchain, shell, router, roles, sesión, tema y cliente HTTP.
2. **Componentes compartidos (en progreso):** notificaciones y manejo global de errores completados; pendientes tablas, formularios, diálogos y carga de archivos reutilizables.
3. **Primeros dominios funcionales (completado):** Dashboard, Compras, primer corte de Productos y Proveedores básico.
4. **Productos (en progreso):** listado, alta, categorías, stock, precio efectivo, borrado protegido, enriquecimiento masivo, completar precios y catálogos completados; pendientes detalle enriquecido, equivalencias, imágenes, preferencias y activación productiva.
5. **Stock (activo en Vue):** listado y Faltantes reciben tráfico Vue; quedan pendientes smoke por rol, concurrencia PostgreSQL y retiro React.
6. **Mercado (activo en Vue):** listado, jobs, fuentes e histórico reciben tráfico Vue; quedan pendientes smoke final, ventana estable y retiro React.
7. **Cambio de tráfico (completado):** Docker/Nginx compilan ambas SPAs y seleccionan el runtime desde el manifiesto; FastAPI ya no necesita decidir el índice en el camino productivo.
8. **Retiro de React:** eliminar dependencias y código legado en un cambio separado y reversible.

### Primer arranque local

El método oficial de desarrollo es el script único. Desde la raíz del repositorio:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

El script reutiliza `docker-compose:db` cuando ya está activo; sólo levanta ese contenedor cuando falta. Luego ejecuta `alembic upgrade head`, verifica las dependencias Node, inicia la API local y finalmente Vite. API y Vue se consideran listos únicamente cuando responden sus endpoints HTTP.

Abrir `http://127.0.0.1:5176/login`. La SPA Vue usa el puerto 5176 y `VITE_API_BASE_URL=/api`; su proxy apunta a `VITE_API_TARGET` (por defecto `http://127.0.0.1:8000`). `VITE_API_URL` queda solo como alias temporal. React continúa en su puerto habitual.

Cada ejecución crea `logs/dev/<fecha-hora>/` con:

- `start-dev.log`: secuencia y resultado general.
- `database.log` y `migrations.log`: PostgreSQL y Alembic.
- `api.stdout.log` y `api.stderr.log`: backend local.
- `frontend-vue.stdout.log` y `frontend-vue.stderr.log`: Vite.
- `state.json`: URLs, PIDs iniciados y servicios reutilizados.

Los archivos stdout/stderr pertenecen a la ejecución que inició el proceso. Las ejecuciones posteriores reutilizan los servicios saludables y lo indican en su propio `state.json`, mientras el proceso continúa escribiendo en sus logs originales.

Si el script termina con error, revisar primero la ruta de logs que muestra en consola. Los comandos manuales se reservan para troubleshooting.

Los MCP son opcionales para autenticación. Cuando el módulo que se prueba los necesite, se pueden sumar con:

```powershell
docker compose up -d mcp_products mcp_web_search
```

Si la pestaña queda cargando con fondo oscuro, comprobar primero `http://127.0.0.1:8000/health`: Vue rehidrata la sesión mediante `/auth/me` antes de permitir una ruta protegida.

### Verificación

```powershell
cd frontend-vue
npm.cmd test
npm.cmd run test:e2e
npm.cmd run build
npm.cmd audit --audit-level=high
```

## Activación de Clientes y Ventas

Los módulos `customers` y `sales` están activos en `config/modules.json`. Incluyen `/clientes`, `/clientes/:id`, `/ventas`, `/ventas/nueva` y `/ventas/:id`. El build Vue publica referencias bajo `/vue-assets`; React conserva `/assets`.

Nginx selecciona el índice por las reglas generadas desde el manifiesto. Procedimiento de corte:

1. Confirmar `state: "active"` y `runtime: "vue"` para el dominio.
2. Ejecutar `npm run generate:nginx` y el quality gate.
3. Reconstruir y desplegar el contenedor frontend.
4. Para rollback, cambiar el runtime a `legacy`, regenerar y desplegar; no revertir migraciones ni datos.

La operación detallada está en `docs/FRONTEND_MIGRATION_OPERATIONS.md`.

## Activación de Servicios administrativos

El módulo `admin-services` está `active` en Vue y publica `/admin/servicios`, `/admin/servicios/workers` y `/admin/servicios/mcp-tools`. El manifiesto mantiene el wildcard `/admin/*` en React para que los demás plugins administrativos continúen operativos durante la migración.

- Workers: `colaborador` y `admin`, capacidad `services.control`.
- MCP: solo `admin`, en concordancia con `/admin/mcp/*`.
- Instalación de dependencias: visible solo con `services.dependencies.install`.
- Logs en vivo: transporte SSE compartido bajo `/api/admin/services/{name}/logs/stream`.

Usuarios y Backups también están activos en Vue como módulos independientes, ambos solo para `admin` y protegidos por `users.manage` y `backups.manage`. Las descargas de backup usan el helper autenticado de blobs; ya no navegan a una URL construida por la vista.

La retrospectiva y el handoff del corte están en `docs/RETROSPECTIVE_FRONTEND_ADMIN_20260718.md`. El HTTP 500 informado durante una prueba no tuvo request ni stack trace suficientes para determinar causa raíz; no debe considerarse resuelto sin una nueva reproducción instrumentada.

## 6. Criterios de aceptación

- Cada ruta migrada conserva permisos y contratos HTTP del frontend React.
- Todo componente Vue usa Composition API con `script setup`.
- Los módulos migrados tienen pruebas proporcionales a su riesgo.
- `npm run build` y `npm test` finalizan correctamente.
- Solo los módulos `active` son servidos por Vue; el resto conserva fallback React.
- Las dependencias nuevas quedan declaradas en `package.json` y fijadas en `package-lock.json`.
- Se documentan los cambios y se actualiza cualquier contenido desactualizado en `Roadmap.md`, `README.md` y `docs/`.
