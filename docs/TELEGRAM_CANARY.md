<!-- NG-HEADER: Nombre de archivo: TELEGRAM_CANARY.md -->
<!-- NG-HEADER: Ubicación: docs/TELEGRAM_CANARY.md -->
<!-- NG-HEADER: Descripción: Funcionamiento, captura y despliegue seguro del canary Telegram. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Canary de Telegram

## Qué es y qué no es

El canary es una única cuenta Telegram de prueba autorizada durante la fase
`preflight`. No es el bot, un token, un rol, un administrador ni el controlador
automático de rollout. El token autentica a Growen ante Telegram; el
`telegram_canary_user_id` identifica a la persona autorizada a probar el bot.

El controlador de rollout es otro proceso: evalúa métricas y decide si una fase
productiva puede avanzar o retroceder. En desarrollo puede quedar apagado y
`preflight` puede utilizarse como una allowlist estable de un solo tester.

## Cómo se autoriza al usuario

1. Telegram entrega el mensaje con `message.from.id` y `message.chat.id`.
2. Growen toma exclusivamente `from.id` como identidad personal. `chat.id` sólo
   identifica el destino o la conversación.
3. El valor configurado en `TELEGRAM_CANARY_USER_ID_FILE` nunca se guarda como
   rol. Growen calcula un HMAC tanto para el remitente como para el canary y los
   compara en tiempo constante.
4. Si el rollout está `preflight/active` y coinciden, el mensaje continúa por el
   pipeline común. Si no coinciden, se responde mantenimiento.
5. Fuera de `preflight`, el acceso depende de la fase y del rol actual en
   `User.role`; el canary deja de ser una excepción de acceso.

La implementación actual admite un solo canary. No se debe reutilizar este
secreto como lista de administradores. Si se necesitan varios testers, debe
crearse una allowlist separada, auditable y revocable.

## Captura recomendada en desarrollo

La captura usa el token ya almacenado y escucha únicamente un comando
`/canary` en chat privado. No muestra el token ni el ID.

Terminal 1:

```powershell
$SecretDir = Join-Path $env:LOCALAPPDATA 'Growen\secrets'
.\.venv\Scripts\python.exe scripts\generate_chat_keys.py `
  --output-dir $SecretDir `
  --capture-canary `
  --capture-timeout 120
```

Mientras aparezca `Esperando /canary...`, abrir el chat privado con el bot y
enviar un mensaje nuevo que contenga exactamente:

```text
/canary
```

No ejecutar simultáneamente el worker Telegram ni otro proceso que consuma
`getUpdates`. Si el comando termina con
`telegram_canary_message_not_received`, volver a iniciarlo y enviar un
`/canary` nuevo durante la espera. Un `/start` anterior puede haber sido
consumido y no aparecer en una consulta posterior.

## Activación local

Con PostgreSQL migrado y los flags Telegram todavía bajo control:

```powershell
.\.venv\Scripts\python.exe scripts\chat_rollout_gate.py initialize-preflight --development
.\.venv\Scripts\python.exe scripts\chat_rollout_gate.py initialize-preflight --development --apply
```

El primer comando es dry-run. `--development` sólo funciona con
`ENV=dev|test|testing`, deja `auto_advance=false` y no exige acumular ventanas de
métricas productivas.

## Lecturas relacionadas

- `docs/CHAT_DEPLOYMENT.md`: preflight, servicios, fases y rollback.
- `docs/CHATBOT_ARCHITECTURE.md`: pipeline multicanal e identidad.
- `docs/SECURITY.md`: roles y techo de Telegram.
- `docs/SECURITY.md`: secretos, HMAC, privacidad y logs.
- `docs/CHAT.md`: contratos HTTP, WebSocket y Telegram.
- `docs/MIGRATIONS_NOTES.md`: estado de la revisión de rollout.
- `scripts/chat_rollout_gate.py`: inicialización y transiciones permitidas.
- `services/chat/rollout.py`: decisión de acceso y controlador automático.

## Diagnóstico seguro

- `telegram_webhook_active`: hay un webhook configurado; polling y webhook no
  deben consumir updates a la vez.
- `telegram_api_unavailable`: fallo HTTP o conectividad con Telegram.
- `telegram_capture_timeout`: la solicitud excedió el tiempo configurado.
- `telegram_canary_message_not_received`: no llegó un `/canary` privado durante
  esa consulta.
- `telegram_bot_token` ya existe: el generador lo conserva; no lo sobrescribe.
