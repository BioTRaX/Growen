<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_SESSION_20260905.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_SESSION_20260905.md -->
<!-- NG-HEADER: Descripción: Retrospectiva consolidada del cierre técnico del 5 de septiembre de 2026 -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva consolidada de sesión — 2026-09-05

## Implementaciones relevadas

- SiYuan incorporó edición privada con revisión, historial, base estructurada de tareas, publicación Git controlada y el widget Crono sincronizable.
- Mercado consolidó jobs persistentes de descubrimiento, validación y extracción, detección focal y validación manual auditable desde Vue.
- MeLi quedó aislado como dominio transaccional con OAuth PKCE, webhooks idempotentes, outbox, sincronización de stock, Cloudflare Tunnel y definición Swarm.
- El entorno agéntico adoptó ramas efímeras obligatorias desde `dev`, cierre secuencial, resolución verificable de conflictos y una matriz de precedencia que evita duplicar Superpowers.

## Dificultades y errores

- Los scripts exploratorios de SiYuan dependían de rutas locales de credenciales y datos de workspace. Se preservaron fuera de Git y `scratch/` quedó ignorado para impedir su publicación accidental.
- La validación integral detectó versiones vulnerables de `cryptography`, `pypdf` y `pip`. Se elevaron los pisos, se regeneraron todos los locks con hashes y la auditoría local quedó sin vulnerabilidades conocidas.
- `pip-tools 7.5.3` no ejecuta con `pip 26.2.1` por una API interna eliminada. La regeneración usa temporalmente `pip 26.1.2`, pero los requisitos y el entorno validado terminan en `pip 26.2.1`.
- Dos pruebas de Chat heredaban `OPENAI_API_KEY_FILE` del entorno mientras definían una clave ficticia directa. Se aislaron ambas fuentes para validar el flujo sin leer credenciales reales ni debilitar el rechazo de configuraciones ambiguas.
- Una prueba criptográfica MeLi tenía el mismo problema de aislamiento con `MELI_TOKEN_ENCRYPTION_KEY_FILE`, y el contrato del head Alembic todavía apuntaba a la revisión previa. Ambos casos se alinearon con la configuración segura y con `20260905_meli_scopes_text`.
- El gate de ambos frontends detectó vulnerabilidades transitivas altas y moderadas en `brace-expansion`, `browserslist`, `nanoid`, `postcss` y `react-router`. Se actualizaron las resoluciones compatibles, se regeneraron los locks y `npm audit` quedó sin hallazgos. El umbral obligatorio se elevó de alto a moderado.
- El generador de locks agregaba una línea vacía adicional al final. Se normalizó la escritura para producir exactamente un salto de línea final.
- La acumulación de cambios de varios dominios amplió el alcance del cierre. Se mantuvieron gates focales por componente y un gate integral previo a la integración.

## Evolución agéntica implementada

- Las skills canónicas conservan contratos específicos de Growen y referencian la metodología general de Superpowers sin copiarla.
- Los únicos triggers directos de cierre son `Cerrar sesión` y `Cerremos sesión`; ante trabajo ambiguo se solicita confirmación breve.
- Todo agente crea una rama efímera desde el estado actual de `dev`; los commits directos a `dev` están prohibidos.
- El cierre exige retrospectiva, evolución, compuerta de riesgo, documentación, sincronización con `origin/dev`, resolución autónoma demostrable, validación, merge y push.
- Las propuestas de riesgo bajo o medio se implementan; una de riesgo muy alto detiene el flujo hasta recibir autorización explícita.
- El auditor y las pruebas contractuales verifican estas reglas y la precedencia sobre Superpowers.

## Seguridad y riesgo residual

- No se versionan tokens, credenciales, archivos personales ni scripts locales que los consuman.
- Los locks autónomos de API, workers y MCP fijan versiones corregidas de las dependencias auditadas.
- Permanecen pendientes los smokes reales documentados para notificaciones, stock y renovación MeLi, además de las validaciones operativas que requieren credenciales o infraestructura externa.
- El drift histórico de Alembic se conserva explícito; no se encubre con una migración masiva.

## Evidencia de cierre

- Gate integral: 51 pruebas backend, 100 pruebas Vue, 5 E2E, typecheck, builds React/Vue, auditoría Python, auditorías npm y SBOM completados.
- Suites focales de SiYuan, Mercado, MeLi y migraciones: 185 aprobadas y 2 omitidas por condiciones declaradas.
- Widget Crono: 8 pruebas Node aprobadas.
- `docker compose config` y `docker stack config` validaron las definiciones; el stack se renderizó con imágenes y callback de ejemplo, sin secretos reales.
- La integración queda condicionada al escaneo final del índice, la sincronización con `origin/dev` y la repetición del gate sobre el árbol fusionado.
