<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_REPOSITORY_PUBLICATION_20260721.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_REPOSITORY_PUBLICATION_20260721.md -->
<!-- NG-HEADER: Descripción: Retrospectiva técnica de la preparación, validación y publicación segura de la rama dev. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva de publicación segura en `dev` — 2026-07-21

## 1. Contexto

La sesión comenzó con un worktree en `main` que contenía cambios rastreados y no rastreados de plataforma, backend, migraciones, frontends y documentación. La instrucción operativa fue conservar todos los cambios, mover el trabajo a una rama `dev`, validar el conjunto y publicarlo sin modificar `main`.

La rama `dev` no existía local ni remotamente. Se creó desde `875a8a3`, el mismo commit de `origin/main`, manteniendo intacto el worktree. Luego se revisaron 327 archivos candidatos y se publicaron cuatro commits:

- `81a50a8` — plataforma, entorno agéntico, Docker y MCP.
- `6bc9e24` — API, migraciones, dominios y pruebas.
- `65fb7bd` — frontend Vue, fallback React y E2E.
- `6dba030` — documentación viva.

## 2. Observaciones

### Tareas completadas

- Creación y activación de `dev` sin perder cambios ni preparar archivos prematuramente.
- Revisión de estado, estadísticas, whitespace, NG-HEADER, documentación, dependencias y secretos.
- Ejecución del quality gate completo con Python 3.14.6 del `.venv`.
- Corrección de la inicialización SQLite de tests y de un smoke E2E inestable.
- Staging explícito por grupos; no se usó `git add .`.
- Creación de cuatro commits convencionales en español.
- Auditoría final de secretos con salida redactada y clasificación de falsos positivos.
- Publicación de `dev` en `https://github.com/BioTRaX/Growen.git` y verificación de igualdad entre `HEAD` y `origin/dev` en `6dba030061eb2ab86e7aca3dccc3e5c39c03a05b`.

### Evidencia final

- Python: 39 pruebas aprobadas; una advertencia conocida de `TestClient`/`httpx2`.
- Vue: 65 pruebas en 22 archivos, typecheck y build aprobados.
- E2E: 5 smokes Playwright aprobados.
- React: build aprobado.
- Seguridad: Ruff, Bandit, `pip-audit`, auditorías npm y escaneo de secretos aprobados; 0 vulnerabilidades conocidas reportadas.
- Git: worktree limpio y seguimiento `dev -> origin/dev` configurado.

## 3. Errores y/u outputs

| Incidente | Evidencia | Causa técnica | Estado |
|---|---|---|---|
| El sandbox rechazó el Python del `.venv` | `Unable to create process ... Acceso denegado` | Restricción de ejecución del sandbox, no defecto del repositorio | Resuelto mediante ejecución autorizada fuera del sandbox |
| Pytest falló con `table ... already exists` y `no such table` | 35/39 y luego 33/39 antes del fix | `sqlite+aiosqlite:///file:memdb1?...` resolvía en Windows a una ruta física; procesos existentes competían sobre el mismo esquema | Resuelto |
| Un comando exploratorio `pytest --trace-config` empezó a ejecutar tests | Proceso iniciado sin `--collect-only` y terminado manualmente | Uso incorrecto del comando de inspección | Resuelto; usar `pytest --version` e inspección de módulos para consultar plugins |
| El smoke de Compras no encontró el texto en 5 segundos | 1 E2E fallido, 4 aprobados | Primera compilación lazy de Vite y selector de texto genérico con timeout corto | Resuelto |
| El primer push fue rechazado por riesgo de exfiltración | Remoto externo no verificable como privado por la plataforma | Faltaba aprobación explícita informada para 327 archivos | Resuelto tras informar URL/alcance y recibir aprobación literal |
| El escaneo detectó `AKIA...` | Coincidencia en `frontend-vue/package-lock.json` | Fragmento aleatorio de un hash npm en la propiedad `integrity`, no clave AWS | Falso positivo clasificado |
| El quality gate fue silencioso durante etapas largas | Procesos activos sin salida incremental durante auditorías/tests | Herramientas que acumulan output hasta finalizar | Sin defecto funcional; se monitorearon procesos sin interrumpir |

### Deuda residual comprobada

- `fastapi.testclient.TestClient` emite `StarletteDeprecationWarning`; los tests nuevos deben usar `httpx.AsyncClient` y los heredados deben migrarse antes de `httpx2`.
- La concurrencia pesimista de Stock todavía requiere PostgreSQL real; SQLite no prueba bloqueo de filas.
- `.env.example` conserva valores simples de desarrollo para `ADMIN_PASS` y `SECRET_KEY` que ya existían en `origin/main`. No son credenciales nuevas ni secretas, pero nunca deben reutilizarse fuera de desarrollo.

## 4. Objetivo

Convertir los incidentes observados en controles reproducibles para que una futura publicación extensa:

1. preserve el worktree y la rama objetivo;
2. use el runtime obligatorio del proyecto;
3. detecte configuraciones SQLite que dejan de ser memoria real;
4. diferencie secretos de hashes lock sin exponer valores;
5. solicite aprobación informada antes de enviar código a un destino externo no verificado;
6. confirme el SHA remoto tras publicar.

## 5. Propuesta de código o pasos

### Cambios aplicados durante el cierre

- `db/session.py`: conserva `sqlite+aiosqlite:///:memory:` y agrega `StaticPool` sin URI `file:` nombrada.
- `frontend-vue/tests/e2e/shell.spec.ts`: valida el encabezado semántico `Compras` con timeout de 15 segundos.
- `.agents/skills/git-commit-push/SKILL.md`: incorpora auditoría redactada, clasificación de locks, verificación de remoto, aprobación explícita y comprobación del SHA.
- `docs/TESTING.md`, `docs/SECURITY.md` y `docs/DEVELOPMENT_WORKFLOW.md`: alinean el flujo canónico con los incidentes resueltos.

### Mejora propuesta basada en obstáculos reales

Crear en un cambio separado `scripts/audit-secrets.ps1` con pruebas automatizadas. Debe recibir una base y un head, inspeccionar solo archivos candidatos, emitir hallazgos redactados, reconocer campos npm `integrity`, detectar `.env` no permitidos y devolver un código distinto de cero ante hallazgos no clasificados. Esta herramienta reemplazaría el scanner PowerShell ad hoc utilizado en la sesión.

No se justifica una skill nueva: `git-commit-push` es el punto de control correcto y fue ampliada. Tampoco se justifica un agente adicional; staging, commit y push comparten un único índice Git y deben ejecutarse serialmente. Un subagente paralelo aumentaría el riesgo de clasificar un estado distinto o interferir con el worktree.

### Contexto que debe incluir un futuro prompt de publicación

- rama origen y rama destino;
- URL exacta del remoto y confirmación de confianza/privacidad;
- si se autorizan stage, commit y push;
- alcance esperado y cambios que deben excluirse;
- quality gate requerido;
- autorización explícita para un destino externo cuando la plataforma la exija.

## 6. Criterios de aceptación

- Las tareas realizadas y los cuatro commits están registrados con evidencia verificable.
- Cada error observado contiene causa, solución y estado; no se atribuyen fallos no reproducidos.
- La documentación ya no presenta la colisión SQLite como deuda vigente.
- La skill Git refleja los controles que faltaron en el primer intento de push.
- README, Roadmap, Changelog, Testing, Seguridad y workflow de desarrollo quedaron actualizados.
- Las propuestas de herramienta y arquitectura provienen exclusivamente de obstáculos de esta sesión.
- No se incluyen secretos, cookies ni valores de credenciales en este reporte.
