<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_CHAT_RAG_VUE_20260817.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_CHAT_RAG_VUE_20260817.md -->
<!-- NG-HEADER: Descripción: Retrospectiva factual del cierre de Chat, Telegram, RAG local y paridad Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva técnica — Chat 😎, Telegram, RAG y Vue

Fecha: 2026-08-17.

## Contexto

La sesión abarcó la estabilización del chatbot multicanal en desarrollo, el
arranque controlado de Telegram mediante polling, la normalización de Ollama en
GPU, la carga y evaluación de un corpus RAG clasificado, y la paridad técnica del
módulo Vue `/chat`. La evidencia consultada fue el código publicado, las pruebas
backend y Vue, el build, Alembic, las evaluaciones RAG, el smoke visual guest y
los outputs operativos compartidos durante la sesión.

El cierre se publicó en `dev` mediante `7bb1b31`, `8bc9dee` y `c66452d`; el SHA
local y remoto verificado fue `c66452d1094ce0ebf13f46057c0eac2e18f72c48`.
No se verificó un despliegue productivo ni los smokes autenticados de los cinco
roles, por lo que no se presentan como completados.

## Observaciones

### Completado y verificado

- Ollama respondió con `llama3.1:8b` usando GPU y
  `qwen3-embedding:4b` produjo vectores de 1536 dimensiones.
- Telegram respondió por long polling en desarrollo con canary, Redis y worker;
  la identidad personal usa `from.id` y el runtime mantiene políticas públicas.
- HTTP, WebSocket y Telegram convergen en el orquestador y en la sanitización de
  catálogo; las respuestas públicas no exponen SKU, proveedor ni stock exacto.
- El corpus RAG v1 cargó 10 fuentes con scopes explícitos. La evaluación obtuvo
  cero fugas, recall@5 sintético y curado 1,00, MRR 1,00, citas 100 %, presupuesto
  100 % y separación/invalidation de cache correcta.
- Las aclaraciones y respuestas WebSocket generan correlación y trazabilidad;
  los fixtures focales dejaron `TestClient` y ciclos async mezclados.
- Chat Vue consume `data.results`, soporta streaming, citas, cards sanitizadas,
  recuperación ante desconexión y panel de vínculos Telegram.
- El gate final aprobó 66 pruebas backend, 91 pruebas Vue, typecheck, build de
  610 módulos, validación de skills y un único head Alembic
  `20260816_chat_rollout_v1`.
- Se auditaron 107 archivos antes de publicar: cero patrones de secretos y cero
  archivos `.env` reales; sólo se versionó `.env.example`.

### Parcial o pendiente

- El smoke visual real cubrió `guest`; faltan `cliente`, `proveedor`,
  `colaborador` y `admin`, además de la matriz completa HTTP/WS/Telegram.
- `/chat` permanece `ready/legacy`; React continúa como fallback y Vue no debe
  activarse hasta aprobar todos los gates de paridad.
- El catálogo real no encontró «maceta soplada». Debe verificarse el dato
  canónico, sus aliases y disponibilidad antes de atribuirlo a RAG.
- El rollout productivo, sus ventanas temporales y el controlador automático no
  se ejecutaron: la sesión trabajó exclusivamente en desarrollo.
- OpenAI permanece sin API key. El soporte `OPENAI_API_KEY_FILE` quedó preparado,
  pero el diagnóstico por imágenes no fue implementado ni validado.

## Errores y/u outputs

1. **Telegram devolvía errores antes de reservar VRAM.** El modelo configurado
   no coincidía con el tag instalado y la clasificación legacy enviaba smalltalk
   al intent de producto. Se alineó `llama3.1:8b`, se retiró el falso positivo y
   luego Telegram respondió correctamente. Riesgo residual: consultas de
   catálogo sin dato canónico todavía devuelven “no encontrado”.
2. **El servidor local quedó con código anterior tras hot reload.** El launcher
   no pudo finalizar un proceso hijo; se detuvo el supervisor explícitamente y
   se reinició el stack. El smoke posterior aprobó conexión y respuesta sin
   errores de consola.
