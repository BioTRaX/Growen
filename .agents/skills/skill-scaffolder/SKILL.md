---
name: skill-scaffolder
description: Crea o actualiza skills de Codex dentro de Growen con frontmatter válido, instrucciones concisas y recursos reutilizables. Usar cuando se solicite una nueva skill, adaptar una existente o validar su descubrimiento.
---

# Crear skills de Growen

1. Definir un nombre `kebab-case` menor a 64 caracteres y ejemplos que deban activar la skill.
2. Crear la fuente canónica en `.agents/skills/<nombre>/SKILL.md`.
3. Escribir primero el frontmatter con solamente `name` y `description`; `SKILL.md` está exceptuado de NG-HEADER.
4. Explicar en la descripción qué hace y cuándo se activa. Mantener el cuerpo imperativo y conciso.
5. Agregar `scripts/`, `references/` o `assets/` solo cuando sean reutilizables.
6. Para compatibilidad con `.agent/skills`, crear un adaptador corto que apunte a la fuente canónica.
7. Validar con `scripts/check-quality.ps1 -AgentOnly` y probar un trigger realista.

No duplicar instrucciones extensas: la fuente de verdad es `.agents/skills`.
