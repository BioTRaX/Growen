---
name: skill-scaffolder
description: Usar cuando se solicite crear, adaptar o validar una skill canónica compartida por los agentes de Growen.
---

# Crear skills de Growen

**REQUIRED SUB-SKILL:** usar `superpowers:writing-skills` para RED–GREEN–REFACTOR,
escenarios de presión y calidad de redacción. Esta skill sólo añade contratos de
Growen.

1. Definir un nombre `kebab-case` menor a 64 caracteres y ejemplos que deban activar la skill.
2. Crear la fuente canónica en `.agents/skills/<nombre>/SKILL.md`.
3. Escribir primero el frontmatter con solamente `name` y `description`; `SKILL.md` está exceptuado de NG-HEADER.
4. Limitar la descripción a condiciones de activación, en tercera persona, y mantener el cuerpo imperativo y conciso.
5. Agregar `scripts/`, `references/` o `assets/` solo cuando sean reutilizables.
6. Mantener una sola fuente en `.agents/skills`; no crear adaptadores nuevos en `.agent/skills`. Conservar los adaptadores legacy existentes sólo mientras algún consumidor antiguo los requiera.
7. Validar frontmatter con
   `scripts/check-quality.ps1 -SkillsOnly -SkillName <nombre>` y probar un
   trigger realista. Omitir `-SkillName` para revisar todas las skills. Usar
   `-AgentOnly` cuando también corresponda ejecutar contratos, locks y escaneo
   local de secretos.

No copiar el procedimiento de `writing-skills`: `.agents/skills` define únicamente la fuente, compatibilidad y validadores propios de Growen.
