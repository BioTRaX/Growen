<!-- NG-HEADER: Nombre de archivo: TOKEN_OPTIMIZATION.md -->
<!-- NG-HEADER: Ubicación: docs/development/TOKEN_OPTIMIZATION.md -->
<!-- NG-HEADER: Descripción: Guía integral de optimización de tokens, filtros de exclusión contextual, lazy-loading de skills y segmentación de sesiones (context-splitting). -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Optimización de tokens y gestión contextual en Growen

Este documento establece las políticas, configuraciones y lineamientos operativos para maximizar la eficiencia en el consumo de tokens en asistentes de IA (GitHub Copilot, OpenAI Codex, Google Gemini / Antigravity y Cursor) al interactuar con el repositorio Growen.

---

## 1. Diagnóstico y problemática resuelta

La combinación de un repositorio full-stack (FastAPI + Vue 3 + PostgreSQL + Redis/Dramatiq) con paquetes externos de habilidades agénticas (como Superpowers) puede generar un consumo explosivo de tokens de entrada antes incluso de que el modelo comience a responder:

1. **Bloat por carga estática de skills:** Las 14 skills de Superpowers suman ~370 KB de texto (~90.000 a 100.000 tokens). Si un asistente las inyecta en bloque en cada turno, satura la ventana de contexto y agota las cuotas de suscripciones profesionales.
2. **Indexación contextual indiscriminada:** Herramientas como GitHub Copilot (`@workspace`), Gemini Code Assist o indexadores de IDE escaneaban por defecto carpetas voluminosas como `.venv/` (1.2 GB), `node_modules/` (210 MB), archivos binarios/imágenes en `media/` y la carpeta `logs/` (más de 7 MB de texto plano).
3. **Contaminación cruzada de dominio:** Mantener conversaciones largas mezclando desarrollo de componentes Vue con migraciones Alembic o infraestructura Docker produce "ruido contextual" que degrada el razonamiento del modelo y multiplica innecesariamente los tokens consumidos en cada turno.

---

## 2. Arquitectura de exclusión contextual

Para impedir que los motores de IA indexen archivos innecesarios de fondo, el repositorio implementa una matriz unificada de archivos de exclusión que respetan la sintaxis estándar de globbing:

