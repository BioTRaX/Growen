---
name: skill-scaffolder
description: Crea o actualiza skills agénticas de Growen con frontmatter válido, instrucciones concisas y recursos reutilizables. Usar cuando se solicite una nueva skill, adaptar una existente o validar su descubrimiento compartido por Codex, Gemini CLI y GitHub Copilot.
---

# Crear skills de Growen

1. Definir un nombre `kebab-case` menor a 64 caracteres y ejemplos que deban activar la skill.
2. Crear la fuente canónica en `.agents/skills/<nombre>/SKILL.md`.
3. Escribir primero el frontmatter con solamente `name` y `description`; `SKILL.md` está exceptuado de NG-HEADER.
4. Explicar en la descripción qué hace y cuándo se activa. Mantener el cuerpo imperativo y conciso.
5. Agregar `scripts/`, `references/` o `assets/` solo cuando sean reutilizables.
6. Mantener una sola fuente en `.agents/skills`; no crear adaptadores nuevos en `.agent/skills`. Conservar los adaptadores legacy existentes sólo mientras algún consumidor antiguo los requiera.
7. Validar frontmatter con
   `scripts/check-quality.ps1 -SkillsOnly -SkillName <nombre>` y probar un
   trigger realista. Omitir `-SkillName` para revisar todas las skills. Usar
   `-AgentOnly` cuando también corresponda ejecutar contratos, locks y escaneo
   local de secretos.

No duplicar instrucciones: `.agents/skills` es la fuente de verdad compartida por Codex, Gemini CLI y GitHub Copilot.
