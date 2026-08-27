<!-- NG-HEADER: Nombre de archivo: CHAT_DEPLOYMENT.md -->
<!-- NG-HEADER: Ubicación: docs/CHAT_DEPLOYMENT.md -->
<!-- NG-HEADER: Descripción: Preflight, rollout y rollback productivo de Chat, Telegram y Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Despliegue de Chat 😎

## Estado seguro inicial

La revisión `20260816_chat_rollout_v1` crea `disabled/paused`. Los flags `TELEGRAM_ENABLED`, `TELEGRAM_PUBLIC_BOT_ENABLED` y `TELEGRAM_ROLE_LINKING_ENABLED` continúan como kill switch y deben permanecer en `0` hasta aprobar todos los gates. No se revierten migraciones durante rollback.

## Secretos

Definir `GROWEN_SECRET_DIR` como ruta persistente fuera del repositorio. El directorio se monta read-only en `/run/secrets/growen`.

```powershell
$SecretDir = Join-Path $env:LOCALAPPDATA 'Growen\secrets'
.\.venv\Scripts\python.exe scripts\generate_chat_keys.py --output-dir $SecretDir --interactive-bot-token
icacls $SecretDir /inheritance:r /grant:r "${env:USERNAME}:(OI)(CI)F"
```

Para capturar el ID sin imprimirlo, iniciar la escucha y, mientras está activa,
enviar `/canary` en un chat privado con el bot:

```powershell
.\.venv\Scripts\python.exe scripts\generate_chat_keys.py `
  --output-dir $SecretDir `
  --capture-canary `
  --capture-timeout 120
```

Las entradas interactivas permanecen ocultas. El script crea
`telegram_bot_token`, `telegram_canary_user_id`,
`telegram_identity_encryption_key` y `telegram_identity_hmac_key` sin mostrar
valores y conserva archivos existentes. Configurar en `.env` solamente
`GROWEN_SECRET_DIR=<ruta absoluta>`; el contenido de los secretos no va allí.
La clave anterior es opcional y sólo se usa durante una rotación controlada.
El detalle del modelo de acceso y diagnóstico está en `docs/TELEGRAM_CANARY.md`.

OpenAI permanece opcional y apagado. Si posteriormente se habilita diagnóstico
por imágenes, crear `openai_api_key` con `--interactive-openai-key` y configurar
`OPENAI_API_KEY_FILE` con su ruta absoluta en el host. Compose lo monta en los
runtimes IA como `/run/secrets/growen/openai_api_key`. Mantener
`AI_ALLOW_EXTERNAL=false` hasta aprobar privacidad,
costos y smokes del flujo de visión.

## Preflight

1. Aprobar `scripts/ollama-preflight.ps1`: ≥8 GiB de VRAM libre, ≥1,5 GiB de RAM libre, pagefile automático o fijo ≥16 GiB y ≥15 GiB de disco.
2. Iniciar Ollama y descargar exactamente `llama3.1:8b` y `qwen3-embedding:4b`.
3. Validar health de generación y embeddings; dimensión 1536.
4. Iniciar PostgreSQL y Redis; aplicar Alembic hasta `20260816_chat_rollout_v1`.
5. Ejecutar `scripts/rag_corpus.py --synthetic --curated`, luego `--evaluate`.
6. Ejecutar suite backend/Vue e integración Redis.
7. Preparar el archivo absoluto `CHAT_SMOKE_CREDENTIALS_FILE` fuera del repo con credenciales efímeras para cliente, proveedor, colaborador y admin.
8. Ejecutar `scripts/smoke_chat_roles.py`; retirar los usuarios/credenciales de smoke al terminar.

El comando que inicia preflight tiene dry-run por defecto:

```powershell
.\.venv\Scripts\python.exe scripts\chat_rollout_gate.py initialize-preflight
.\.venv\Scripts\python.exe scripts\chat_rollout_gate.py initialize-preflight --apply
```

No usar `--apply` hasta aprobar los ocho puntos.

### Flujo reducido para desarrollo

En `ENV=dev` no es necesario ejecutar el controlador de rollout ni acumular
muestras por fase. Se puede usar `preflight` como allowlist estable de un solo
tester y dejar el autoavance apagado:

```powershell
.\.venv\Scripts\python.exe scripts\chat_rollout_gate.py initialize-preflight --development
.\.venv\Scripts\python.exe scripts\chat_rollout_gate.py initialize-preflight --development --apply
```

`--development` falla cerrado fuera de `dev/test/testing`. El token autentica al
bot frente a Telegram; `telegram_canary_user_id` identifica qué persona puede
hablarle durante esta prueba. Son datos diferentes y ninguno reemplaza al otro.

## Servicios Compose

```powershell
docker compose up -d db redis api frontend
docker compose --profile telegram up -d telegram_worker chat_rollout_controller
```

El worker es no-root, filesystem read-only, cola acotada y health basado en `logs/telegram_health.json`. Ollama corre en el host y se alcanza por `host.docker.internal`; el puerto 11434 no se publica mediante Compose.

`telegram_worker` es el único worker que ejecuta el preflight completo de
transporte, flags y secretos del bot. Los workers de catálogo, Mercado, Enrich
y Conocimiento sobrescriben los flags Telegram a `0` y no montan el token. No
se debe compartir `/run/secrets/growen/telegram_bot_token` con consumidores
ajenos para corregir errores de arranque.

## Fases

`disabled → preflight → guest → linked_basic → collaborator → admin_capped → vue_eligible → vue_active → stable`.

`preflight` es la verificación previa a abrir el bot. En esa fase sólo puede
interactuar el **canary**, una cuenta Telegram de prueba cuyo `from.id` está en
`telegram_canary_user_id`. Sirve para comprobar el circuito real sin exponerlo
todavía al público. No es un rol ni una credencial administrativa. En
desarrollo funciona simplemente como una allowlist de un usuario.

El controlador evalúa cada cinco minutos. No autoavanza con muestra insuficiente. Una fuga, mutación o violación de autorización vuelve a `disabled/paused`; dos fallos consecutivos de fiabilidad deben volver a la fase estable anterior y pausar. Admin nunca obtiene capacidades superiores a colaborador en Telegram.

Los únicos endpoints manuales son consulta, pause, resume y rollback. No existe force-advance.

## Vue y rollback

El manifiesto fuente conserva `ready/legacy`. Sólo el workflow `.github/workflows/chat-production-rollout.yml` usa `CHAT_MODULE_RUNTIME=vue` desde un runner `[self-hosted, windows, growen-production]` cuando el estado es `vue_eligible/active`. El artefacto registra SHA, runtime y fecha.

Si falla quality gate o smoke, se restaura `growen/frontend:rollback-<sha>` y el estado vuelve a `admin_capped/paused`. React se retira únicamente tras dos releases y siete días continuos en `stable`.

## Estado local actual

El 2026-08-17 el preflight Ollama completo aprobó: RTX 5070, carga `100% GPU`,
contexto 4096, pagefile de 18 GB, RAM/disco suficientes y ambos modelos. Token,
canary y claves de identidad están almacenados fuera del repositorio. El rollout
local está `preflight/active`, con autoavance deshabilitado, y el worker polling
fue iniciado mediante `scripts/start_worker_telegram_polling.cmd`. PostgreSQL,
Redis y Ollama están saludables; el bot procesó sus primeros updates.
La configuración local y de enriquecimiento referencia el tag completo
`llama3.1:8b`; Ollama trata `llama3.1` como otro identificador y devuelve 404 si
ese tag no existe.
