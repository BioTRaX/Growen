<!-- NG-HEADER: Nombre de archivo: AGENT_ORCHESTRATION.md -->
<!-- NG-HEADER: Ubicación: docs/architecture/AGENT_ORCHESTRATION.md -->
<!-- NG-HEADER: Descripción: Auditoría y arquitectura de orquestación para agentes concurrentes sobre el mismo worktree. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Orquestación de agentes concurrentes en Growen

## 1. Alcance y método

Auditoría del entorno agéntico real del repositorio (no hipotético): directorios
de configuración, skills, manifiestos por agente, scripts de auditoría y
topología Git. Se inspeccionó el árbol de trabajo, el historial de ramas y la
documentación de gobernanza vigente (`AGENTS.md`,
[docs/development/AGENT_SKILLS.md](../development/AGENT_SKILLS.md), retrospectivas
técnicas). El foco es la concurrencia real entre agentes: condiciones de
carrera, bloqueo de archivos y comunicación de estado, no la calidad individual
de cada skill.

## 2. Inventario del entorno agéntico actual

| Directorio/archivo | Rol actual |
|---|---|
| `.agents/skills/<nombre>/SKILL.md` | Fuente canónica única de skills, compartida por Codex, Gemini CLI, GitHub Copilot y Antigravity. |
| `.agent/skills/<nombre>/SKILL.md` | Adaptadores legacy (≤12 líneas) que sólo redirigen a `.agents/skills/`. No existe adaptador legacy para `retrospectiva-tecnica-sesion` (asimetría intencional: los consumidores legacy nunca la necesitaron). |
| `.agents/skills/retrospectiva-tecnica-sesion/agents/openai.yaml` | Único manifiesto de interfaz por agente (`display_name`, `default_prompt`) en todo el árbol de skills. Ninguna otra skill tiene manifiesto equivalente; es asimétrico pero no contradice documentación vigente, por lo que no se corrige en esta auditoría. |
| `.agents/mcp_config.json` | Registro de servidores MCP vía stdio (hoy sólo `siyuan`) consumido por clientes tipo Codex/Claude Desktop. |
| `.cursor/check_sessions.py` | Único artefacto de integración específico de Cursor; sin relación con skills. |
| `.github/agents/`, `.github/workflows/` | CI (`chat-production-rollout.yml`, `quality-manual.yml`) y Dependabot; no hay definición de "agents" propia de GitHub Copilot en este repo. |
| `scripts/audit_agentic_environment.py` | Auditor determinista de gobernanza y consistencia de skills (frontmatter, adaptadores legacy, contratos obligatorios de `git-commit-push` y `retrospectiva-tecnica-sesion`). Ejecutado por `scripts/check-quality.ps1 -AgentOnly`. |
| `scripts/check-quality.ps1 -SkillsOnly [-SkillName <n>]` | Permite validar una sola skill en forma focal, mitigación reactiva ya usada para evitar que la validación global de un agente bloquee el trabajo de otro. |

No existen directorios `.claude/` ni `.gemini/` en la raíz del repositorio. Esto
es consistente con el modelo de descubrimiento vigente: la fuente única en
`.agents/skills/` reemplaza manifiestos redundantes por cliente. No se detectó
contradicción entre este hallazgo y la documentación actual; no se requiere
corrección.

### Topología Git real

`git worktree list` confirma **un único worktree físico** para todo el
repositorio (`C:/Proyectos/NiceGrow/Growen`, rama activa
`fix/production-security-hardening` al momento de esta auditoría). No hay
worktrees adicionales (`git worktree add`) en uso. El histórico de ramas remotas
muestra más de 100 ramas `codex/*` de tareas pasadas, evidencia de un patrón
establecido de una rama por tarea, pero siempre ejecutadas de a una sobre el
mismo directorio.

## 3. Hallazgos: cuellos de botella y condiciones de carrera

### 3.1 El worktree único es el riesgo estructural principal

El contrato vigente de `git-commit-push` y del diseño de branching efímero
(`docs/superpowers/specs/2026-09-05-feature-branching-efimero-cierre-sesion-design.md`)
resuelve el aislamiento **en el historial de Git**: cada sesión trabaja en una
rama `feat/*`, `fix/*`, `docs/*` o `chore/*` creada desde `dev`. Ese contrato
asume **ejecución secuencial** de sesiones. No contempla dos agentes activos al
mismo tiempo sobre el mismo checkout:

- `git switch -c <rama>` cambia el contenido de disco para **todo el
  worktree**. Si un segundo agente tiene ediciones sin confirmar en curso, un
  cambio de rama ejecutado por el primer agente puede fallar, mezclar cambios
  de ambos flujos en el mismo commit, o forzar un stash no atribuible.
- Dos agentes escribiendo el mismo archivo en paralelo (sin límite de proceso
  del sistema operativo) generan una condición de carrera clásica de última
  escritura gana (*last write wins*), indetectable hasta el `git status` o el
  gate de staging.