| Archivo | Asistente / Herramienta | Función |
|---------|-------------------------|---------|
| [`.copilotignore`](file:///.copilotignore) | GitHub Copilot (VS Code / JetBrains / Web) | Bloquea la inclusión de archivos en el contexto `@workspace`, autocompletado e indexación semántica. |
| [`.geminiignore`](file:///.geminiignore) | Google Gemini CLI, Gemini Code Assist, Antigravity | Excluye rutas de la base vectorial local y del escaneo contextual de Gemini. |
| [`.cursorignore`](file:///.cursorignore) | Cursor IDE | Previene el escaneo de fondo para codebase indexing. |
| [`.aiderignore`](file:///.aiderignore) | Aider CLI | Evita que el `repomap` de Aider se infle con dependencias o logs. |
| [`.gitignore`](file:///.gitignore) | Git / Entorno general | Evita el seguimiento de artefactos temporales y estado efímero. |

### Regla estricta de exclusiones:
Quedan estrictamente excluidos de la indexación automática de contexto:
- `.venv/`, `env/`, `venv/`, `__pycache__/`, `*.py[cod]`
- `node_modules/`, `frontend-vue/dist/`, `frontend-vue/.vite/`, `*.tsbuildinfo`
- `media/`, `Imagenes/`, `ImagenesTest/`, `Productos/`, `catalogos/`, `Conocimientos/`
- `logs/`, `*.log`, `*.log.*`
- `tmp/`, `temp/`, `scratch/`, `.cache/`, `.pytest_cache/`, `.ruff_cache/`
- `certs/`, `credentials/`, `secrets/`, `.env*` (salvo plantillas seguras)
- `.agents/state/` (locks efímeros)
- `docs/superpowers/plans/`, `docs/superpowers/specs/` (histórico de planes ejecutados)

---

## 3. Acceso a logs bajo demanda (On-Demand Debugging)

> **Principio clave:** Los archivos de log NO deben indexarse de forma permanente ni cargarse automáticamente al contexto, pero permanecen 100% accesibles en el disco para depuración cuando se solicite explícitamente.

### ¿Cómo consultar logs de manera eficiente sin saturar tokens?

1. **Lectura acotada con comandos:**
   Nunca pedir "revisá todo el backend.log". En su lugar, consultar únicamente las líneas recientes o filtrar por error:
   ```powershell
   # Leer las últimas 50 líneas de un worker
   Get-Content logs/worker_telegram_polling.log -Tail 50

   # Buscar un error específico sin volcar el archivo completo
   Select-String -Path logs/backend.log -Pattern "ERROR" | Select-Object -Last 20
   ```
2. **Uso de herramientas de agente:**
   Utilizar `view_file` especificando `StartLine` y `EndLine` para leer solo el bloque relevante del log, en vez de transferir archivos de varios megabytes.
3. **Rotación y limpieza periódica:**
   Utilizar los scripts canónicos de mantenimiento:
   - `python scripts/clear_backend_log.py`
   - `python scripts/cleanup_logs.py`

---

## 4. Protocolo de Lazy Loading para Superpowers

Growen no elimina las skills de Superpowers instaladas globalmente en `~/.agents/skills/superpowers/`, sino que desacopla su catálogo de su contenido extenso:

### Niveles del protocolo:

1. **Nivel 1: Catálogo Mínimo en Memoria (~500 tokens)**
   El asistente solo necesita conocer el nombre y una descripción de una sola línea de cada una de las 14 skills. Este registro reside en [`docs/superpowers/CATALOG.md`](../superpowers/CATALOG.md).
2. **Nivel 2: Verificación de Precedencia Canónica de Growen**
   Antes de considerar una skill de Superpowers, el agente DEBE verificar si existe una skill canónica en `.agents/skills/` que resuelva el requerimiento:
   - Diagnóstico de servicios $\rightarrow$ `diagnose-local-services`
   - Git / Cierres $\rightarrow$ `git-commit-push` / `retrospectiva-tecnica-sesion`
   - Base de datos / Migraciones $\rightarrow$ `database-migrations`
   - Creación de servicios $\rightarrow$ `create-service`
   - Módulos UI $\rightarrow$ `vue-module-migration`
   - Nuevas skills $\rightarrow$ `skill-scaffolder`
   Si una skill canónica aplica, **NO se carga Superpowers**.
3. **Nivel 3: Carga Bajo Demanda (Lazy Load)**
   Solo cuando se requiera explícitamente la metodología de Superpowers (por ejemplo, `systematic-debugging` ante un bug no trivial), el agente lee **únicamente** el archivo `SKILL.md` específico:
   `~/.agents/skills/superpowers/<nombre-skill>/SKILL.md`
4. **Nivel 4: Cierre y No Propagación**
   Al finalizar el bloque metodológico, las instrucciones de la skill no se arrastran a las interacciones posteriores de la sesión.

---

## 5. Pauta de Context-Splitting (Sesiones segmentadas por dominio)

Para evitar la contaminación cruzada y el crecimiento descontrolado del prompt en conversaciones largas, los agentes y desarrolladores deben estructurar su trabajo en **sesiones mono-dominio**:

### Dominios de trabajo delimitados:

| Dominio | Archivos / Rutas de Alcance | Lo que NUNCA debe cargarse en la sesión |
|---------|-----------------------------|----------------------------------------|
| **Frontend UI** | `frontend-vue/src/**`, vistas, componentes, stores Pinia, `modules.json` | Migraciones Alembic, código SQL crudo, workers Dramatiq, Docker Compose |
| **Backend & API** | `services/**`, `agent_core/**`, esquemas Pydantic, dependencias de FastAPI | Componentes Vue, estilos CSS/SCSS, scripts de despliegue Swarm |
| **Base de Datos** | `db/**`, `db/migrations/**`, `docs/features/MIGRATIONS_NOTES.md` | Código de frontend, plantillas HTML, workers asíncronos no relacionados |
| **Workers & Scraping** | `workers/**`, `services/jobs/**`, configuración de colas Redis/Dramatiq | UI Vue, router frontend, componentes visuales |
| **Infraestructura / Swarm** | `docker-compose.yml`, `docker-stack.yml`, `infra/**`, Nginx configs | Código de lógica de componentes individuales, vistas Vue |
| **Gobernanza & Agentes** | `.agents/**`, `AGENTS.md`, `docs/architecture/**` | Archivos de datos, logs masivos, librerías del venv |

### Reglas de oro para sesiones de chat eficientes:

1. **Una tarea = Una sesión = Un dominio:** No utilizar el mismo hilo de chat para ajustar un componente de Vuetify y seguidamente diseñar una migración de PostgreSQL.
2. **Reinicio tras cierre:** Al invocar `retrospectiva-tecnica-sesion` o finalizar una entrega técnica, la sesión debe cerrarse. La siguiente tarea comienza en un hilo limpio.
3. **Referencia puntual de archivos:** En lugar de solicitar al agente "revisá el proyecto para ver qué falla", proporcionar la ruta exacta en formato markdown: `[archivo.py](file:///services/routers/catalog.py)`.
4. **Resumen de contexto en traspasos:** Si una tarea de backend requiere una adaptación en el frontend, el agente debe cerrar la fase de backend produciendo un contrato de interfaz conciso (ej. esquema JSON del endpoint) e iniciar una nueva sesión en el dominio de Frontend con dicho contrato como único input.

---

## 6. Métricas de impacto

| Parámetro | Antes de la optimización | Con la optimización activa | Beneficio |
|-----------|--------------------------|---------------------------|-----------|
| **Carga de skills Superpowers** | ~90.000 tokens (14 skills completas) | ~500 tokens (catálogo minimalista) | **-99.4% tokens en prompt inicial** |
| **Indexación de `logs/`** | ~7.1 MB de logs escaneados en fondo | 0 tokens (acceso bajo demanda) | **Elimina contaminación de trazas viejas** |
| **Indexación de `.venv` y builds** | > 1.4 GB de archivos candidatos | 0 archivos en `@workspace` | **Búsquedas semánticas limpias y rápidas** |
| **Duración de cuotas Pro** | Agotamiento acelerado en pocas horas | Consumo quirúrgico y predecible | **Máxima disponibilidad de modelos Pro** |
