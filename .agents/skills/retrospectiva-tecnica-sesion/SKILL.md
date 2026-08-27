---
name: retrospectiva-tecnica-sesion
description: "Cierra una sesión técnica de Growen mediante una retrospectiva factual: verifica tareas y evidencia, documenta errores y soluciones, detecta desactualizaciones y propone mejoras reutilizables. Usar únicamente cuando el usuario informe explícitamente que llegó el final de la sesión o chat y solicite el cierre, la retrospectiva o las lecciones aprendidas. No activarla por completar una implementación, diagnóstico o migración si el usuario no declaró el fin de la sesión."
---

# Elaborar retrospectivas técnicas de sesión

1. Confirmar el gate de activación: el usuario debe informar explícitamente que éste es el final de la sesión o chat. Son válidas expresiones inequívocas como «terminamos la sesión», «éste es el final del chat» o «cerrá la sesión con una retrospectiva». Nombrar la skill, completar una tarea, pedir estado o solicitar documentación sin declarar el cierre no satisface el gate. Si falta esa declaración, no elaborar ni persistir la retrospectiva; continuar la tarea normal o indicar brevemente que se reservará para el cierre.
2. Leer `AGENTS.md`, el historial disponible, los outputs de herramientas, el diff actual y la documentación del dominio afectado. No afirmar acceso a mensajes u outputs ausentes; declarar cualquier límite de evidencia.
3. Delimitar la sesión analizada. Separar cambios propios, cambios preexistentes del worktree y acciones externas. No atribuir resultados sin evidencia.
4. Contrastar cada tarea supuestamente terminada contra código, pruebas, logs, estado del sistema o documentación. Clasificarla como completada, parcial, bloqueada o no verificada.
5. Registrar errores de implementación, fallos post-implementación, bloqueos ambientales y resultados inesperados. Incluir síntoma, causa raíz confirmada o hipótesis explícita, impacto, solución aplicada, evidencia posterior y riesgo residual.
6. Documentar las soluciones con precisión reutilizable: archivos o componentes afectados, decisión técnica, validación ejecutada y condición que evitaría una regresión. No copiar secretos ni outputs sensibles.
7. Revisar vigencia. Corregir documentación desactualizada cuando la evidencia actual la contradiga. Corregir lógica fuera de la tarea principal sólo cuando el desajuste esté verificado y el cambio sea seguro y autorizado; en caso contrario, registrarlo como pendiente concreto sin afirmar que quedó resuelto.
8. Evaluar mejoras agénticas en dos carriles:
   - **Prevención:** controles derivados de obstáculos, errores o retrabajo reales de la sesión.
   - **Aceleración:** skills, referencias, plantillas o scripts que harían más rápidas y consistentes futuras implementaciones similares, aunque esta sesión no haya presentado dificultades.
9. Para cada mejora candidata, indicar evidencia, frecuencia esperada, beneficio, costo de mantenimiento y opción recomendada: ampliar una skill existente, crear una skill, añadir un recurso determinista, mejorar el prompt/contexto, usar una herramienta o delegar a un agente independiente. Preferir ampliar una skill existente y no proponer agentes separados sin una frontera clara de contexto, permisos o paralelismo.
10. Basar las propuestas preventivas en problemas observados. Basar los aceleradores en pasos repetibles observados, no en herramientas hipotéticas sin caso de uso.
11. Cuando el usuario autorice cambios del entorno agéntico, **materializar al menos una mejora prioritaria** antes de cerrar: actualizar la skill aplicable, agregar una referencia determinista, incorporar una prueba o crear/ajustar un script reutilizable. Ejecutar una validación focal y registrar el archivo modificado y la evidencia. Si no existe una mejora materializable segura, dejar la razón explícita como bloqueo.
12. No crear ni modificar otras skills automáticamente sin autorización; la autorización explícita del usuario para mejorar el entorno agéntico sí habilita el cambio acotado y validado.
13. Actualizar `README.md`, `Roadmap.md` y los documentos de `docs/` realmente afectados. Crear `docs/RETROSPECTIVE_<DOMINIO>_<AAAAMMDD>.md` cuando el volumen de hallazgos justifique un informe persistente. Mantener NG-HEADER y enlaces relativos válidos.
14. Entregar el reporte con esta estructura de Growen:
   - **Contexto:** alcance, evidencia consultada y límites.
   - **Observaciones:** tareas verificadas, estado y documentación actualizada.
   - **Errores y/u outputs:** incidentes, causas, soluciones, validación y riesgos.
   - **Objetivo:** conocimiento que se busca preservar para próximas sesiones.
   - **Propuesta de código o pasos:** prevención, aceleración y prioridad de cada mejora.
   - **Criterios de aceptación:** comprobar que el reporte es factual, que los cambios están documentados, que se actualizó todo elemento desactualizado verificable y que los pendientes no se presentan como completados.

Mantener el reporte breve cuando no existan incidentes. La ausencia de errores no exime de identificar patrones exitosos que merezcan reutilización.
