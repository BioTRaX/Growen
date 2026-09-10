---
name: skill-scaffolder
description: Usar cuando se solicite crear, adaptar o validar una skill canónica compartida por los agentes de Growen.
---

# Crear skills de Growen

**REQUIRED SUB-SKILL:** usar `superpowers:writing-skills` para RED–GREEN–REFACTOR,
escenarios de presión y calidad de redacción. Esta skill sólo añade contratos de
Growen.

1. Definir un nombre `kebab-case` menor a 64 caracteres y ejemplos que deban activar la skill.
2. Adquirir `scripts/agent_lock.py acquire .agents/skills/<nombre> --agent <nombre-agente> --reason scaffold` antes de crear archivos, dado que otro agente puede estar escribiendo la misma skill en paralelo sobre el worktree compartido. Liberarlo con `release` al terminar.
3. Crear la fuente canónica en `.agents/skills/<nombre>/SKILL.md`.
4. Escribir primero el frontmatter con solamente `name` y `description`; `SKILL.md` está exceptuado de NG-HEADER.
5. Limitar la descripción a condiciones de activación, en tercera persona, y mantener el cuerpo imperativo y conciso.
6. Agregar `scripts/`, `references/` o `assets/` solo cuando sean reutilizables.
7. Mantener una sola fuente en `.agents/skills`; no crear adaptadores nuevos en `.agent/skills`. Conservar los adaptadores legacy existentes sólo mientras algún consumidor antiguo los requiera.
8. Validar frontmatter con
   `scripts/check-quality.ps1 -SkillsOnly -SkillName <nombre>` y probar un
   trigger realista. Omitir `-SkillName` para revisar todas las skills. Usar
   `-AgentOnly` cuando también corresponda ejecutar contratos, locks y escaneo
   local de secretos.

No copiar el procedimiento de `writing-skills`: `.agents/skills` define únicamente la fuente, compatibilidad y validadores propios de Growen.
