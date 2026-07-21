---
name: vue-module-migration
description: Planifica, implementa y valida migraciones incrementales de módulos React a Vue 3 en Growen, preservando contratos, rutas, permisos y fallback. Usar al migrar pantallas o capacidades desde frontend/ hacia frontend-vue/, recuperar paridad funcional o revisar un corte Vue.
---

# Migrar un módulo a Vue

Activar ante pedidos como “migrar Canónicos de React a Vue”, “recuperar una función React en Vue” o “revisar la paridad del módulo Vue”.

1. Leer `AGENTS.md`, `docs/FRONTEND_MIGRATION_VUE.md`, `docs/FRONTEND_DEBUG.md`, la documentación del dominio y las instrucciones de testing aplicables.
2. Inspeccionar `git status`, el diff activo y los archivos no versionados del alcance. Preservar cambios previos y no reformatear, revertir ni regenerar artefactos ajenos.
3. Relevar la capacidad React actual en `frontend/`: rutas, roles, estados, inputs, acciones, endpoints, errores, persistencia local y dependencias con otros módulos.
4. Contrastar cada contrato con backend y tests. No inferir reglas de negocio desde el componente React si la API o el modelo actual difieren.
5. Definir un corte pequeño con matriz de paridad y criterios observables. Mantener rutas públicas y fallback React para todo lo que quede fuera del corte.
6. Implementar en `frontend-vue/src/modules/<dominio>/` separando `api`, `types`, `composables`, `components` y `views`. Reutilizar Vue 3, Vuetify, Axios y utilidades existentes; no agregar dependencias sin justificar y documentar.
7. Mantener autorización en router, navegación y UI, pero tratar FastAPI como autoridad final. No mostrar mutaciones a roles sin permiso y cubrir 401, 403, 404, 409 y 500 cuando apliquen.
8. Usar `/api` y el proxy canónico de Vue. No sumar prefijos de dominio a Vite si el transporte compartido ya los cubre.
9. Para búsquedas o polling, cancelar respuestas obsoletas, detener timers al desmontar y persistir sólo datos necesarios. Para jobs, exigir idempotencia, estados terminales y errores parciales tipados.
10. Antes de cambiar la firma o el tipo de retorno de un helper compartido, localizar todos sus consumidores con `rg`; adaptar y probar cada call site, incluidos handlers, intents y compatibilidad React.
11. Agregar pruebas unitarias y de componentes. Las interacciones de Vuetify deben montar Vuetify real: configurar `vite-plugin-vuetify`, incluir `vuetify` en las dependencias inline de Vitest y proveer en JSDOM los APIs ausentes usados por el componente, como `ResizeObserver` o `visualViewport`. Al cambiar plugins globales, revisar pruebas vecinas porque un auto-import real puede dejar sin efecto stubs shallow.
12. En Windows usar `npm.cmd`. El script `npm.cmd test` ya incluye `vitest --run`; para una suite focal ejecutar `npm.cmd test -- <ruta>` sin repetir `--run`.
13. Ejecutar `npm.cmd run typecheck`, pruebas y build. Declarar explícitamente arreglos con opciones discriminadas antes de insertar elementos sintéticos para Vuetify; una prueba de componente verde no sustituye a `vue-tsc`.
14. Si el corte toca backend, ejecutar Python sólo con `.\.venv\Scripts\python.exe` y no lanzar dos procesos pytest simultáneos en el mismo checkout. Empezar por módulos focales y repetir al final la selección consolidada afectada. Usar la skill `database-migrations` cuando cambien modelos o Alembic.
15. Validar en `http://127.0.0.1:5176/<ruta>` con el rol requerido. Cuando esté disponible, usar la skill `browser:control-in-app-browser` para escribir, seleccionar, guardar, recargar y comprobar persistencia. Hacer preflight de la superficie solicitada; HTTP 200 no equivale a validación visual y un bloqueo debe quedar explícito.
16. Actualizar `Roadmap.md`, `README.md`, `CHANGELOG.md` y documentos del dominio cuando cambien comportamiento, contratos, rutas, permisos o estado de migración.
17. No cambiar tráfico productivo, Docker ni retirar React salvo autorización explícita y paridad comprobada del dominio completo.

Entregar siempre el alcance migrado, límites restantes, pruebas ejecutadas, resultados y bloqueos reproducibles.
