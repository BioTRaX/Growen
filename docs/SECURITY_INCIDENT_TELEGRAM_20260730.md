<!-- NG-HEADER: Nombre de archivo: SECURITY_INCIDENT_TELEGRAM_20260730.md -->
<!-- NG-HEADER: Ubicación: docs/SECURITY_INCIDENT_TELEGRAM_20260730.md -->
<!-- NG-HEADER: Descripción: Informe forense de la exposición del token de Telegram -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Informe forense: exposición del token de Telegram

Fecha de auditoría: 2026-07-30

Estado: causa de fuga confirmada; erradicación del historial pendiente

Clasificación: incidente de credencial, severidad crítica

## Resumen ejecutivo

Se confirmó que el token operativo del bot de Telegram fue publicado en el
repositorio. El secreto se agregó como supuesto ejemplo dentro del filtro de
enmascaramiento de logs de `workers/telegram_polling.py:56`. GitHub Secret
Scanning lo validó como **Public leak** y abrió la alerta el 2025-12-16.

El commit que introdujo la credencial fue:

- `b4bf96907f05cc772f265400f7d8d60ba3dcf3ac`
- Fecha: `2025-12-15T21:52:31-03:00`
- Asunto: `Mask Telegram tokens in logs and improve log deletion`
- Archivo: `workers/telegram_polling.py:56`
- Blob afectado: `8df79f648a97e2c0cf546fd3128758c981f2944c`
- Huella segura del secreto: prefijo SHA-256 `2de10d614e9d`

El literal se eliminó del archivo en:

- `590ef3b8598b6434d7a8474d9a5b02f721cb1bdf`
- Fecha: `2026-07-23T20:45:25-03:00`
- Asunto: `feat(chat): incorpora seguridad y operación multicanal`

Eliminar el texto en un commit posterior no lo retira del historial. Al cierre
de esta auditoría, la punta de `main` todavía contiene el literal y el objeto
histórico sigue siendo recuperable. La revocación realizada en BotFather fue la
contención correcta y debe considerarse definitiva para esa credencial.

La combinación de evidencia es consistente con un abuso directo de la
credencial: la infraestructura Growen estaba apagada, el spam continuó y cesó
al revocar las API keys. No se hallaron cambios maliciosos ni un canal alterno
de envío en el código Telegram revisado. Esto confirma el vector Git/credencial
con alta confianza, pero una auditoría del repositorio por sí sola no puede
probar que el equipo, las cuentas de nube o las sesiones de navegador nunca
fueron comprometidos.

## Alcance y metodología

La auditoría se realizó sin imprimir secretos completos e incluyó:

- árbol de trabajo actual, archivos ocultos e ignorados;
- índice Git y reglas de `.gitignore`;
- 631 commits únicos alcanzables desde ramas, tags y reflogs;
- 137 puntas de referencias locales/remotas;
- ramas locales, ramas remotas, tag `v0.2.0` y stashes;
- 433 blobs no alcanzables informados por `git fsck`;
- patrones de Telegram exacto y ampliado, OpenAI, AWS, GitHub, Google,
  Slack, Stripe, llaves privadas y asignaciones sensibles;
- historial de nombres `.env`, archivos de credenciales y scripts;
- dependencias directas, locks y cambios recientes en scripts de arranque;
- rutas de salida de Telegram y dominios HTTP utilizados.

`gitleaks` y `trufflehog` no estaban instalados. El barrido se hizo con Git,
Ripgrep y expresiones regulares redactadas. Los 433 blobs no alcanzables eran
menores a 5 MiB y se escanearon completos; no hubo coincidencias de alta
confianza.

## Hallazgos

### F-01 — Token Telegram operativo publicado

Severidad: crítica

Estado: revocado, todavía presente en Git

Confianza: confirmada por proveedor

La credencial se incorporó en un comentario marcado como “Ejemplo” dentro de
un cambio destinado, paradójicamente, a ocultar tokens de los logs. Un ejemplo
de documentación nunca debe tener forma ni valor de una credencial real.

Las siguientes puntas todavía contienen el token en su snapshot actual:

- `refs/heads/main`
- `refs/remotes/origin/main`
- `refs/remotes/origin/HEAD`
- `refs/remotes/origin/dependabot/npm_and_yarn/frontend/multi-ed462d840e`
- `refs/remotes/origin/dependabot/npm_and_yarn/frontend/react-19.2.3`
- `refs/remotes/origin/dependabot/npm_and_yarn/frontend/react-dom-19.2.3`
- `refs/remotes/origin/dependabot/npm_and_yarn/frontend/react-router-dom-7.10.1`

`dev` y `origin/dev` contienen el commit de remoción, pero también conservan el
secreto en su historia ancestral.

### F-02 — Archivo `.env` versionado históricamente

Severidad: alta

Estado: eliminado del índice; persiste en la historia

`.env` fue agregado en dos líneas de historia paralelas:

- `71cb670367a61a4710d3102433b9d6178c2c109e`
- `e6f923a6b853e1a84b12a8852d683849fb49e394`
- Fecha: `2025-08-15T14:53:21-03:00`

Fue modificado en:

- `c3f4c309138b1c0c7e69a7f3fc1d2ed5415f5479`
- `599e6868a95f4b3e0ffd0ccb3dd6955664e41e94`
- Fecha: `2025-08-16T16:30:57-03:00`