3. **El manifiesto RAG estaba ignorado por `*.json`.** `git status` no mostraba el
   corpus que debía ser versionado. Se agregó una excepción focal en `.gitignore`
   y el manifiesto entró al commit. La validación reutilizable es ejecutar
   `git check-ignore -v` sobre todo artefacto nuevo esperado.
4. **El test de OpenAI heredó configuración local.** La coexistencia del valor de
   prueba con `OPENAI_API_KEY_FILE` produjo conflicto; luego
   `AI_ALLOW_EXTERNAL=false` ocultó el proveedor. El test ahora elimina el
   `*_FILE` y construye settings con autorización explícita. La suite completa
   focal pasó 66/66 después de la corrección.
5. **Windows denegó la ejecución de la venv dentro del sandbox.** Se repitió el
   mismo comando con permiso elevado, conservando la venv Python 3.14.6 del
   proyecto. No se usó Python del sistema.
6. **El primer push fue bloqueado por destino externo no verificado.** Los tres
   commits se conservaron localmente; después de informar remoto y alcance, el
   usuario autorizó explícitamente los 107 archivos. El push y la igualdad de
   SHA local/remoto fueron verificados.

## Objetivo

Preservar un patrón seguro y repetible para avanzar Chat desde desarrollo:
configuración local fail-closed, corpus versionado y evaluado, contratos comunes
por canal, pruebas aisladas del entorno, publicación auditada y activación Vue
únicamente con evidencia por rol.

## Propuesta de código o pasos

| Prioridad | Carril | Mejora | Evidencia y frecuencia | Beneficio | Costo / opción recomendada |
|---|---|---|---|---|---|
| Alta | Prevención | Aislar automáticamente `NAME` y `NAME_FILE` en fixtures de secretos. | El conflicto OpenAI ocurrió dos veces durante el gate; es probable en equipos con `.env` local. | Tests deterministas sin debilitar la validación productiva. | Bajo; ampliar el fixture central de tests. |
| Alta | Prevención | Verificar artefactos esperados con `git check-ignore -v` antes del staging. | El manifiesto RAG versionado quedó oculto por `*.json`. | Evita entregas incompletas silenciosas. | Bajo; incorporar el control a la guía o quality gate Git. |
| Alta | Prevención | Mantener un smoke determinista por rol y canal con aliases de catálogo controlados. | Sólo guest fue recorrido de extremo a extremo y «maceta soplada» no tuvo match. | Detecta fugas, drift de permisos y huecos de catálogo antes de activar Vue. | Medio; ampliar `scripts/smoke_chat_roles.py` y fixtures canary. |
| Media | Aceleración | Añadir un comando de estado que reúna API, Vue, PostgreSQL, Redis, Ollama, worker y último poll. | El diagnóstico exigió correlacionar varios procesos y reiniciar un supervisor obsoleto. | Reduce tiempo de diagnóstico y evita confundir código stale con errores funcionales. | Medio; crear el `status_stack.py` ya previsto en `AGENTS.md`. |
| Media | Aceleración | Conservar el manifiesto RAG como fuente única de corpus y gates. | Carga, reindexación y evaluación fueron pasos repetibles y exitosos. | Hace reproducible la clasificación y evita publicar fuentes sin scope. | Bajo; ampliar `scripts/rag_corpus.py`, no crear otra skill. |
| Media | Prevención | Resolver la privacidad del remoto antes del push y registrar el alcance exacto. | La plataforma bloqueó la primera publicación aunque ya existía una solicitud general. | Evita bloqueos tardíos y exportaciones ambiguas. | Bajo; aplicar siempre `git-commit-push` con URL y conteo redactado. |

## Criterios de aceptación

- La retrospectiva diferencia completado, parcial y no verificado.
- Cada incidente registra síntoma, causa o límite, solución, evidencia y riesgo
  residual sin reproducir secretos ni contenido privado.
- README, Roadmap, Changelog y la guía agéntica enlazan este cierre.
- Los próximos gates permanecen explícitos: smokes de cinco roles, validación de
  catálogo, diagnóstico por imágenes y activación Vue.
- Todo cambio del cierre se valida, se audita y se publica en `dev` sin incluir
  credenciales ni afirmar un rollout productivo inexistente.
