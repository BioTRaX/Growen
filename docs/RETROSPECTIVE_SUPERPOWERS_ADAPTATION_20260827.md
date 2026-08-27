<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_SUPERPOWERS_ADAPTATION_20260827.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_SUPERPOWERS_ADAPTATION_20260827.md -->
<!-- NG-HEADER: Descripción: Retrospectiva de instalación, descubrimiento y adaptación de Superpowers a Growen. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva — adaptación de Superpowers a Growen

## Contexto

La sesión evaluó las 14 skills de Superpowers instaladas globalmente, sus solapamientos con las skills canónicas de Growen y su descubrimiento por Codex, Gemini CLI, GitHub Copilot y Antigravity. La evidencia consultada incluye el junction local, los 14 `SKILL.md`, `AGENTS.md`, la documentación agéntica, el diff, los quality gates y cinco pruebas de presión con agentes en contexto limpio.

El worktree ya contenía numerosos cambios de Enrich, Chat, Vue, workers y tests que no pertenecen a esta adaptación. No se modificaron, publicaron ni atribuyeron a este trabajo. Tampoco se ejecutaron stage, commit o push.

## Observaciones

- **Completado:** las 14 skills están expuestas mediante `~/.agents/skills/superpowers`, con frontmatter válido en los 14 manifiestos y sin forks dentro de Growen.
- **Completado:** se definió la precedencia de Growen sobre Superpowers para seguridad, idioma, documentación, Python y Git.
- **Completado:** `git-commit-push` exige autorización explícita; sólo `dev` permite automatización ya autorizada y siempre después del gate completo.
- **Completado:** Python y pytest quedaron restringidos al venv de Growen o Docker en la documentación aplicable.
- **Completado:** se documentaron los solapamientos con `skill-scaffolder`, `diagnose-local-services`, testing, Git y retrospectiva.
- **Parcial:** la estructura coincide con las rutas oficiales de Copilot y Antigravity, pero no se pudo comprobar la enumeración dentro de esos clientes. VS Code no tiene instalada la extensión GitHub Copilot y el comando `agy` no está disponible.

## Errores y/u outputs

1. **Interrupción de la adaptación.** El procesamiento fue detenido por el usuario y luego reanudado. La revisión del diff permitió continuar sin rehacer ni sobrescribir cambios preexistentes.
2. **Fallo ambiental al consultar extensiones.** `code --list-extensions` intentó escribir en el perfil de VS Code y recibió `EPERM` dentro del sandbox. La consulta autorizada fuera del sandbox funcionó y confirmó que Copilot no está instalado.
3. **Riesgo metodológico detectado.** Las instrucciones genéricas de Superpowers podían interpretar `dev` como autorización implícita o usar pytest del sistema. Se corrigió mediante precedencia explícita, tabla de decisión y señales de detención.

Validación posterior:

- quality gate focal de `git-commit-push`: aprobado;
- quality gate de todas las skills canónicas: aprobado;
- manifiestos Superpowers: `14/14` válidos;
- Markdown bajo `docs/superpowers/`: `1/1` con NG-HEADER;
- pruebas de presión: `5/5` decisiones esperadas;
- `git diff --check`: sin errores de whitespace.

Riesgo residual: la instalación global y su junction no forman parte del repositorio. Una máquina nueva requiere repetir la instalación y validar el listado desde cada cliente disponible.

## Objetivo

Preservar una integración actualizable desde el repositorio original de Superpowers, sin duplicar skills ni debilitar los controles particulares de Growen.

## Propuesta de código o pasos

### Prevención — prioridad media

Agregar, cuando se necesite repetir esta validación, un script determinista y opcional que compruebe ruta global, cantidad de skills, frontmatter y junction sin depender de que Copilot o Antigravity estén instalados. Evidencia: la sesión repitió estas verificaciones manualmente. Beneficio alto tras upgrades o cambios de equipo; costo de mantenimiento bajo. Recomendación: recurso bajo `scripts/`, no una skill nueva.

### Aceleración — prioridad baja

Mantener una checklist de smoke por cliente: reiniciar, listar skills y activar una skill conocida. Evidencia: la validación estructural no prueba la enumeración en UI. Frecuencia esperada: instalaciones nuevas y actualizaciones mayores. Recomendación: ampliar `docs/superpowers/README.md` cuando se disponga de ambos clientes, sin crear adaptadores adicionales.

## Criterios de aceptación

- [x] El reporte distingue cambios de la sesión y cambios preexistentes.
- [x] Los estados completado, parcial y no verificado están respaldados por evidencia.
- [x] Se documentaron outputs, causas, soluciones y riesgo residual sin exponer secretos.
- [x] La documentación viva refleja las reglas vigentes de Superpowers en Growen.
- [x] Se documentaron los cambios y se actualizaron las referencias desactualizadas verificables.
- [ ] Ejecutar el smoke dentro de Copilot y Antigravity cuando estén instalados y disponibles.
