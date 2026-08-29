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
3. Toda mutación Git requiere autorización explícita. En la rama exacta `dev`, el usuario puede autorizar la automatización para una entrega o sesión; esa autorización no elimina el gate de secretos, alcance, pruebas, documentación y remoto.
4. Los flujos de Superpowers solo pueden operar con Python y pytest del venv de Growen (`.venv\Scripts\python.exe`) o con Docker; no se permiten ejecutables del sistema.
5. Todo Markdown bajo `docs/superpowers/` debe incluir NG-HEADER y mantenerse alineado con la documentación viva del proyecto.
6. Las respuestas, documentación y comunicación de skills externas deben mantenerse en español.

### Matriz de solapamiento útil

- `writing-skills` / `skill-scaffolder`: complementarios; la metodología TDD de Superpowers puede reforzar la creación de skills, pero Growen conserva la salida canónica en `.agents/skills/` y el frontmatter obligatorio.
- `systematic-debugging` / `diagnose-local-services`: complementarios; la primera aporta análisis general, la segunda aporta el contexto técnico exacto de Growen (API, Docker, PostgreSQL, Redis, Dramatiq).
- `finishing-a-development-branch`, `requesting-code-review`, `executing-plans` / `git-commit-push`: parcialmente solapados; la regla local exige autorización explícita. Sólo `dev` admite automatización ya autorizada y siempre después del gate completo.
- `test-driven-development` / testing de Growen: complementarios; TDD define el orden metodológico, mientras Growen obliga a ejecutar pytest con `.venv\Scripts\python.exe` o Docker y a consultar `docs/TESTING.md`.
- `verification-before-completion` / `retrospectiva-tecnica-sesion`: complementarios; la primera aporta evidencia general, la segunda exige cierre explícito y no se activa por tareas aisladas.
- `using-git-worktrees` / `using-superpowers`: útiles como marco operativo, pero deben adaptarse a los requisitos de entorno de Growen y a los comandos Python permitidos.

En resumen, Superpowers aporta disciplina y composición de flujos; Growen conserva la autoridad final sobre seguridad, entorno, idioma, documentación y publicación.

Las 14 skills de Superpowers se mantienen en su instalación global y se actualizan desde el repositorio original. Growen no conserva forks locales: aplica esta capa de precedencia al descubrirlas desde el directorio compartido del usuario.

## Retrospectiva técnica de sesión

Usar `retrospectiva-tecnica-sesion` únicamente cuando el usuario informe de
forma explícita que llegó el final de la sesión o chat y solicite el cierre, la
retrospectiva o las lecciones aprendidas. Completar una implementación,
diagnóstico o migración no activa la skill por sí solo.

Una vez satisfecho ese gate, la skill permite:

- verificar tareas y evidencia antes de declararlas completas;
- registrar errores, causas, soluciones y riesgos residuales;
- corregir documentación desactualizada verificable;
- proponer controles preventivos nacidos de problemas reales;
- detectar aceleradores reutilizables aun cuando el trabajo haya sido exitoso y sencillo.

Invocación sugerida:

- Codex: «Éste es el final del chat; usá `$retrospectiva-tecnica-sesion`».
- Gemini CLI: comprobarla con `/skills` y declarar el cierre antes de solicitarla por nombre.
- GitHub Copilot CLI: «Terminamos la sesión; ejecutá `/retrospectiva-tecnica-sesion`».

No son triggers suficientes: «terminá la implementación», «actualizá la
documentación», «dame el estado» o nombrar la skill sin declarar que finaliza la
sesión. En esos casos se continúa trabajando y la retrospectiva se reserva para
cuando el usuario confirme el cierre.

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

## Auditoría ejecutable del entorno agéntico

`scripts/audit_agentic_environment.py` valida de forma determinista que existan
los documentos de gobernanza, que las skills canónicas tengan frontmatter válido
y que los adaptadores legacy redirijan a `.agents/skills/` sin duplicar reglas.
`scripts/check-quality.ps1 -AgentOnly` lo ejecuta automáticamente. La prueba
`tests/test_audit_agentic_environment.py` cubre el directorio de trabajo por
defecto, la gobernanza requerida y el rechazo de frontmatter cuyo delimitador de
cierre no aparezca inmediatamente después de `description`.
