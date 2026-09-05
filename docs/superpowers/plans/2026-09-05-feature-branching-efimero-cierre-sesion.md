<!-- NG-HEADER: Nombre de archivo: 2026-09-05-feature-branching-efimero-cierre-sesion.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/plans/2026-09-05-feature-branching-efimero-cierre-sesion.md -->
<!-- NG-HEADER: Descripción: Plan de implementación del branching efímero y cierre secuencial de sesión. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Plan de implementación de Feature Branching Efímero

> **Para agentes ejecutores:** SUB-SKILL REQUERIDA: usar `superpowers:subagent-driven-development` o `superpowers:executing-plans` para ejecutar este plan tarea por tarea. Los pasos usan casillas para seguimiento.

**Objetivo:** implantar ramas efímeras obligatorias, cierre secuencial con
autoevolución y auto-merge, y una composición sin duplicaciones con Superpowers.

**Arquitectura:** `AGENTS.md` define el contrato global; las skills canónicas
implementan los gates Git y de cierre; el auditor y las pruebas impiden
regresiones; la documentación explica el flujo operativo y la frontera con
Superpowers. Los adaptadores legacy sólo redirigen.

**Tecnologías:** Markdown, YAML, Python 3.14.6, pytest, PowerShell y Git CLI.

**Especificación:** `docs/superpowers/specs/2026-09-05-feature-branching-efimero-cierre-sesion-design.md`

## Restricciones globales

- Todo Python o pytest se ejecuta con `.venv\Scripts\python.exe` o Docker.
- Toda operación Git se ejecuta por terminal.
- No se hacen commits directos a `dev`.
- No se ejecutan commit, merge final ni push sin el trigger de cierre aplicable.
- `.agents/skills/` es la fuente canónica; `.agent/skills/` sólo contiene adaptadores legacy existentes.
- No se debilitan los gates de secretos, alcance, pruebas, documentación, remoto ni riesgo.

---

### Tarea 1: Contratos ejecutables en estado RED

**Archivos:**

- Modificar: `tests/test_retrospective_skill.py`
- Modificar: `tests/test_audit_agentic_environment.py`

**Interfaces:**

- Consume: texto de las skills y `audit_agentic_environment(root)`.
- Produce: pruebas sobre triggers exactos, prohibición de commits directos,
  rama efímera, secuencia de cierre, compuerta de riesgo y no duplicación.

- [x] Añadir pruebas que fallen con las directivas actuales.
- [x] Ejecutar
  `.\.venv\Scripts\python.exe -m pytest tests/test_retrospective_skill.py tests/test_audit_agentic_environment.py -q`.
- [x] Confirmar que los fallos corresponden a contratos ausentes y no a errores de entorno.

### Tarea 2: Gate Git de ramas efímeras

**Archivos:**

- Modificar: `.agents/skills/git-commit-push/SKILL.md`
- Modificar: `.agent/skills/git-commit-push/SKILL.md`

**Interfaces:**

- Consume: autorización explícita, rama actual, inventario del worktree y remoto.
- Produce: inicio en rama efímera y publicación exclusiva mediante merge a `dev` durante el cierre.

- [x] Reescribir la skill canónica con prohibición directa sobre `dev`, naming
  efímero, gate de pertenencia y resolución autónoma verificable.
- [x] Mantener el adaptador legacy como redirección breve, sin copiar el flujo.
- [x] Ejecutar las pruebas focalizadas y confirmar el avance hacia GREEN.

### Tarea 3: Cierre secuencial y autoevolución

**Archivos:**

- Modificar: `.agents/skills/retrospectiva-tecnica-sesion/SKILL.md`
- Modificar: `.agents/skills/retrospectiva-tecnica-sesion/agents/openai.yaml`

**Interfaces:**

- Consume: triggers `Cerrar sesión` o `Cerremos sesión`, historial, diff y evidencia.
- Produce: retrospectiva, evolución según riesgo, documentación, sincronización,
  resolución, merge a `dev`, push y checklist final exclusivo.

- [x] Ajustar la descripción para que sólo declare condiciones de activación.
- [x] Implementar el orden obligatorio y la pausa ante riesgo muy alto.
- [x] Incorporar confirmación breve si el trigger coincide con trabajo pendiente ambiguo.
- [x] Ejecutar las pruebas focalizadas y confirmar GREEN.

### Tarea 4: Auditoría de composición con Superpowers

**Archivos:**

- Modificar: `scripts/audit_agentic_environment.py`
- Modificar: `tests/test_audit_agentic_environment.py`
- Modificar cuando exista solapamiento: `.agents/skills/*/SKILL.md`

**Interfaces:**

- Consume: inventario de skills canónicas y referencias declaradas a Superpowers.
- Produce: hallazgos deterministas sobre duplicación de adaptadores y contratos esenciales ausentes.

- [x] Comparar las ocho skills locales contra las catorce de Superpowers por
  trigger, responsabilidad y procedimiento.
- [x] Mantener conocimiento exclusivo de Growen y reemplazar metodología general
  repetida por referencias `REQUIRED SUB-SKILL` o `REQUIRED BACKGROUND`.
- [x] Extender el auditor sólo con reglas mecánicas estables; dejar el juicio de
  solapamiento en la matriz documental.
- [x] Ejecutar pruebas focalizadas y `scripts/check-quality.ps1 -SkillsOnly`.

### Tarea 5: Gobernanza y documentación viva

**Archivos:**

- Modificar: `AGENTS.md`
- Modificar: `docs/AGENT_SKILLS.md`
- Modificar: `docs/DEVELOPMENT_WORKFLOW.md`
- Modificar: `CONTRIBUTING.md`
- Modificar: `README.md`
- Modificar: `Roadmap.md`

**Interfaces:**

- Consume: contrato probado de las tareas 1 a 4.
- Produce: una descripción coherente del inicio, cierre, riesgo, auto-merge y frontera con Superpowers.

- [x] Reemplazar las reglas que permiten trabajo directo en `dev`.
- [x] Retirar `develop` del flujo vigente y documentar ramas efímeras.
- [x] Añadir la matriz Growen/Superpowers y recomendaciones de carga mínima.
- [x] Preservar cambios preexistentes en los mismos documentos.
- [x] Verificar enlaces, encabezados y consistencia terminológica.

### Tarea 6: Verificación integrada

**Archivos:**

- Verificar todos los archivos modificados por este plan.

**Interfaces:**

- Consume: implementación completa.
- Produce: evidencia reproducible sin commit, merge final ni push.

- [x] Ejecutar las pruebas focalizadas con el venv.
- [x] Ejecutar `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-quality.ps1 -SkillsOnly`.
- [x] Ejecutar `git diff --check` y revisar el diff por rutas explícitas.
- [x] Buscar referencias activas a `develop`, commits directos a `dev`, triggers antiguos y marcadores de conflicto.
- [x] Documentar resultados, cambios y cualquier contenido desactualizado corregido.
