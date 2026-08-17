<!-- NG-HEADER: Nombre de archivo: AGENT_SKILLS.md -->
<!-- NG-HEADER: Ubicación: docs/AGENT_SKILLS.md -->
<!-- NG-HEADER: Descripción: Convenciones de descubrimiento y uso de skills agénticas de Growen. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Skills agénticas de Growen

## Fuente canónica y compatibilidad

Las skills del proyecto residen únicamente en `.agents/skills/<nombre>/SKILL.md`. Esta ubicación común es descubierta por Codex, Gemini CLI y GitHub Copilot. Los archivos bajo `.agent/skills/` son adaptadores legacy preexistentes: no deben duplicar procedimientos ni usarse para skills nuevas.

Referencias oficiales: [skills de Codex](https://learn.chatgpt.com/codex/build-skills), [skills de Gemini CLI](https://codelabs.developers.google.com/gemini-cli/how-to-create-agent-skills-for-gemini-cli) y [skills de GitHub Copilot](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills).

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
