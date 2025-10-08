<!-- NG-HEADER: Nombre de archivo: FRONTEND_DEBUG.md -->
<!-- NG-HEADER: Ubicación: docs/FRONTEND_DEBUG.md -->
<!-- NG-HEADER: Descripción: Guía de diagnóstico de frontend (login/carga) -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Guía de diagnóstico Frontend (Login no carga / pantalla en "Cargando…")

## Objetivo
Proveer pasos rápidos para detectar por qué la pantalla de login no aparece y la SPA queda en estado de carga.

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
- El dev server ahora incluye proxy automático para `/auth`, `/products-ex`, `/products`, `/suppliers`, `/purchases`, `/stock`, `/media`, `/ws`, `/chat`, `/actions`. Si agregas un nuevo prefijo API añade la regla correspondiente en `vite.config.ts`.

## Errores típicos recientes

| Síntoma | Causa | Resolución |
|---------|-------|------------|
| `EACCES: permission denied %VITE_PORT%` | Placeholder CMD no expandido en PowerShell | Ajustar scripts a puerto fijo o usar `cross-env` |
| 404 en `/app` tras limpiar `dist` | Build ausente | Ejecutar `npm run build` dentro de `frontend/` |
| Frontend no responde en 5175 | Servidor no iniciado | Correr `npm run dev` |
| UI carga pero API falla | Backend aún iniciando | Esperar a que logs muestren `Application startup complete` |

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
| No aparecen requests /auth/me | Bundle no ejecuta o base URL rota | Ver `VITE_API_URL`, revisar consola y network. |
| Cookies no se guardan | Mezcla `localhost` vs `127.0.0.1` o `https` inconsist. | Usar host consistente; revisar `SameSite` y `Secure`. |
| 403 CSRF en mutaciones | Falta header `X-CSRF-Token` | Confirmar cookie `csrf_token`; en dev puede estar deshabilitado override. |

## Buenas prácticas
- Abrir siempre el frontend dev (Vite) durante desarrollo en vez de depender del build en `dist`.
- Limpiar caches si se modificó la ruta base: `Application > Clear site data`.
- Mantener logs de backend abiertos para ver si llegan `GET /auth/me` al refrescar.

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
Actualizado: 2025-10-07