Fue eliminado en:

- `c418884664d81fe99e35ea8b7c5c30b83b37d43b`
- `19e43bc23130761b8bba78eae6b3282e54810b10`
- Fecha: `2025-08-24T16:13:57-03:00`

Los campos Telegram, OpenAI y Tienda Nube de esas revisiones estaban vacíos.
Sí existía una URL PostgreSQL local con usuario y contraseña embebidos. Esa
credencial debe permanecer invalidada y no reutilizarse.

### F-03 — Clave OpenAI real en el `.env` local

Severidad: alta

Estado: no rastreada; rotación pendiente

El `.env` actual está correctamente ignorado y no está rastreado, pero contiene
una clave OpenAI con formato real en la línea 29. La presencia local no prueba
una publicación en Git: no se encontró ese formato en commits, reflogs ni blobs
no alcanzables. Debe rotarse porque el host forma parte del alcance del
incidente y la documentación anterior que la daba por eliminada estaba
desactualizada.

### F-04 — Protección `.gitignore`

Severidad: informativa

Estado: adecuada con endurecimiento recomendado

El árbol contiene cinco archivos de entorno:

- `.env`: ignorado, no rastreado;
- `.env.example`: rastreado intencionalmente;
- `frontend/.env.development`: rastreado intencionalmente;
- `frontend/.env.example`: rastreado intencionalmente;
- `frontend-vue/.env.example`: rastreado intencionalmente.

La regla `.env.*` con excepciones explícitas es correcta. Los ejemplos deben
mantener valores vacíos o placeholders que no cumplan formatos válidos de
proveedores.

### F-05 — Dependencias y scripts

Severidad: alta para React; informativa para el incidente

Estado: corrección de React pendiente

- No se observaron nombres directos compatibles con typosquatting en los
  manifiestos Python, React o Vue.
- `pip-audit` sobre `requirements-lock.txt`: sin vulnerabilidades conocidas.
- `npm audit --omit=dev` en `frontend-vue`: sin vulnerabilidades conocidas.
- `npm audit --omit=dev` en `frontend`: dos hallazgos altos relacionados entre
  sí en `react-router@7.18.1` y `react-router-dom@7.18.1`, con corrección disponible
  ([GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2)).
- Los cambios recientes de Telegram se concentran en el worker, migración de
  sesiones y arranque. Las salidas revisadas usan `api.telegram.org`; no se
  halló un host de exfiltración o dependencia agregada alrededor del incidente.

La vulnerabilidad de React debe corregirse, pero no explica el envío de spam
con la infraestructura apagada.

## Acciones obligatorias

### Contención inmediata

1. Mantener revocado el token filtrado; nunca restaurarlo.
2. Rotar la clave OpenAI local y cualquier credencial que haya compartido el
   mismo host, archivo, terminal o canal de distribución.
3. Confirmar en BotFather que no existan tokens adicionales activos del bot.
4. Revisar administradores del bot, sesiones Telegram y cuentas GitHub.
5. Marcar la alerta de GitHub como revocada sólo después de registrar evidencia.

### Erradicación Git

1. Preservar primero evidencia mínima en almacenamiento cifrado y restringido:
   hashes, fechas, alerta y logs; no crear otra copia abierta del secreto.
2. Integrar la remoción en `main` de inmediato.
3. Reescribir todas las referencias con `git filter-repo` o mecanismo
   equivalente para reemplazar el literal en cada blob.
4. Eliminar o regenerar las ramas Dependabot afectadas.
5. Forzar la publicación de las referencias saneadas en una ventana coordinada.
6. Invalidar clones, forks, caches de CI y artefactos; exigir reclonado limpio.
7. Verificar nuevamente todas las puntas y objetos antes de cerrar el incidente.

La reescritura es destructiva y no se ejecutó durante esta auditoría. Requiere
autorización explícita, coordinación con colaboradores y una copia forense
protegida.

### Prevención

- Habilitar GitHub Secret Scanning y Push Protection para todas las ramas.
- Ejecutar `gitleaks` o herramienta equivalente en pre-commit y CI sobre el
  contenido agregado y el historial relevante.
- Prohibir ejemplos que coincidan con formatos válidos. Usar
  `TELEGRAM_BOT_TOKEN=<valor_emitido_por_BotFather>`.
- No incluir tokens en URLs copiadas al navegador, tickets, capturas o logs.
- Usar secretos de entorno/CI con mínimo privilegio y rotación documentada.
- Tratar cualquier secreto confirmado en Git como comprometido aunque el
  repositorio sea privado.

## Criterios de cierre

- [x] Token expuesto identificado y revocado.
- [x] Commit, fecha, archivo, línea, blob y huella documentados.
- [x] Árbol actual, historia, reflogs, ramas, blobs no alcanzables y stashes
  revisados.
- [x] Política de secretos y documentación actualizadas.
- [ ] Token eliminado de la punta de `main`.
- [ ] Historia y ramas remotas saneadas.
- [ ] Clones, forks, caches y artefactos invalidados o revisados.
- [ ] Clave OpenAI local rotada.
- [ ] Push Protection y escaneo CI obligatorios habilitados.
- [ ] Dependencia React vulnerable actualizada y auditada nuevamente.
- [ ] Cambios documentados y cualquier instrucción desactualizada corregida.