- El gate de `git-commit-push` audita "cambios ajenos" por inspección de diff,
  pero es una barrera de **detección tardía** (en el commit), no de
  **prevención** (en el momento de editar).

### 3.2 Incidente real ya documentado

La retrospectiva
[RETROSPECTIVE_TELEGRAM_SECRET_FORENSICS_20260815.md](../retrospectives/RETROSPECTIVE_TELEGRAM_SECRET_FORENSICS_20260815.md)
registra explícitamente: *"La validación global encontró una skill concurrente
incompleta | Los agentes comparten worktree y otro flujo dejó un scaffolding
con TODO y sin adaptador"*. La mitigación aplicada fue reactiva: se agregó el
flag `-SkillName` a `scripts/check-quality.ps1` para validar en forma focal sin
tocar el trabajo ajeno. Esto confirma que la ejecución concurrente de agentes
sobre este repositorio ya ocurrió y ya produjo fricción real, no es un
escenario hipotético.

### 3.3 Ausencia de "Agent Awareness"

No existía, antes de esta auditoría, ningún mecanismo para que un agente
declare "estoy trabajando en `X`" de forma legible por otro agente en tiempo
real. Los mecanismos existentes son:

- **Git como señal indirecta**: `git status`, nombre de rama y `git log`. Útil
  pero sólo refleja lo ya confirmado o el estado final del worktree, no la
  intención declarada ni el trabajo en curso sin commitear.
- **Auditoría estática** (`audit_agentic_environment.py`): detecta
  inconsistencias de skills ya escritas, no reserva ni negocia acceso previo.
- **Ninguna capa de bloqueo de archivos o ámbitos** (skills, migraciones,
  documentos de gobernanza) existía para prevenir edición simultánea.

### 3.4 Redundancias menores (no bloqueantes)

- `.agent/skills/` y `.agents/skills/` deben mantenerse sincronizados a mano;
  el auditor ya detecta divergencias (`legacy_diverges`), por lo que el riesgo
  está mitigado pero exige disciplina manual en cada skill nueva.
- No hay un directorio único de "estado runtime" para artefactos de
  coordinación entre agentes (locks, heartbeats); antes de esta propuesta no
  existía un lugar canónico para ese tipo de dato.

## 4. Arquitectura propuesta: Agent Awareness

### 4.1 Principios

1. El lock es **cooperativo y de ámbito lógico** (`scope`), no un lock de
   sistema operativo: no impide físicamente escribir un archivo, pero permite
   que un agente disciplinado consulte antes de empezar y evite pisar trabajo
   ajeno. Coherente con el resto de la gobernanza de Growen, que confía en que
   los agentes seguirán reglas declaradas en vez de imponer control obligatorio
   a nivel de SO.
2. El estado de coordinación vive fuera del historial versionado
   (`.agents/state/`, ignorado por Git) porque es efímero por naturaleza y
   nunca debe generar conflictos de merge ni condicionar revisiones humanas.
3. TTL obligatorio en cada lock: un agente que se cae, se cancela o pierde
   contexto no debe dejar un ámbito bloqueado indefinidamente. Un lock vencido
   se puede tomar sin intervención manual.
4. El mecanismo no reemplaza ninguna compuerta existente de
   `git-commit-push`, `retrospectiva-tecnica-sesion` ni del auditor de
   skills; es una capa adicional, previa a la edición.

### 4.2 Ámbitos (`scope`) recomendados

Un `scope` es una ruta o identificador lógico del área de trabajo, no
necesariamente un archivo único:

- Una skill completa: `.agents/skills/create-service`.
- Un documento de gobernanza: `AGENTS.md`, `docs/development/AGENT_SKILLS.md`.
- Un área de esquema: `db/models.py`, `db/migrations`.
- Un dominio funcional amplio en refactor: `services/routers/purchases.py`.

No se recomienda un lock por cada archivo tocado en una tarea normal: el costo
de coordinación debe reservarse para gobernanza compartida (skills, `AGENTS.md`,
migraciones, contratos de API) y refactors de alcance amplio, no para el flujo
diario de una sola sesión trabajando en su propia rama efímera.

### 4.3 Implementación: `scripts/agent_lock.py`

Se implementó un coordinador determinista y con pruebas
(`tests/test_agent_lock.py`, 8 casos) que materializa el mecanismo:

```powershell
# Antes de tocar una skill compartida o un área sensible
.\.venv\Scripts\python.exe scripts\agent_lock.py acquire ".agents/skills/create-service" `
  --agent codex --reason "agregar contrato de Dramatiq" --ttl-minutes 45

# Otro agente puede consultar antes de empezar
.\.venv\Scripts\python.exe scripts\agent_lock.py status ".agents/skills/create-service"

# Al terminar (o durante el cierre de sesión)
.\.venv\Scripts\python.exe scripts\agent_lock.py release ".agents/skills/create-service" --agent codex

