---
name: git-commit-push
description: Usar cuando el usuario solicite stage, commit o push en Growen, o active el cierre de sesión autorizado.
---

# Gestionar Git con ramas efímeras

## Reglas estrictas

- Todo trabajo comienza desde el estado actual de `dev` en una rama efímera nueva: `feat/<tarea>`, `fix/<tarea>`, `docs/<tarea>` o `chore/<tarea>`.
- Está prohibido hacer un commit directo en `dev`. `dev` sólo recibe el merge final de una rama efímera validada.
- Ejecutar Git exclusivamente por terminal. Nunca usar `git push --force`, reescribir historia ni incluir cambios ajenos.
- Crear la rama es un paso normal de inicio. Stage, commit y push requieren una solicitud explícita o el trigger válido de cierre definido por `retrospectiva-tecnica-sesion`.
- Una solicitud Git fuera del cierre sólo opera sobre la rama efímera. Integrar y publicar `dev` pertenece al flujo secuencial de cierre.
- Ante una fuga o reescritura autorizada, aplicar `git-secret-forensics`.

## Inicio de trabajo

1. Ejecutar `git status --short --branch`, `git branch --show-current` y `git rev-parse HEAD`. Inventariar cambios preexistentes y su atribución.
2. Confirmar que la base es `dev` y crear la rama con `git switch -c <tipo>/<nombre-tarea>`. Si ya se está en una rama efímera exclusiva de la sesión, continuar sin crear otra.
3. Si existe un commit local directo en `dev`, detener la publicación. Reparar la topología sin reescribir una referencia remota.

## Gate previo a toda publicación

1. Revisar `git status --short`, `git diff --stat` y el diff de cada ruta.
2. Separar cambios propios, preexistentes y ajenos. Si no puede demostrarse que un archivo pertenece al alcance, no incluirlo.
3. Verificar NG-HEADER, pruebas y documentación viva. Ejecutar Python sólo con `.venv\Scripts\python.exe` o Docker.
4. Auditar nombres sensibles y líneas agregadas sin imprimir valores. Confirmar que sólo se versione `.env.example`, nunca un `.env` real.
5. Resolver `git remote get-url origin`. Si el remoto no puede verificarse como autorizado, detenerse antes del push.
6. Agregar únicamente las rutas atribuidas a la sesión y crear commits atómicos con Conventional Commits en español. Confirmar que la rama actual no sea `dev` antes de cada commit.

## Sincronización y resolución autónoma

1. Con los cambios de la sesión ya confirmados en la rama efímera, ejecutar `git fetch` y `git merge origin/dev`.
2. Si hay conflictos, listar `git diff --name-only --diff-filter=U` y buscar los marcadores `<<<<<<<`, `=======` y `>>>>>>>`.
3. Entender la intención de ambos lados y resolver reescribiendo la integración correcta. No elegir globalmente `ours` o `theirs`.
4. Resolver de forma autónoma sólo cuando contratos, contexto y pruebas permiten demostrar la intención. Si es ambigua o de riesgo muy alto, detener el flujo.
5. Comprobar que no queden rutas sin fusionar ni marcadores y repetir el gate.
6. Tras una resolución, usar `git add .` sólo si el inventario demuestra que todo el worktree pertenece al cierre; si no, agregar rutas explícitas. Crear el commit de fusión cuando Git lo requiera.

## Integración final a Dev

1. Repetir las validaciones sobre el árbol sincronizado.
2. Ejecutar `git switch dev`, verificar que `dev` no avanzó y fusionar la rama efímera sin commit directo ni reescritura.
3. Si `dev` avanzó, volver a la rama efímera, repetir fetch, merge y validación.
4. Ejecutar `git push origin dev` y comprobar que `HEAD`, `dev` y `origin/dev` coincidan.
5. No eliminar la rama efímera automáticamente; su limpieza es posterior y debe ser recuperable.

## Señales de detención

- Secreto real o remoto no verificable.
- Cambio ajeno que no puede aislarse.
- Prueba, documentación, auditoría o gate fallido.
- Conflicto cuya intención no puede demostrarse.
- Operación destructiva o de riesgo muy alto sin confirmación.

El apuro, el tamaño del cambio y una suite verde no eliminan ninguna compuerta.
