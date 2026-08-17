<!-- NG-HEADER: Nombre de archivo: RAG.md -->
<!-- NG-HEADER: Ubicación: docs/RAG.md -->
<!-- NG-HEADER: Descripción: Contrato vigente del RAG híbrido local y sus evaluaciones. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# RAG híbrido local

`KnowledgeSource` es la única autoridad de `role_scope`, `channel_scope`, visibilidad, estado, vigencia y `content_version`. Los chunks se filtran mediante join antes de rankear; `stale`, `disabled` y vencidos nunca se recuperan.

PostgreSQL combina pgvector `Vector(1536)` y full-text en español mediante fusión de rankings. Los embeddings provienen exclusivamente de Ollama `qwen3-embedding:4b`, solicitando 1536 dimensiones. Si el embedding falla, modo `vector` bloquea la búsqueda; modo `hybrid` puede conservar recuperación textual, pero el health de embeddings impide el rollout productivo.

El cache usa hash de consulta + rol efectivo + canal + versión máxima del corpus. El contexto respeta `RAG_CONTEXT_MAX_TOKENS`. Cada resultado devuelve:

```json
{
  "source_id": 12,
  "title": "Guía de cultivo",
  "chunk_index": 4,
  "page": 7,
  "score": 0.86,
  "content_version": 3
}
```

## Corpus v1

`docs/rag/corpus-manifest.v1.json` incluye fuentes sintéticas pública, cliente, proveedor, operativa y administrativa; añade centinelas stale, disabled y vencida. Las fuentes reales curadas iniciales son `docs/API_PRODUCTS.md` y `docs/PRODUCTS_UI.md`, sólo `colaborador|admin` en `web|websocket`; ninguna documentación interna se publica por Telegram.

```powershell
# Sólo valida manifiesto/rutas; no escribe ni requiere Ollama
.\.venv\Scripts\python.exe scripts\rag_corpus.py --synthetic --curated --dry-run

# Carga idempotente una vez aprobados Ollama y PostgreSQL
.\.venv\Scripts\python.exe scripts\rag_corpus.py --synthetic --curated

# Evalúa sin imprimir textos recuperados
.\.venv\Scripts\python.exe scripts\rag_corpus.py --evaluate
```

También admite `--cleanup-synthetic` y combinación con `--dry-run`.

## Gates

- cero recuperaciones fuera de rol/canal;
- cero stale, disabled o vencidas;
- recall@5 sintético ≥ 0,95;
- MRR sintético ≥ 0,90;
- citas completas 100 %;
- inclusión de la fuente esperada dentro del presupuesto de contexto 100 %;
- cero citas ante smalltalk irrelevante con el umbral operativo;
- separación de cache por rol/canal y versión 100 %.

El runner emite JSON agregado con rol, canal, intención, conteos y métricas; nunca incluye consultas completas, chunks ni respuestas. Una fuga retorna exit code distinto de cero y debe registrar un `ChatRolloutCheck` fallido.

## Estado

El 2026-08-17 se cargaron idempotentemente 10 fuentes en el entorno de desarrollo con Ollama local. Las fuentes curadas se dividen en chunks de hasta 1.000 caracteres para respetar `RAG_CONTEXT_MAX_TOKENS`; las sintéticas conservan un único fragmento centinela. La evaluación real aprobó scopes, vigencia, recall, MRR, citas y cache. Este resultado habilita desarrollo y smoke local, no constituye por sí solo autorización para activar tráfico productivo.
