<!-- NG-HEADER: Nombre de archivo: CATALOG.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/CATALOG.md -->
<!-- NG-HEADER: Descripción: Catálogo indexado minimalista de skills de Superpowers para carga diferida (lazy loading). -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Catálogo minimalista de Superpowers (Lazy Loading)

Este catálogo proporciona el registro indexado mínimo de las 14 skills de Superpowers disponibles en la instalación global (`~/.agents/skills/superpowers/` o `~/.codex/superpowers/skills/`). 

Su propósito es **reducir drásticamente el consumo de tokens** evitando la inyección de los 14 manifiestos completos en cada turno de conversación. Los agentes deben consultar este catálogo (consumo ~500 tokens) y **cargar el contenido extenso (`SKILL.md`) exclusivamente bajo demanda puntual**.

---

## Protocolo de carga diferida (Lazy Loading)

```
+-----------------------------------------------------------------------+
| Nivel 1: Registro Mínimo (Catálogo)                                  |
| Consulta de nombre + descripción de 1 línea (~500 tokens en prompt)   |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
| Nivel 2: Evaluación de Precedencia Growen                            |
| ¿Existe una skill canónica de Growen que resuelva la tarea?          |
| -> SÍ: Usar la skill canónica (.agents/skills/). NO cargar Superpowers |
| -> NO: Proceder a Nivel 3 si se requiere la metodología               |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
| Nivel 3: Carga Bajo Demanda (On-Demand Fetch)                         |
| Leer ÚNICAMENTE el SKILL.md requerido mediante herramienta de lectura |
| Ruta: ~/.agents/skills/superpowers/<nombre>/SKILL.md                  |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
| Nivel 4: Ejecución y Aislamiento                                      |
| Aplicar la metodología subordinada a AGENTS.md y cerrar contexto      |
+-----------------------------------------------------------------------+
```

---

## Índice minimalista de las 14 Skills

| # | Skill | Descripción corta (1 línea) | Cuándo cargar bajo demanda | Alternativa canónica Growen |
|---|-------|-----------------------------|----------------------------|-----------------------------|
| 1 | `brainstorming` | Exploración estructurada de requerimientos e intención de diseño antes de crear features. | Al iniciar un módulo o componente complejo sin especificación previa. | `vue-module-migration` (en UI) |
| 2 | `dispatching-parallel-agents` | Despacho concurrente de tareas independientes sin dependencias secuenciales ni estado compartido. | Al disponer de 2 o más sub-tareas desacopladas ejecutables en paralelo. | Subagentes nativos (`invoke_subagent`) |
| 3 | `executing-plans` | Ejecución guiada de planes paso a paso con puntos de control de revisión formal. | Al ejecutar un plan de implementación previamente redactado y aprobado. | N/A |
| 4 | `finishing-a-development-branch` | Metodología de cierre de rama tras pruebas exitosas y selección de estrategia de integración. | **Subordinada**: NO usar para git directo; el cierre en Growen lo gobierna `git-commit-push`. | `git-commit-push` |
| 5 | `receiving-code-review` | Evaluación rigurosa y no complaciente de observaciones recibidas en un code review. | Al procesar feedback crítico o ambiguo de revisiones de código de terceros. | N/A |
| 6 | `requesting-code-review` | Verificación de completitud y preparación de solicitud de revisión antes de merge. | Al culminar una feature mayor antes de solicitar revisión del usuario. | `retrospectiva-tecnica-sesion` |
| 7 | `subagent-driven-development` | Desarrollo guiado por subagentes para tareas modulares con contexto acotado en la misma sesión. | Al dividir un plan en sub-agentes con tareas aisladas. | Subagentes nativos (`invoke_subagent`) |
| 8 | `systematic-debugging` | Depuración metódica basada en hipótesis, evidencia y aislamiento de fallas antes de tocar código. | Al investigar un bug complejo de causa raíz desconocida. | `diagnose-local-services` (en servicios) |
| 9 | `test-driven-development` | Ciclo TDD estricto (red-green-refactor) antes de escribir código de producción. | Al diseñar lógica de negocio nueva que requiera suite unitaria previa. | Tests en `.venv` de Growen |
| 10 | `using-git-worktrees` | Aislamiento de directorios de trabajo concurrentes mediante git worktrees. | **Restringida**: En Growen el worktree físico es compartido y requiere lock `git-worktree`. | `scripts/agent_lock.py` |
| 11 | `using-superpowers` | Meta-regla de descubrimiento e invocación de skills dentro del ecosistema Superpowers. | Para entender la interacción entre skills del pack (lectura excepcional). | `docs/development/AGENT_SKILLS.md` |
| 12 | `verification-before-completion` | Verificación empírica con comandos reales y evidencia antes de afirmar que un cambio está listo. | Antes de cerrar cualquier tarea; no asumir éxito sin ejecutar pruebas. | `retrospectiva-tecnica-sesion` |
| 13 | `writing-plans` | Elaboración de planes detallados por pasos a partir de especificaciones y requerimientos. | Al planificar una feature o refactor que implique múltiples archivos/fases. | `create-service` (en servicios) |
| 14 | `writing-skills` | Guía de creación, edición y comprobación de nuevas skills. | Al redactar una skill nueva (debe adaptarse a la ubicación canónica local). | `skill-scaffolder` |

---

## Reglas de optimización de tokens para agentes

1. **Prohibida la inyección masiva:** Ningún agente ni prompt debe cargar los 14 manifiestos completos en el contexto inicial.
2. **Prioridad canónica:** Si la tarea encaja en `diagnose-local-services`, `database-migrations`, `git-commit-push`, `retrospectiva-tecnica-sesion`, `create-service`, `skill-scaffolder` o `vue-module-migration`, la skill canónica de Growen (`.agents/skills/`) es la única que debe consultarse.
3. **Carga puntual:** Si se requiere una skill de Superpowers (por ejemplo, `systematic-debugging`), el agente leerá únicamente `~/.agents/skills/superpowers/systematic-debugging/SKILL.md`.
4. **No propagación:** Al concluir la tarea asociada a la skill, el agente debe abstenerse de continuar citando o arrastrando las directivas genéricas de Superpowers que contradigan las normas de Growen (ej. uso de venv obligatorio, prohibición de commits directos a `dev`).
