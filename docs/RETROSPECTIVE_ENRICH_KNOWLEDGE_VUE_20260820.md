<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_ENRICH_KNOWLEDGE_VUE_20260820.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_ENRICH_KNOWLEDGE_VUE_20260820.md -->
<!-- NG-HEADER: Descripción: Cierre factual de calidad editorial Enrich y Conocimiento Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva — Enrich v2 y Conocimiento Vue

## Contexto

La sesión del 20 de agosto de 2026 abarcó el contrato editorial de Enrich v2,
la presentación de especificaciones e instrucciones y el acceso de Producto a
su Base de Conocimiento Canónica. La evidencia consultada incluye el historial
visible de la sesión, el diff local, pruebas backend/Vue, build y un smoke real
en Chrome autenticado como `admin`.

El worktree ya contenía cambios preexistentes de observabilidad de proveedores,
aislamiento de workers y Chat/Telegram. Esta retrospectiva no los atribuye a la
sesión salvo cuando fueron modificados explícitamente para los objetivos
anteriores. No se ejecutaron commit, push, migraciones ni enriquecimiento masivo.

## Observaciones

| Tarea | Estado | Evidencia |
|---|---|---|
| Evitar referencias a fuentes dentro de la descripción comercial | Completada | Prompt explícito y rechazo determinista de metadiscurso en `services/jobs/enrichment_jobs.py`; 17 pruebas Enrich aprobadas. |
| Mostrar especificaciones e instrucciones sin JSON crudo | Completada | `StructuredProductData.vue`, ocultamiento de metadatos de procedencia y smoke sobre producto 18. |
| Recuperar legibilidad de Conocimiento | Completada con cambio de enfoque | El modal de Producto fue reemplazado por `/productos/:id/Conocimiento`; Mercado conserva su diálogo contextual. |
| Verificar navegación y permisos | Completada | 39 pruebas Vue, typecheck, build y navegación real desde `/productos/20` como `admin`, sin errores de consola. |
| Regenerar contenido histórico y ejecutar Enrich masivo | Pendiente | No se reinició el worker ni se lanzó el lote; el producto 18 conserva la descripción anterior hasta regenerarse. |

Se actualizaron `README.md`, `Roadmap.md`, `CHANGELOG.md`,
`docs/PRODUCTS_UI.md` y la documentación agéntica.

## Errores y/u outputs

1. **El primer ajuste del modal no resolvió la experiencia.**
   - Síntoma: el overlay continuó desproporcionado y luego el área de contenido
     quedó prácticamente invisible.
   - Causa: una superficie con siete pestañas, filtros, CRUD y listas extensas
     no era adecuada para el overlay; además, las pruebas de componente/build no
     validaban la composición con datos reales.
   - Solución: ruta dedicada y modo embebido del centro compartido.
   - Evidencia posterior: `/productos/20/Conocimiento` mostró cinco activos y la
     navegación desde el botón de la ficha quedó comprobada.

2. **La prueba nueva falló por `ResizeObserver` ausente en JSDOM.**
   - Impacto: un test rojo, sin fallo de producción.
   - Solución: stub local siguiendo el patrón Vuetify existente.
   - Evidencia posterior: selección consolidada de 39 pruebas aprobada.

3. **Pytest no pudo iniciar dentro del sandbox de Windows.**
   - Síntoma: `Acceso denegado` al crear el proceso del venv.
   - Solución: repetir el mismo comando autorizado fuera del sandbox, siempre
     con `.venv\Scripts\python.exe`.
   - Evidencia posterior: 17 pruebas focales Enrich aprobadas.

Riesgos residuales: el worker debe reiniciarse para adoptar el nuevo prompt y
el lote masivo necesita observar deduplicación canónica, estados terminales,
calidad editorial y carga de la nueva vista con mayor volumen de activos.

## Objetivo

Preservar dos decisiones: la procedencia se mantiene en trazabilidad y nunca en
el texto publicable; las superficies operativas densas y navegables deben usar
una ruta propia, no un modal ajustado sucesivamente por CSS.

## Propuesta de código o pasos

### Prevención

1. **Prioridad alta — ampliar `vue-module-migration`.** Exigir elección explícita
   de página, diálogo o drawer y smoke visual autenticado con datos
   representativos. Evidencia: dos iteraciones fallidas del modal. Frecuencia:
   alta en cortes administrativos Vue. Costo: bajo; beneficio: menos retrabajo.
2. **Prioridad alta — validar desde la acción de origen.** Un acceso directo a la
   URL no prueba que el botón, nombre de ruta y permisos estén conectados.
   Evidencia: el smoke final navegó desde Producto y comprobó el destino.
3. **Prioridad media — mantener APIs del navegador en el harness.** Declarar
   `ResizeObserver`/`visualViewport` según el componente Vuetify usado.

### Aceleración

1. Incorporar el checklist
   `.agents/skills/vue-module-migration/references/visual-validation-checklist.md`
   para reutilizar la secuencia manifest → generación Nginx → tests → typecheck
   → build → smoke por rol.
2. En la próxima sesión, ejecutar Enrich masivo sobre una selección pequeña
   primero; comprobar resultados y recién después ampliar el lote.

No se recomienda crear un agente independiente: el problema comparte contexto,
estado visual, permisos y worktree con la implementación Vue principal.

## Criterios de aceptación

- El reporte distingue cambios de sesión y cambios preexistentes.
- Los estados se apoyan en código, pruebas o smoke real.
- La prueba masiva y la regeneración histórica permanecen como pendientes.
- La documentación afectada está actualizada.
- La mejora agéntica tiene fuente canónica, frontmatter válido y quality gate.

