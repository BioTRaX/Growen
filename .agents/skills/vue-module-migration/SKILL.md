---
name: vue-module-migration
description: Usar al crear, evolucionar, refactorizar o auditar un módulo o capacidad en frontend-vue/ conforme a los lineamientos modulares de Growen.
---

# Desarrollo y evolución modular en Vue

Activar ante pedidos como “crear un nuevo módulo en Vue”, “evolucionar una capacidad en frontend-vue”, “revisar paridad de un contrato en Vue” o “auditar vistas modulares de Growen”.

1. Leer `AGENTS.md`, `docs/development/FRONTEND_MIGRATION_VUE.md`, `docs/development/FRONTEND_MIGRATION_OPERATIONS.md`, `docs/development/FRONTEND_DEBUG.md`, la documentación del dominio y las instrucciones de testing aplicables.
2. Inspeccionar `git status`, el diff activo y los archivos no versionados del alcance. Preservar cambios previos y no reformatear, revertir ni regenerar artefactos ajenos.
3. El frontend de Growen opera al 100% sobre Vue 3 (React 19 fue retirado definitivamente el 2026-09-15). Todo nuevo requerimiento se implementa exclusivamente en `frontend-vue/`.
4. Contrastar cada contrato con backend y tests. Validar contratos HTTP en FastAPI (`services/routers/`) y modelos asociados.
5. Para vistas compuestas o reclamos visuales, leer `references/visual-validation-checklist.md` y elegir explícitamente página, diálogo o drawer antes de implementar.
6. Implementar en `frontend-vue/src/modules/<dominio>/` separando `api`, `types`, `composables`, `components` y `views`. Reutilizar Vue 3, Vuetify, Axios y utilidades existentes; no agregar dependencias sin justificar y documentar.
7. Mantener autorización en router, navegación y UI, pero tratar FastAPI como autoridad final. No mostrar mutaciones a roles sin permiso y cubrir 401, 403, 404, 409 y 500 cuando apliquen.
8. Usar `/api` y el proxy canónico de Vue. No sumar prefijos de dominio a Vite si el transporte compartido ya los cubre.
9. Para búsquedas o polling, cancelar respuestas obsoletas, detener timers al desmontar y persistir sólo datos necesarios. Para jobs, exigir idempotencia, estados terminales y errores parciales tipados.
10. Antes de cambiar la firma o el tipo de retorno de un helper compartido, localizar todos sus consumidores con `rg`; adaptar y probar cada call site, incluidos handlers e intents.
11. Agregar pruebas unitarias y de componentes. Las interacciones de Vuetify deben montar Vuetify real: configurar `vite-plugin-vuetify`, incluir `vuetify` en las dependencias inline de Vitest y proveer en JSDOM los APIs ausentes usados por el componente, como `ResizeObserver` o `visualViewport`. Al cambiar plugins globales, revisar pruebas vecinas porque un auto-import real puede dejar sin efecto stubs shallow.
12. En Windows usar `npm.cmd`. El script `npm.cmd test` ya incluye `vitest --run`; para una suite focal ejecutar `npm.cmd test -- <ruta>` sin repetir `--run`.
13. Ejecutar `npm.cmd run typecheck`, pruebas y build. Declarar explícitamente arreglos con opciones discriminadas antes de insertar elementos sintéticos para Vuetify; una prueba de componente verde no sustituye a `vue-tsc`.
14. Si el corte toca backend, ejecutar Python sólo con `.\.venv\Scripts\python.exe` y no lanzar dos procesos pytest simultáneos en el mismo checkout. Empezar por módulos focales y repetir al final la selección consolidada afectada. Usar la skill `database-migrations` cuando cambien modelos o Alembic.
15. Si cambia `frontend-vue/config/modules.json`, ejecutar `npm.cmd run generate:nginx` y cubrir el manifiesto antes de typecheck/build; no editar `generated/modules.runtime.json` manualmente.
16. Validar en `http://127.0.0.1:5176/<ruta>` con el rol requerido y datos representativos. Cuando esté disponible, usar la skill `browser:control-in-app-browser` o `chrome:control-chrome` según dónde exista la sesión requerida. Iniciar el smoke desde la acción de origen, confirmar URL/título, revisar consola y composición visual; HTTP 200 o una suite verde no equivalen a validación visual.
17. Ante un reclamo visual acompañado de captura, inspeccionarla antes de editar. Si un overlay denso exige ajustes sucesivos de ancho, alto o scroll, reevaluar la superficie y preferir una ruta dedicada cuando corresponda.
18. Actualizar `Roadmap.md`, `README.md`, `CHANGELOG.md` y documentos del dominio cuando cambien comportamiento, contratos, rutas o permisos.

Entregar siempre el alcance implementado, límites restantes, pruebas ejecutadas, resultados y bloqueos reproducibles.
