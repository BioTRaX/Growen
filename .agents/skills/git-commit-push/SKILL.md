---
name: git-commit-push
description: Usar cuando el usuario solicite publicar cambios de Growen o autorice automatizar la publicación de una entrega en la rama exacta dev.
---

# Publicar cambios Git

## Autorización

- No activar por finalizar una tarea ni por detectar archivos modificados.
- Activar stage, commit, sincronización o push sólo mediante autorización explícita del usuario.
- La autorización puede cubrir una publicación puntual o la automatización de una entrega o sesión en la rama exacta `dev`; debe quedar expresada por el usuario y no se infiere de la rama, del estado de las pruebas ni de autorizaciones antiguas.
- En `dev`, una automatización ya autorizada puede completar commit y push sin pedir una segunda confirmación, pero únicamente después de aprobar todo el gate de seguridad.
- Fuera de la rama exacta `dev`, cada publicación requiere una solicitud explícita para ese alcance. Estar en una rama que luego se integrará a `dev` no concede la excepción.
- Nunca usar `git add .`, `git push --force` ni incluir cambios ajenos al objetivo.
- Si la solicitud incluye una fuga confirmada, reescritura de historia,
  eliminación coordinada de ramas o `git-filter-repo`, aplicar primero
  `git-secret-forensics`. El flujo normal de publicación no autoriza esas
  operaciones destructivas.

## Flujo obligatorio

1. Confirmar la autorización y clasificarla como puntual o automatizada para la entrega o sesión actual en `dev`. Sin autorización aplicable, detenerse antes de cualquier mutación Git.
2. Confirmar la rama exacta con `git branch --show-current`. La automatización sólo continúa si el resultado es `dev`.
3. Revisar `git status --short`, `git diff --stat` y el diff de cada archivo candidato.
4. Identificar cambios preexistentes o ajenos y excluirlos del staging.
5. Verificar NG-HEADER, tests y documentación viva según `AGENTS.md`.
6. Ejecutar el quality gate aplicable con `scripts/check-quality.ps1` o comandos focalizados. Todo Python o pytest debe ejecutarse con `.venv\Scripts\python.exe` o Docker.
7. Antes de publicar, auditar nombres sensibles y patrones de secretos en los archivos candidatos y en las líneas agregadas. Mostrar sólo archivo, línea, variable y categoría; nunca imprimir el valor coincidente.
8. Clasificar falsos positivos de archivos lock por la propiedad contenedora (`integrity`/`resolved`) y confirmar que sólo se versionen `.env.example`, no `.env` reales.
9. Resolver y comunicar la URL de `origin`. Si el destino externo no puede verificarse como confiable o privado, informar URL y cantidad de archivos y obtener aprobación explícita antes del push.
10. Presentar el alcance exacto y agregar archivos mediante `git add -- <archivo...>`.
11. Crear commits atómicos con Conventional Commits y mensajes en español.
12. Sincronizar sin operaciones destructivas. Ante conflictos, detenerse e informar.
13. Hacer push de la rama actual y verificar que `HEAD` coincida con la referencia remota. Comunicar rama, commits, validaciones, auditoría de secretos y archivos excluidos.

## Decisión rápida

| Estado observable | Acción |
|---|---|
| `dev` + automatización autorizada para el alcance actual + gate completo aprobado | Puede completar commit y push sin otra confirmación |
| `dev` sin autorización explícita aplicable | Detenerse y solicitar autorización |
| Cualquier otra rama | Exigir una solicitud explícita para esa publicación |
| Secreto real o sospechoso, alcance no aislable, prueba o documentación fallida, remoto dudoso o conflicto | Detenerse antes de stage, commit o push |

## Racionalizaciones que no conceden autorización

| Atajo | Regla |
|---|---|
| «Estamos en `dev`, así que ya hay permiso» | La rama habilita la modalidad, no concede autorización |
| «Las pruebas pasaron; el commit es seguro» | Las pruebas no sustituyen la auditoría de secretos, alcance, documentación y remoto |
| «Audito después del commit» | El gate completo ocurre antes de la primera mutación Git |
| «Esta rama terminará en `dev`» | Sólo la rama cuyo nombre exacto es `dev` admite automatización autorizada |
| «Es un cambio pequeño» | El tamaño no elimina ningún control |

## Señales de detención

- Falta una autorización explícita aplicable al alcance actual.
- La automatización se intenta fuera de `dev`.
- Aparece un secreto real o no se puede clasificar una coincidencia con seguridad.
- Hay archivos ajenos que no pueden excluirse con staging selectivo.
- Fallan pruebas, documentación, NG-HEADER, sincronización o verificación del remoto.

Todas estas señales obligan a detener el flujo antes de mutar Git y comunicar el bloqueo sin exponer valores sensibles.

Si la plataforma bloquea un push por riesgo de exfiltración, no intentar rutas alternativas: conservar los commits locales, pedir la aprobación explícita requerida y reanudar solo cuando llegue.

Actualizar `Roadmap.md`, `README.md` y documentos de dominio cuando cambien comportamientos, contratos, modelos, infraestructura o requisitos de entorno.
