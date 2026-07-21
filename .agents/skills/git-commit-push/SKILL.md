---
name: git-commit-push
description: Publica cambios de Growen mediante revisión, documentación, pruebas, staging selectivo, commit y push. Usar exclusivamente cuando el usuario solicite de forma explícita preparar, confirmar o subir cambios al repositorio.
---

# Publicar cambios Git

## Autorización

- No activar por finalizar una tarea ni por detectar archivos modificados.
- Considerar autorizadas stage, commit, sincronización y push solo cuando el usuario pida explícitamente subir, pushear, commitear o actualizar el repositorio remoto.
- Nunca usar `git add .`, `git push --force` ni incluir cambios ajenos al objetivo.

## Flujo obligatorio

1. Revisar `git status --short`, `git diff --stat` y el diff de cada archivo candidato.
2. Identificar cambios preexistentes o ajenos y excluirlos del staging.
3. Verificar NG-HEADER, tests y documentación viva según `AGENTS.md`.
4. Ejecutar el quality gate aplicable con `scripts/check-quality.ps1` o comandos focalizados.
5. Presentar el alcance exacto y agregar archivos mediante `git add -- <archivo...>`.
6. Crear commits atómicos con Conventional Commits y mensajes en español.
7. Sincronizar sin operaciones destructivas. Ante conflictos, detenerse e informar.
8. Hacer push de la rama actual y comunicar rama, commit, validaciones y archivos excluidos.

Actualizar `Roadmap.md`, `README.md` y documentos de dominio cuando cambien comportamientos, contratos, modelos, infraestructura o requisitos de entorno.
