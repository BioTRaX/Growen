<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_TOKEN_OPTIMIZATION_20260926.md -->
<!-- NG-HEADER: Ubicación: docs/retrospectives/RETROSPECTIVE_TOKEN_OPTIMIZATION_20260926.md -->
<!-- NG-HEADER: Descripción: Retrospectiva de arquitectura de optimización de tokens, lazy-loading de Superpowers y filtros de contexto. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva: optimización de tokens y gestión contextual — 2026-09-26

## Contexto

El incremento en el uso de modelos de razonamiento avanzado y asistentes de desarrollo (Copilot, Codex, Gemini/Antigravity, Cursor) provocó un agotamiento acelerado de las cuotas de tokens en interacciones con el repositorio Growen. La causa principal radicaba en la indexación de fondo de carpetas masivas (`.venv/`, `node_modules/`, `media/`, y `logs/` con más de 7 MB de texto plano), sumada a la inyección potencial estática de las 14 skills completas de Superpowers (~370 KB de texto, equivalentes a ~90.000 tokens en prompt inicial).

La sesión se ejecutó bajo la rama efímera `chore/token-context-optimization` con lock cooperativo `git-worktree` activo, garantizando la preservación del acceso a logs bajo demanda y la plena compatibilidad metodológica sin duplicar forks de Superpowers.

## Observaciones

| Tarea | Estado | Evidencia |
|---|---|---|
| Filtros de exclusión contextual | Completada | Creación de `.copilotignore`, `.geminiignore`, `.cursorignore`, `.aiderignore` y actualización de `.gitignore`. |
| Lazy loading de Superpowers | Completada | Catálogo minimalista en `docs/superpowers/CATALOG.md` (~500 tokens) con protocolos en 4 niveles y actualización de `README.md`. |
| Preservación de logs bajo demanda | Completada | Verificación en vivo de lectura acotada (`Get-Content logs/worker_telegram_polling.log -Tail 5`) y exclusión de embeddings masivos. |
| Pauta de Context-Splitting | Completada | Guía integral en `docs/development/TOKEN_OPTIMIZATION.md` con matrices por dominio y reglas mono-sesión. |
| Pruebas de integridad de gobernanza | Completada | Suite automatizada `tests/test_token_optimization_and_ignore_rules.py` con 5/5 casos aprobados en el venv oficial. |

## Errores y/u outputs

1. **Archivos de aider preexistentes en status:** `.aider.chat.history.md`, `.aider.input.history` y `.aider.tags.cache.v4/` figuraban como untracked. Se agregaron a `.gitignore` preservando explícitamente el versionado de `.aiderignore`.
2. **Sintaxis de lectura de frontmatters en PowerShell:** `Get-Content` falló inicialmente por combinar `-Raw` y `-TotalCount`. Se corrigió con `-TotalCount 6` para leer estrictamente los metadatos YAML.
3. **Validación de suites:**
   - Suite canónica de skills (`test_create_service_skill.py`, `test_retrospective_skill.py`): `9 passed in 3.24s`.
   - Suite de optimización y reglas de exclusión (`test_token_optimization_and_ignore_rules.py`): `5 passed in 11.24s`.
   - `git diff --check`: 0 errores de whitespace o formato.

## Objetivo

Configurar el entorno y la estructura de consumo agéntico para reducir drásticamente el consumo de tokens de entrada en Copilot, Codex y Gemini, preservando la funcionalidad de Superpowers y el acceso a logs bajo demanda.

## Evolución agéntica

- **Mejora materializada:** Se implementó una suite unitaria permanente (`tests/test_token_optimization_and_ignore_rules.py`) que audita determinísticamente la presencia de archivos de exclusión, la obligatoriedad de los patrones críticos, la indexación de las 14 skills en `CATALOG.md` y la disponibilidad física de `logs/`.
- **Acelerador futuro:** Incorporar este verificador al gate de cierre o preflight local para evitar que modificaciones accidentales en `.gitignore` o reglas de indexación vuelvan a exponer carpetas pesadas a la indexación de modelos de lenguaje.

## Compuerta de riesgo

- **Clasificación:** **Bajo**.
- **Justificación:** Los cambios abarcan exclusivamente archivos de configuración de indexación contextual (`.*ignore`), documentación viva, guías metodológicas, catálogo minimalista y pruebas unitarias aisladas. No existen mutaciones en base de datos, modelos SQLAlchemy, dependencias externas ni endpoints de producción. Es 100 % reversible.

## Actualización de documentación viva

- `AGENTS.md`: Incorporación obligatoria de subsecciones sobre Lazy Loading de Superpowers, Filtros de Exclusión, Acceso a Logs Bajo Demanda y Pauta de Context-Splitting.
- `docs/development/AGENT_SKILLS.md`: Inclusión del protocolo de lazy loading y referencias al catálogo minimalista.
- `docs/superpowers/README.md`: Enlace al nuevo `CATALOG.md` y directiva de aislamiento de planes/specs históricos.
- `docs/development/TOKEN_OPTIMIZATION.md`: Documento maestro de economía de tokens y partición de contexto.
- `Roadmap.md`: Registro de hito completado al 2026-09-26.
- `README.md`: Actualización de enlaces en la sección de lineamientos de agentes.
