<!-- NG-HEADER: Nombre de archivo: AGENT_SKILLS.md -->
<!-- NG-HEADER: Ubicación: docs/AGENT_SKILLS.md -->
<!-- NG-HEADER: Descripción: Convenciones de descubrimiento y uso de skills agénticas de Growen. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Skills agénticas de Growen

## Fuente canónica y compatibilidad

Las skills del proyecto residen únicamente en `.agents/skills/<nombre>/SKILL.md`. Esta ubicación común es descubierta por Codex, Gemini CLI, GitHub Copilot y Antigravity. Los archivos bajo `.agent/skills/` son adaptadores legacy preexistentes: sólo redirigen a la fuente canónica y no deben duplicar procedimientos ni usarse para skills nuevas.

Referencias oficiales: [skills de Codex](https://learn.chatgpt.com/codex/build-skills), [skills de Gemini CLI](https://codelabs.developers.google.com/gemini-cli/how-to-create-agent-skills-for-gemini-cli), [skills de GitHub Copilot](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) y [skills de Antigravity](https://antigravity.google/docs/skills).

## Compatibilidad con Superpowers

Las skills externas de Superpowers pueden utilizarse como metodología general, pero no reemplazan ni desactivan las reglas locales de Growen. La precedencia es la siguiente:

1. `AGENTS.md` y las skills canónicas de Growen (bajo `.agents/skills/`) tienen prioridad sobre cualquier flujo de Superpowers.
2. Los gates de seguridad y Git de Growen prevalecen sobre commits automáticos, pushes, merges o publicación de ramas.
3. Todo trabajo se realiza en una rama efímera creada desde `dev`; los commits directos a `dev` están prohibidos. Un trigger válido de cierre autoriza la integración secuencial, sin eliminar los gates de secretos, alcance, pruebas, documentación, remoto y riesgo.
4. Los flujos de Superpowers solo pueden operar con Python y pytest del venv de Growen (`.venv\Scripts\python.exe`) o con Docker; no se permiten ejecutables del sistema.
5. Todo Markdown bajo `docs/superpowers/` debe incluir NG-HEADER y mantenerse alineado con la documentación viva del proyecto.
6. Las respuestas, documentación y comunicación de skills externas deben mantenerse en español.

### Matriz de responsabilidad y carga mínima

| Skill de Growen | Superpowers relacionada | Responsabilidad exclusiva de Growen |
|---|---|---|
| `skill-scaffolder` | `writing-skills` | Fuente `.agents/skills`, frontmatter, compatibilidad y quality gate local |
| `diagnose-local-services` | `systematic-debugging` | Recorrido UI → API → Redis/Dramatiq → PostgreSQL, puertos, PID y logs por ejecución |
| `database-migrations` | `systematic-debugging`, `verification-before-completion` | Alembic, drift histórico, PostgreSQL y comandos del venv |
| `git-commit-push` | `verification-before-completion` | Autorización, ramas efímeras, secretos, remoto y merge final hacia `dev` |
| `retrospectiva-tecnica-sesion` | `verification-before-completion` | Triggers exactos, evolución agéntica, riesgo y cierre secuencial |
| `create-service` | `writing-plans`, `test-driven-development` | Dramatiq, MCP, Docker y operación de servicios Growen |
| `vue-module-migration` | `brainstorming`, `test-driven-development` | Paridad React/Vue, Vuetify, rollback y smoke autenticado |
| `git-secret-forensics` | Sin equivalente directo | Rotación, `git-filter-repo`, referencias remotas y evidencia redactada |

No cargar una skill de Superpowers sólo porque comparte vocabulario con la tarea. Cargarla cuando su metodología sea necesaria y luego aplicar únicamente la capa local relevante. Las skills locales no deben copiar ciclos, checklists ni explicaciones completas del pack.

En resumen, Superpowers aporta disciplina y composición de flujos; Growen conserva la autoridad final sobre seguridad, entorno, idioma, documentación y publicación.

Las 14 skills de Superpowers se mantienen en su instalación global y se actualizan desde el repositorio original. Growen no conserva forks locales: aplica esta capa de precedencia al descubrirlas desde el directorio compartido del usuario.

## Retrospectiva técnica de sesión

Usar `retrospectiva-tecnica-sesion` únicamente ante `Cerrar sesión` o
`Cerremos sesión`. Si existe trabajo pendiente ambiguo, pedir confirmación antes
de comenzar. Completar una implementación, solicitar una retrospectiva o decir
«terminamos» no activa la skill por sí solo.

Una vez satisfecho ese gate, la skill permite:

- verificar tareas y evidencia antes de declararlas completas;
- registrar errores, causas, soluciones y riesgos residuales;
- corregir documentación desactualizada verificable;
- proponer controles preventivos nacidos de problemas reales;
- detectar aceleradores reutilizables aun cuando el trabajo haya sido exitoso y sencillo.

Invocación sugerida en cualquier agente: `Cerrar sesión` o `Cerremos sesión`.

No son triggers suficientes: «terminá la implementación», «actualizá la
documentación», «dame el estado», «terminamos», «final del chat» o nombrar la
skill. En esos casos se continúa trabajando.

Las propuestas deben diferenciar entre ampliar una skill existente, crear una nueva, añadir un script o referencia, mejorar el contexto y delegar trabajo. Una sesión sin errores también puede justificar un acelerador si contiene pasos repetibles con beneficio claro.

## Aprendizajes operativos incorporados

La retrospectiva de [Chat, Telegram, RAG y Vue del 2026-08-17](./RETROSPECTIVE_CHAT_RAG_VUE_20260817.md)
dejó tres controles reutilizables para futuras entregas:

- aislar en tests tanto el secreto directo como su variante `*_FILE`, para que el
  `.env` local no altere casos que deben ser deterministas;
- ejecutar `git check-ignore -v` sobre artefactos nuevos que se espera versionar,
  especialmente manifiestos JSON y corpus controlados;
- antes de publicar a un remoto externo, informar URL y cantidad de archivos y
  conservar los commits locales si todavía falta autorización explícita.

Estos controles amplían el contexto operativo; no sustituyen las skills
`git-commit-push`, `git-secret-forensics` ni sus gates de autorización.

La retrospectiva de [Enrich v2 y Conocimiento Vue del 2026-08-20](./RETROSPECTIVE_ENRICH_KNOWLEDGE_VUE_20260820.md)
incorporó un control adicional a `vue-module-migration`:

- elegir página, diálogo o drawer antes de implementar una superficie compuesta;
- no aceptar pruebas/build como sustituto del smoke visual autenticado;
- validar rutas nuevas desde la acción de origen, con datos representativos,
  consola y composición visibles;
- regenerar el manifiesto/Nginx cuando cambie `config/modules.json`.

El checklist canónico vive junto a la skill en
`.agents/skills/vue-module-migration/references/visual-validation-checklist.md`.

La retrospectiva de [SiYuan MCP del 2026-08-28](./RETROSPECTIVE_SIYUAN_MCP_20260828.md)
incorporó un contrato especializado a `create-service` para mutaciones
documentales y Attribute Views:

- crear historial y revalidar autoridad antes de toda escritura;
- tratar resultados ambiguos como estado incierto, sin reintento automático;
- reconciliar únicamente artefactos generados y vacíos que puedan demostrarse;
- aceptar la tool mediante MCP real, API semántica y verificación visual, en ese
  orden.

La referencia canónica vive en
`.agents/skills/create-service/references/siyuan-mcp-mutations.md`.

La retrospectiva del [widget Crono de SiYuan del 2026-08-29](./RETROSPECTIVE_SIYUAN_WIDGET_CRONO_20260829.md)
evaluó crear una skill especializada, pero el escenario de control sin esa skill
ya produjo el procedimiento correcto. Para evitar duplicación, el aprendizaje
mecánico se materializó en `scripts/sync-siyuan-widget.ps1`:

- comparar siempre la fuente versionada con la copia operativa realmente servida;
- mantener el diagnóstico por hash como comportamiento predeterminado;
- copiar sólo archivos runtime mediante `-Apply`, sin borrar extras ni leer secretos;
- aceptar cambios de Attribute Views con pruebas puras, API semántica y smoke visual.

La decisión deja una frontera clara: las skills conservan criterios y juicio; el
script automatiza la sincronización repetible que no merece una skill propia.

## Auditoría ejecutable del entorno agéntico

`scripts/audit_agentic_environment.py` valida de forma determinista que existan
los documentos de gobernanza, que las skills canónicas tengan frontmatter válido
y que los adaptadores legacy redirijan a `.agents/skills/` sin duplicar reglas.
`scripts/check-quality.ps1 -AgentOnly` lo ejecuta automáticamente. La prueba
`tests/test_audit_agentic_environment.py` cubre el directorio de trabajo por
defecto, la gobernanza requerida y el rechazo de frontmatter cuyo delimitador de
cierre no aparezca inmediatamente después de `description`.
