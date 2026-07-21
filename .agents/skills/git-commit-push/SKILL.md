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
5. Antes de publicar, auditar nombres sensibles y patrones de secretos en los archivos candidatos y en las líneas agregadas. Mostrar solo archivo, línea, variable y categoría; nunca imprimir el valor coincidente.
6. Clasificar falsos positivos de archivos lock por la propiedad contenedora (`integrity`/`resolved`) y confirmar que solo se versionen `.env.example`, no `.env` reales.
7. Presentar el alcance exacto y agregar archivos mediante `git add -- <archivo...>`.
8. Crear commits atómicos con Conventional Commits y mensajes en español.
9. Sincronizar sin operaciones destructivas. Ante conflictos, detenerse e informar.
10. Resolver y comunicar la URL de `origin`. Si el destino externo no puede verificarse como confiable o privado, informar URL y cantidad de archivos y obtener aprobación explícita antes del push.
11. Hacer push de la rama actual y verificar que `HEAD` coincida con la referencia remota. Comunicar rama, commits, validaciones, auditoría de secretos y archivos excluidos.

Si la plataforma bloquea un push por riesgo de exfiltración, no intentar rutas alternativas: conservar los commits locales, pedir la aprobación explícita requerida y reanudar solo cuando llegue.

Actualizar `Roadmap.md`, `README.md` y documentos de dominio cuando cambien comportamientos, contratos, modelos, infraestructura o requisitos de entorno.
