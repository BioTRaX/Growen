<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_TELEGRAM_SECRET_FORENSICS_20260815.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_TELEGRAM_SECRET_FORENSICS_20260815.md -->
<!-- NG-HEADER: Descripción: Retrospectiva técnica de la auditoría y reescritura histórica del token Telegram -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva de auditoría y saneamiento Git — 2026-08-15

## 1. Contexto

La sesión investigó el envío masivo de spam desde el bot Telegram mientras la
infraestructura Growen estaba apagada. GitHub Secret Scanning había identificado
un token operativo como fuga pública en `workers/telegram_polling.py`. El
objetivo posterior fue preservar los cambios válidos de desarrollo, sanear
`main` y `dev`, eliminar ramas Dependabot afectadas y documentar la intervención.

## 2. Observaciones

### Tareas completadas

- Se escanearon el árbol actual, archivos ignorados, índice, 631 commits, 137
  referencias, reflogs, stashes y 433 blobs no alcanzables sin imprimir
  credenciales.
- Se confirmó el commit introductor
  `b4bf96907f05cc772f265400f7d8d60ba3dcf3ac`, el archivo afectado y el blob
  histórico `8df79f648a97e2c0cf546fd3128758c981f2944c`.
- Se verificó que `.env` está ignorado y no rastreado. Los `.env` versionados
  son ejemplos o configuración de desarrollo explícita.
- Se revisaron dependencias y scripts. Python y Vue no reportaron
  vulnerabilidades; React conservó el hallazgo alto asociado a
  `react-router`/`react-router-dom` 7.18.1.
- Se preservó el trabajo válido de `dev` en tres commits reescritos:
  `6c304c1`, `bdc2992` y `5eaf36a`; 105 pruebas backend, la prueba de migración,
  34 pruebas Vue, typecheck y builds focales finalizaron correctamente.
- Se reescribió el historial con `git-filter-repo`, preservando exactamente el
  árbol final de `dev` y limitando en `main` el cambio al literal sensible.
- Se publicaron `main` en `1e117589d8547e07d12d30c94ddc0513a6452695`
  y la base saneada de `dev` en
  `5eaf36a42771c0a3ed7104b60a08a9f488fd75af` mediante leases explícitos.
- Se eliminaron cuatro ramas Dependabot afectadas. La documentación final quedó
  publicada en `dev` como `70c2332b9bb3733c9e6feac7ef391181a70d912f`.
- Se eliminó el espejo temporal que contenía objetos históricos sensibles.

## 3. Errores y/u outputs

| Incidente | Causa técnica | Solución aplicada | Estado |
|---|---|---|---|
| La preparación inicial pareció una clonación innecesaria o una copia del `.venv` | No se explicó antes de actuar que el espejo aislado era para reescribir y validar historia sin tocar el worktree | Se pausó la operación y se aclaró que el tooling era temporal, fuera del repositorio, y que no se clonaba el `.venv` | Resuelto; faltaba comunicación previa |
| El worktree contenía 95 archivos válidos sin confirmar | Reescribir historia con cambios locales habría mezclado preservación funcional y erradicación | Se auditaron, probaron y confirmaron primero en `dev` mediante staging selectivo | Resuelto |
| `git-filter-repo` no estaba instalado | La herramienta no formaba parte del entorno local | Se instaló exclusivamente en un directorio temporal usando el Python 3.14.6 del proyecto | Resuelto; no se modificaron dependencias del proyecto |
| `scripts/debug_migrations.py` agotó 60 segundos | El diagnóstico esperaba conexión a PostgreSQL; no fue un error de Alembic | Se verificó de forma independiente un único head y se registró el smoke PostgreSQL como opt-in | Bloqueo ambiental, no funcional |
| El sandbox rechazó `git add` con `index.lock: Permission denied` | `.git` era legible pero no escribible dentro del sandbox | Se repitió únicamente la escritura del índice con autorización elevada | Resuelto |
| El primer escaneo remoto todavía alcanzó el blob antiguo | GitHub conserva referencias internas `refs/pull/*` aunque se reescriban heads y tags | Se enumeraron diez referencias y se documentó la necesidad de una purga por GitHub Support | Pendiente externo |
| El espejo de verificación volvió a descargar objetos sensibles | Era necesario comprobar referencias internas desde un clon independiente | Se validó la ruta absoluta y se eliminó recursivamente el temporal al finalizar | Resuelto |
| La documentación afirmó posteriormente que la clave OpenAI local había sido eliminada | Contradicción entre `docs/SECURITY.md` y el informe forense | El 2026-08-15 se verificó sin mostrar valores que continúa una coincidencia real en `.env`, ignorada y no rastreada; la política fue corregida | Rotación pendiente |
| El validador recomendado para skills también escaneaba `.env` | `-AgentOnly` incluye contratos, locks y secretos además de frontmatter/adaptadores | Se agregó `-SkillsOnly` y `skill-scaffolder` pasó a usar ese modo sin debilitar `-AgentOnly` | Resuelto |
| La validación global encontró una skill concurrente incompleta | Los agentes comparten worktree y otro flujo dejó un scaffolding con TODO y sin adaptador | Se agregó `-SkillName` para validar focalmente sin modificar ni aprobar trabajo ajeno; la regex también acepta LF y CRLF | Resuelto para esta entrega; borrador ajeno pendiente |

