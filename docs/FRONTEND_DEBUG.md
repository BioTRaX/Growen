<!-- NG-HEADER: Nombre de archivo: FRONTEND_DEBUG.md -->
<!-- NG-HEADER: Ubicación: docs/FRONTEND_DEBUG.md -->
<!-- NG-HEADER: Descripción: Guía de diagnóstico de frontend (login/carga) -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Guía de diagnóstico Frontend (Login no carga / pantalla en "Cargando…")

## Objetivo
Proveer pasos rápidos para detectar por qué la pantalla de login no aparece y la SPA queda en estado de carga.

## Convivencia durante la migración a Vue

- React productivo/desarrollo: `frontend/`, puerto 5175 según su configuración actual.
- Vue en migración: `frontend-vue/`, puerto 5176.
- Iniciar Vue: `cd frontend-vue && npm.cmd run dev`.
- Vue usa `VITE_API_BASE_URL=/api` y el proxy de Vite para evitar diferencias de host en cookies. `VITE_API_URL` es un alias temporal.
- Docker/Nginx compila y sirve React y Vue: el manifiesto modular decide la SPA por ruta y mantiene React como fallback.
- Plan y estado: `docs/FRONTEND_MIGRATION_VUE.md`.

## Checklist rápido
1. Verificar que el dev server esté corriendo:
   - `cd frontend && npm run dev`
   - Acceder a `http://localhost:5175/` (o el puerto configurado por `VITE_PORT`).
2. Confirmar que el backend responde:
   - `curl http://127.0.0.1:8000/auth/me` → debe devolver JSON con `is_authenticated`.
3. Asegurar orígenes CORS:
   - Variable `ALLOWED_ORIGINS` incluye `http://localhost:5173` y/o `5175`.
4. Sincronía host para cookies:
   - El frontend se debe abrir con el mismo hostname (localhost vs 127.0.0.1) que espera el backend para compartir cookies.
5. Revisar consola del navegador:
   - Errores de módulos (chunk 404, type error) impiden montar `AuthProvider`.
6. Endpoints de diagnóstico:
   - `GET /debug/frontend/diag` → estado del build de producción.
   - `GET /debug/frontend/ping-auth` → prueba directa de autenticación + cookies presentes.
7. Alias `/app`:
   - `GET /app` sirve el build de producción (alias legacy). En desarrollo normal usa directamente el servidor Vite.

## Modo desarrollo vs Ruta /app (Build producción)

| Aspecto | Dev Server (Vite) | Backend `/app` |
|---------|-------------------|----------------|
| Comando | `cd frontend && npm run dev` | `cd frontend && npm run build` luego iniciar backend |
| Puerto  | 5175 (fijo, configurable con `VITE_PORT` antes de arrancar) | 8000 (mismo que API) |
| Hot Reload | Sí (HMR) | No |
| Source Maps | Completos | Normalmente minificados |
| Uso recomendado | Desarrollo iterativo | Verificación pre-deploy / compartir snapshot |
| Requiere `dist` | No | Sí (carpeta `frontend/dist`) |

Notas:
- El error `EACCES: permission denied %VITE_PORT%` provenía de usar `%VITE_PORT%` (sintaxis CMD) en PowerShell. Se fijó un puerto explícito en los scripts `dev` y `preview`.
- Para cambiar puerto temporalmente: `set VITE_PORT=5180` (CMD) / `$env:VITE_PORT=5180` (PowerShell) antes de `npm run dev`; Vite leerá el valor en `vite.config.ts`.
- Si `Test-NetConnection 127.0.0.1 -Port 5175` falla, el dev server no está corriendo (o el puerto cambió). Reinicia `npm run dev` y verifica.
- Vue usa un proxy único: `/api/*` apunta a FastAPI eliminando `/api`, y `/media/*` conserva la ruta. No se agregan prefijos de dominio a Vite ni el puerto 5176 a CORS. WebSocket se habilita dentro de `/api`.

Para diagnosticar qué SPA debe responder una ruta, revisar `frontend-vue/config/modules.json`, regenerar con `npm run generate:nginx` y contrastar `frontend-vue/generated/nginx-spa-routes.conf`. La guía completa está en `docs/FRONTEND_MIGRATION_OPERATIONS.md`.

## Errores típicos recientes

| Síntoma | Causa | Resolución |
|---------|-------|------------|
| `EACCES: permission denied %VITE_PORT%` | Placeholder CMD no expandido en PowerShell | Ajustar scripts a puerto fijo o usar `cross-env` |
| 404 en `/app` tras limpiar `dist` | Build ausente | Ejecutar `npm run build` dentro de `frontend/` |
| Frontend no responde en 5175 | Servidor no iniciado | Correr `npm run dev` |
| UI carga pero API falla | Backend aún iniciando | Esperar a que logs muestren `Application startup complete` |
| `/api/health` en 5176 devuelve HTML | Vite fue iniciado antes de cargar el proxy actual | Identificar el PID de 5176, reiniciar Vue y confirmar que la respuesta sea JSON |
| Recurso responde 500 sin URL ni correlation ID | Evidencia insuficiente para aislar backend, proxy o vista | Capturar request, response, `X-Correlation-ID`, rol, release y logs del mismo instante |

## Interpretación de `/debug/frontend/diag`
Campos:
- `build_present`: Detectó `frontend/dist/index.html` y un bundle principal `index-*.js`.
- `assets_count`: Número de archivos en `dist/assets`. Cero indica build incompleto.
- `main_bundle`: Nombre del bundle principal.
- `api_base_url`: Valor heurístico que el cliente usaría.
- `notes`: Lista de advertencias si falta algo.

