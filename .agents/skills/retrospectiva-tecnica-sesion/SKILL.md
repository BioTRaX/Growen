---
name: retrospectiva-tecnica-sesion
description: "Usar únicamente cuando el usuario escriba Cerrar sesión o Cerremos sesión y solicite finalizar el trabajo técnico de Growen."
---

# Cerrar una sesión técnica

## Activación

Los únicos triggers directos son `Cerrar sesión` y `Cerremos sesión`, sin distinguir mayúsculas ni puntuación final. Frases como `Terminamos la sesión`, `final del chat`, nombrar la skill, pedir una retrospectiva o completar una tarea no activa este flujo.

Si aparece un trigger válido y existe trabajo pendiente ambiguo, solicitar confirmación breve sobre si debe completarse o descartarse antes de cerrar. La respuesta despeja la ambigüedad; no reemplaza el trigger.

**REQUIRED BACKGROUND:** usar `superpowers:verification-before-completion` para contrastar afirmaciones. No cargar otras skills de cierre de Superpowers: el gate Git de Growen es canónico.

## Flujo secuencial obligatorio

### 1. Análisis retrospectivo

Leer historial disponible, outputs, diff y documentos afectados. Delimitar la sesión, separar cambios propios y preexistentes, y clasificar tareas como completadas, parciales, bloqueadas o no verificadas. Documentar dificultades, errores, causa confirmada o hipótesis, implementación, solución, evidencia y riesgo residual sin copiar secretos.

### 2. Evolución agéntica

Proponer una evolución del entorno agéntico basada en trabajo observado. Evitar duplicar Superpowers: ampliar una skill canónica sólo para reglas o contexto propios de Growen; usar scripts para controles mecánicos. Materializar al menos una mejora prioritaria segura y validarla. Si no existe, registrar el motivo.

### 3. Compuerta de riesgo

- **Bajo:** documentación o validaciones locales reversibles.
- **Medio:** cambios acotados y reversibles en skills, scripts o contratos con pruebas.
- **Riesgo muy alto:** reescritura de historia, force-push, eliminación amplia, secretos, mutaciones externas irreversibles, migraciones destructivas o un conflicto cuya intención no pueda demostrarse.

Implementar las mejoras de riesgo bajo o medio. Ante riesgo muy alto, informar únicamente el estado y la propuesta, preguntar si se avanza y detener el flujo hasta recibir respuesta explícita.

### 4. Actualización de documentación

Actualizar `README.md`, `Roadmap.md`, documentación de dominio y todo contenido verificablemente desactualizado encontrado. Mantener NG-HEADER y diferenciar pendientes de resultados comprobados.

### 5. Flujo de auto-merge

Aplicar `git-commit-push` y su gate completo:

1. Confirmar la rama efímera actual, agregar sólo los cambios atribuidos a la sesión y crear los commits atómicos de trabajo.
2. Ejecutar `git fetch` y `git merge origin/dev`.
3. Ante conflictos, usar `git diff --name-only --diff-filter=U`, localizar `<<<<<<<`, `=======` y `>>>>>>>`, entender ambas intenciones y resolver reescribiendo correctamente.
4. Validar la resolución. Si no quedan conflictos, ejecutar `git add .` sólo después de confirmar que todo el worktree pertenece al cierre y crear el commit de fusión cuando corresponda.
5. Repetir pruebas, documentación, secretos y alcance sobre el árbol fusionado.
6. Ejecutar `git switch dev`, fusionar la rama efímera y ejecutar `git push origin dev`.
7. Verificar que `HEAD`, `dev` y `origin/dev` coincidan. Si `dev` avanzó durante el proceso, volver a la rama efímera y repetir sincronización y validación.

### 6. Output final

Después de un cierre exitoso, imprimir exclusivamente este checklist con su estado comprobado, sin introducción, explicación ni epílogo:

- [x] Análisis retrospectivo completado
- [x] Evolución agéntica implementada/propuesta
- [x] Actualización de documentación
- [x] Merge a Dev
- [x] Final de sesión

Si el flujo se detiene por riesgo muy alto, no imprimir el checklist final.