# Ver todos los locks activos o vencidos
.\.venv\Scripts\python.exe scripts\agent_lock.py list
```

Características clave:

- **Creación atómica**: el registro se escribe primero en un archivo temporal y
  se publica con `os.replace` (rename atómico en el mismo directorio), evitando
  lecturas parciales.
- **Conflicto explícito**: `acquire` levanta `LockConflictError` con el nombre
  del agente, el motivo y el tiempo restante si el ámbito está tomado y
  vigente. Es idempotente para el mismo agente (reintentar no falla).
- **Expiración automática**: un lock vencido se puede tomar sin `--force`;
  liberar el lock de otro agente vigente exige `--force` explícito, dejando
  evidencia de que fue una decisión consciente, no un descarte accidental.
- **Estado fuera de Git**: persiste en `.agents/state/locks/*.json`, agregado a
  `.gitignore`. Nunca se versiona ni participa de un merge.

### 4.4 Integración con el ciclo de vida de sesión

- **Al iniciar** un cambio de alcance amplio o sobre gobernanza/skills, adquirir
  el lock del `scope` antes de crear la rama efímera o editar archivos.
- **Antes de un cambio de rama** (`git switch -c` o `git switch dev`), un
  agente debe considerar el estado de locks activos como señal adicional junto
  a `git status --short` para detectar trabajo concurrente no confirmado.
- **Al cerrar sesión** (`retrospectiva-tecnica-sesion`), liberar los locks
  propios como parte del cierre, igual que hoy se valida el resto del gate.
- El mecanismo es aditivo: no se modificó el contrato obligatorio de
  `git-commit-push` ni de `retrospectiva-tecnica-sesion`; ambas skills siguen
  siendo la autoridad final sobre commit, merge y push.

## 5. Evolución de estructura de directorios

```
.agents/
  skills/                # ya existente, sin cambios de fuente
  state/                 # NUEVO, ignorado por Git
    locks/*.json          # locks de coordinación (scripts/agent_lock.py)
```

No se propone mover ni duplicar `.agents/skills/`; la fuente canónica se
mantiene intacta. `.agents/state/` es el único directorio nuevo y es
exclusivamente runtime.

## 6. Plan de acción

| # | Acción | Riesgo | Estado |
|---|---|---|---|
| 1 | Crear `scripts/agent_lock.py` (acquire/release/status/list) | Bajo (local, reversible, sin efecto en Git ni en producción) | Implementado en esta sesión |
| 2 | Agregar pruebas (`tests/test_agent_lock.py`) | Bajo | Implementado en esta sesión |
| 3 | Ignorar `.agents/state/` en `.gitignore` | Bajo | Implementado en esta sesión |
| 4 | Documentar la arquitectura (este documento) y referenciarla desde `AGENTS.md` y `docs/development/AGENT_SKILLS.md` | Bajo | Implementado en esta sesión |
| 5 | Adoptar el lock en `skill-scaffolder` para el escenario que ya causó fricción real (scaffolding concurrente de skills) | Bajo | Implementado en esta sesión |
| 6 | Extender `scripts/audit_agentic_environment.py` para reportar locks vencidos olvidados (limpieza, no bloqueo) | Medio (requiere criterio sobre cuándo alertar sin generar ruido) | Propuesto, no implementado |
| 7 | Evaluar `git worktree add` por sesión para agentes que sí necesiten paralelismo físico real (no sólo lógico) | Medio-alto (cambia el flujo de trabajo diario, exige documentación y validación con el equipo) | Propuesto, requiere decisión explícita del equipo antes de implementar |
| 8 | Métrica de uso: contar activaciones/duración de locks para ajustar TTL por defecto | Bajo | Propuesto para una iteración futura |

Los ítems 1 a 5 son de riesgo bajo, reversibles y ya fueron implementados como
parte de esta auditoría, conforme al criterio de evolución agéntica de riesgo
bajo/medio de `retrospectiva-tecnica-sesion`. El ítem 7 se deja explícitamente
como propuesta abierta porque cambia el flujo operativo diario (un worktree por
agente exige rutas de trabajo, scripts de arranque y documentación adicionales)
y no debe adoptarse sin validación explícita.

## 7. Criterios de aceptación de esta auditoría

- Se contempla explícitamente la naturaleza concurrente de los agentes,
  incluyendo evidencia real (incidente documentado en 2026-08-15) y no sólo
  un escenario hipotético.
- Se entrega un mecanismo ejecutable y probado (`scripts/agent_lock.py` +
  `tests/test_agent_lock.py`), no sólo una recomendación textual.
- Se documenta la arquitectura propuesta en un documento nuevo bajo
  `docs/architecture/` y se referencia desde `AGENTS.md` y
  `docs/development/AGENT_SKILLS.md`.
- Se deja un plan de acción explícito, con ítems ya resueltos y una frontera
  clara hacia decisiones de mayor riesgo (`git worktree` por agente) que
  requieren autorización explícita antes de implementarse.
- No se alteraron los contratos existentes de `git-commit-push` ni
  `retrospectiva-tecnica-sesion`; la capa de Agent Awareness es aditiva.