## Casos frecuentes
| Síntoma | Causa probable | Acción |
|--------|----------------|-------|
| Pantalla queda en "Cargando…" | Error JS en chunk lazy | Ver consola devtools, reconstruir `npm run build` o revisar import lazy. |
| No aparecen requests `/api/auth/me` | Bundle no ejecuta o base URL rota | Ver `VITE_API_BASE_URL`, el proxy `/api`, consola y network. |
| Cookies no se guardan | Mezcla `localhost` vs `127.0.0.1` o `https` inconsist. | Usar host consistente; revisar `SameSite` y `Secure`. |
| 403 CSRF en mutaciones | Falta header `X-CSRF-Token` | Confirmar cookie `csrf_token`; en dev puede estar deshabilitado override. |
| Login correcto pero toda mutación responde 403 | Sesión creada por una versión anterior al arreglo del SID | Volver a iniciar sesión una vez; `/auth/me` debe responder `is_authenticated: true` y el rol real. |

## Buenas prácticas
- Abrir siempre el frontend dev (Vite) durante desarrollo en vez de depender del build en `dist`.
- Limpiar caches si se modificó la ruta base: `Application > Clear site data`.
- Mantener logs de backend abiertos para ver si llegan `GET /auth/me` al refrescar.
- Reiniciar Vite tras cambios en `vite.config.ts`, variables `VITE_*` o scripts de arranque; no asumir que HMR aplicó configuración de infraestructura.

## QA de mutaciones Vue con navegador

1. Comprobar el estado y las precondiciones visibles antes de hacer clic. Un botón deshabilitado debe explicar por qué no puede ejecutarse la acción.
2. Después de guardar o validar, verificar el contrato HTTP completo: `errors` bloqueantes tienen prioridad sobre `warnings`; un HTTP 200 no equivale por sí solo a una validación exitosa.
3. Correlacionar consola y estado del navegador con el access log del backend. Si la respuesta es un 409 o un `IntegrityError` genérico, consultar los logs de PostgreSQL para obtener tabla, columna y constraint exactos.
4. Con hot reload activo, esperar nuevamente el healthcheck de la API antes de repetir una mutación. Los cambios en documentación, scripts o tests pueden reiniciar Uvicorn según la configuración del watcher.
5. Si hay varias pestañas del mismo recurso, confirmar URL, estado y contenido de la pestaña controlada antes de atribuir un resultado a la última acción.
6. Tras una operación transaccional de alto impacto, refrescar la vista y contrastar el estado persistido y sus efectos de dominio; no aceptar únicamente un alert de éxito como evidencia.
7. No copiar cookies, tokens ni URLs con credenciales a reportes. Los scripts y logs de diagnóstico deben enmascarar secretos.
8. En flujos asíncronos, un HTTP 202 sólo prueba que la API aceptó o reconoció la solicitud. Verificar el estado persistido (`QUEUED`, `RUNNING`, `COMPLETED`, `PARTIAL`, `FAILED`), la cola y el efecto de dominio después de recargar.
9. Si un batch devuelve un job `FAILED` con `processed_items=0`, distinguir un fallo global de infraestructura de errores por fila. El wizard canónico debe ofrecer **Reintentar lote**; **Corregir fallidos** corresponde a ítems efectivamente procesados con error.

### Preflight de automatización de navegador

- Antes de prometer un smoke visual automatizado, comprobar que la superficie solicitada está disponible. Si el usuario exige Chrome, la extensión y su host nativo deben estar instalados y comunicarse con el navegador.
- En Codex, cuando esté disponible, usar la skill `browser:control-in-app-browser` para el smoke local. Registrar ruta, rol, texto escrito, opción seleccionada, respuesta visible y estado después de recargar; una captura aislada no prueba persistencia.
- Si Chrome no está disponible, no sustituir silenciosamente la validación por otro navegador ni por Playwright independiente. Registrar el bloqueo, conservar la evidencia automática (`test`, `typecheck`, `build`) y verificar por HTTP que la ruta objetivo responde, aclarando que esto no constituye validación visual.
- Un `403` al consultar directamente un endpoint protegido sin sesión —por ejemplo `GET /categories`— confirma la barrera de autorización, no un defecto funcional. La prueba del formulario requiere una sesión staff y CSRF real.
- En entornos restringidos, `npm audit` puede fallar por red o por no poder escribir el cache global. Repetirlo con la autorización mínima necesaria; no interpretar un error del endpoint de auditoría como vulnerabilidad del proyecto.

## Instrumentación añadida
- `AuthContext.refreshMe()` emite `console.debug` (solo en dev) antes y después del fetch `/auth/me`.
- ErrorBoundary global envuelve las cargas lazy; si hay un error de módulo se muestra mensaje claro.
- Endpoint `/debug/frontend/ping-auth` ya disponible.
- Endpoint `/debug/frontend/log-error` recibe errores capturados por el ErrorBoundary.
- Endpoint `/debug/frontend/env` expone variables de entorno filtradas (sin secretos) para depuración.
- Botón "Reintentar" en la UI de ErrorBoundary fuerza un reload completo.
 - Botón flotante "Reportar" permite enviar un reporte manual a `/bug-report` incluyendo URL y hora (GMT-3). Ver `docs/BUG_REPORTS.md`.

## Próximos pasos automatizables
- ErrorBoundary podría enviar errores a un endpoint de logging.
- Añadir `/debug/frontend/env` para exponer variables relevantes filtradas.
 - Persistir un contador de errores recientes para detectar loops.

---
Actualizado: 2026-07-18