### Deuda residual comprobada

- Diez referencias `refs/pull/*` continuaban alcanzando el objeto antiguo en la
  última verificación remota de la sesión. No existe evidencia registrada de
  que GitHub Support haya completado la purga.
- Los clones y reflogs previos a la reescritura pueden conservar objetos
  sensibles y deben retirarse en lugar de reutilizarse.
- `.env` contiene al 2026-08-15 una clave OpenAI con formato real. Está ignorada
  y no se halló en Git, pero debe rotarse antes de configurar un reemplazo.
- `frontend/package-lock.json` todavía resuelve `react-router` y
  `react-router-dom` 7.18.1; la remediación de la alerta registrada sigue
  pendiente de un cambio de dependencias y nueva auditoría.

## 4. Objetivo

Convertir el conocimiento de la sesión en un procedimiento reproducible que
separe auditoría, contención, preservación del trabajo, reescritura, publicación
y verificación posterior sin exponer nuevamente la credencial.

## 5. Propuesta de código o pasos

### Cambios aplicados en este cierre

- Se creó `.agents/skills/git-secret-forensics/SKILL.md` y su adaptador. La
  skill exige revocación previa, evidencia redactada, espejo temporal, igualdad
  de árboles, leases explícitos, control de `refs/pull/*` y limpieza de copias.
- `git-commit-push` ahora deriva las reescrituras de secretos a la skill
  forense, evitando interpretar una autorización de push normal como permiso
  para destruir historia.
- `scripts/check-quality.ps1 -SkillsOnly -SkillName <nombre>` valida focalmente
  una skill y su adaptador; el gate `-AgentOnly` conserva el escaneo de secretos
  existente.
- Se corrigió `docs/SECURITY.md` para reflejar el estado real de la clave local.

### Mejora de herramienta justificada

Crear en una entrega separada `scripts/audit-git-secrets.ps1`, con pruebas, que
escanee heads, tags, stashes, reflogs y objetos no alcanzables; produzca solo
conteos, rutas y hashes redactados; clasifique `integrity` de npm; y pueda
comparar automáticamente árboles antes/después de `git-filter-repo`. La sesión
dependió de comandos PowerShell ad hoc porque `gitleaks` y `trufflehog` no
estaban disponibles.

No se recomienda un agente adicional para la reescritura: los agentes comparten
worktree e índice Git, y las decisiones de leases, force-push y eliminación de
ramas deben permanecer seriales. Un agente de solo lectura sería útil únicamente
para revisar el informe, nunca para mutar referencias en paralelo.

### Contexto mínimo para futuros prompts

- proveedor y estado de revocación, sin incluir el secreto;
- ramas y tags autorizados, ramas que pueden eliminarse y ventana coordinada;
- URL del remoto y responsables afectados por el reclonado;
- autorización diferenciada para commit normal, reescritura y force-push;
- criterio de equivalencia de árboles y referencias excluidas;
- estado de forks, caches, artefactos y solicitud a GitHub Support.

## 6. Criterios de aceptación

- Las tareas y hashes verificables de la sesión están documentados sin secretos.
- Cada bloqueo contiene causa, solución y deuda residual factual.
- La skill forense separa operaciones de solo lectura y destructivas.
- La contradicción sobre la clave OpenAI local quedó corregida.
- `README.md`, `Roadmap.md`, `CHANGELOG.md` y documentación de seguridad reflejan
  el aprendizaje y cualquier información desactualizada.
- Las propuestas de herramienta y arquitectura derivan exclusivamente de
  obstáculos observados en esta sesión.
- Se documentaron los cambios y se actualizó toda instrucción desactualizada
  detectada durante el análisis.
