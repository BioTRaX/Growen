<!-- NG-HEADER: Nombre de archivo: README.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/README.md -->
<!-- NG-HEADER: Descripción: Compatibilidad local de Superpowers con Growen y precedencia de reglas -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Superpowers y Growen

## Objetivo

Integrar la metodología de Superpowers sin permitir que sus reglas genéricas desplacen las restricciones específicas del repositorio Growen.

## Precedencia

La precedencia local es la siguiente:

1. `AGENTS.md` y las skills canónicas de Growen bajo `.agents/skills/` tienen prioridad.
2. Las reglas de seguridad, idioma, documentación y entorno de Growen prevalecen sobre cualquier patrón externo.
3. Las skills de Superpowers solo sirven como complemento metodológico, no como sustituto de la política local.

## Reglas que prevalecen en Growen

- Los commit, push, merge y publicación automática requieren autorización explícita del usuario.
- En la rama exacta `dev`, el usuario puede autorizar la automatización para una entrega o sesión. Esa autorización no se infiere de la rama y no elimina el gate completo de secretos, alcance, pruebas, documentación y remotos.
- Fuera de `dev`, cada publicación requiere una solicitud explícita para ese alcance.
- Python y pytest deben ejecutarse exclusivamente con el venv de Growen (`.venv\Scripts\python.exe`) o con Docker. Quedan prohibidos `python`, `pip`, `poetry` y `pytest` del sistema.
- Todo Markdown creado bajo `docs/superpowers/` debe incluir NG-HEADER para permitir indexación y mantenimiento futuro.
- Las respuestas, documentación, commits y PRs generados mediante Superpowers deben estar en español.

## Solapamientos relevantes

| Skill de Superpowers | Relación con Growen | Tratamiento |
|---|---|---|
| `writing-skills` | Complementaria con `skill-scaffolder` | Usar la metodología TDD sin reemplazar la fuente canónica de Growen |
| `systematic-debugging` | Complementaria con `diagnose-local-services` | Aplicar diagnóstico general, pero seguir el contexto técnico local |
| `finishing-a-development-branch` | Parcialmente conflictiva | Delegar publicación a `git-commit-push` y respetar el gate de autorización |
| `verification-before-completion` | Complementaria con `retrospectiva-tecnica-sesion` | Mantener evidencia y validación, pero sin activar cierre sin confirmación explícita |
| `using-git-worktrees` | Útil con adaptación | Respetar el entorno de Growen y no usar `pip` o `pytest` del sistema |
| `test-driven-development` | Complementaria con el testing local | Mantener TDD, pero ejecutar pytest sólo mediante el venv de Growen o Docker |

## Descubrimiento sin forks locales

Las 14 skills de Superpowers permanecen en la instalación global compartida del usuario y se actualizan desde su repositorio original. Codex, Gemini CLI, GitHub Copilot y Antigravity pueden descubrir el directorio compartido `~/.agents/skills`; `.agent/skills/` se conserva sólo para adaptadores legacy del proyecto. No se copian ni modifican las skills externas dentro de Growen.

## Documentación viva

Toda documentación incluida bajo `docs/superpowers/` debe mantenerse sincronizada con:

- `AGENTS.md`
- `docs/AGENT_SKILLS.md`
- `Roadmap.md`
- `README.md`

## Conclusión

Superpowers puede aportar disciplina de trabajo y flujo de validación, pero Growen conserva la autoridad final sobre seguridad, entorno local, documentación, idioma y publicación.
