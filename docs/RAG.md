<!-- NG-HEADER: Nombre de archivo: RAG.md -->
<!-- NG-HEADER: Ubicación: docs/RAG.md -->
<!-- NG-HEADER: Descripción: Documentación completa del sistema RAG (Retrieval-Augmented Generation) - Etapa 2 -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# RAG - Retrieval-Augmented Generation

Sistema de recuperación de información con búsqueda vectorial para el chatbot de Growen.

**Estado**: ✅ **Infraestructura + Motor de Ingesta Completos** (Etapa 2) - 2025-11-25

## Resumen

El sistema RAG permite al chatbot acceder a documentación interna mediante búsqueda semántica, evitando alucinaciones y proporcionando respuestas basadas en fuentes verificables.

### Componentes Implementados

1. **Base de datos vectorial**: PostgreSQL 17 + pgvector 0.8.1
2. **Modelos de datos**: `KnowledgeSource` (documentos) + `KnowledgeChunk` (fragmentos vectorizados)
3. **Servicio de embeddings**: `ai/embeddings.py` con AsyncOpenAI
4. **Motor de ingesta**: `services/rag/ingest.py` con chunking inteligente
5. **Script de carga**: `scripts/index_docs.py` para indexación batch

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    Flujo de Indexación                       │
└─────────────────────────────────────────────────────────────┘
                              
docs/knowledge_base/*.md
         │
         ▼
  scripts/index_docs.py
         │
         ├─► DocumentIngestor (services/rag/ingest.py)
         │        │
         │        ├─► RecursiveCharacterTextSplitter
         │        │   (chunk_size=1000, overlap=200)
         │        │
         │        └─► EmbeddingService (ai/embeddings.py)
         │                │
         │                └─► OpenAI API (text-embedding-3-small)
         │                        │ 1536 dimensions
         │                        ▼
         └─────────────► PostgreSQL (pgvector)
                              │
                              ├─► knowledge_sources
                              │   (filename, hash, meta_json)
                              │
                              └─► knowledge_chunks
                                  (content, embedding, metadata)

┌─────────────────────────────────────────────────────────────┐
│                 Flujo de Búsqueda (Futuro)                   │
└─────────────────────────────────────────────────────────────┘

User Question
     │
     ▼
ChatEndpoint (/api/v1/chat/message)
     │
     ├─► EmbeddingService.generate_embedding(question)
     │
     └─► Similarity Search (PostgreSQL pgvector)
           │  SELECT ... ORDER BY embedding <=> query_vector
           │  LIMIT 5
           ▼
     Top K Chunks (contexto relevante)
           │
           └─► OpenAI Chat Completion
                 (system prompt + retrieved context + question)
                       │
                       ▼
                   Response
```

## Base de Datos

### Extensión pgvector

```sql
-- Verificar versión instalada
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
-- Resultado esperado: vector | 0.8.1
```

### Tablas

#### knowledge_sources

Almacena metadatos de documentos fuente:

| Columna      | Tipo     | Descripción                                      |
|--------------|----------|--------------------------------------------------|
| id           | Integer  | Primary Key                                      |
| filename     | String   | Nombre/ruta del archivo (ej: "README.md")        |
| hash         | String   | SHA256 del contenido (detecta cambios)           |
| created_at   | DateTime | Timestamp de creación                            |
| meta_json    | JSONB    | Metadatos extensibles (size, extension, etc.)    |

#### knowledge_chunks

Fragmentos de texto con vectores:

| Columna         | Tipo        | Descripción                                  |
|-----------------|-------------|----------------------------------------------|
| id              | Integer     | Primary Key                                  |
| source_id       | Integer     | FK → knowledge_sources.id (CASCADE)          |
| chunk_index     | Integer     | Orden del fragmento en el documento          |
| content         | Text        | Texto plano del fragmento                    |
| embedding       | Vector(1536)| Vector de embeddings (OpenAI)                |
| chunk_metadata  | JSONB       | Metadatos del chunk (length, page, etc.)     |

### Índices

**Actual**: Solo índices automáticos (PK, FK).

**Futuro** (cuando haya >10K vectores):
```sql
-- Índice IVFFlat para búsqueda aproximada rápida
CREATE INDEX ON knowledge_chunks 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);
```

## Servicio de Embeddings

**Archivo**: `ai/embeddings.py`

### EmbeddingService

Cliente asíncrono para OpenAI Embeddings API.

**Modelo**: `text-embedding-3-small`
- **Dimensiones**: 1536
- **Costo**: $0.02 por 1M tokens
- **Velocidad**: ~2000 chunks/min en batch mode

#### Métodos

```python
from ai.embeddings import get_embedding_service

service = get_embedding_service()

# Generar embedding para un texto
embedding = await service.generate_embedding("¿Cuál es el precio del producto X?")
# → List[float] con 1536 valores

# Procesar batch (hasta 2048 textos, automáticamente dividido en batches de 100)
embeddings = await service.generate_embeddings_batch(
    texts=["texto 1", "texto 2", "texto 3", ...],
    batch_size=100
)
# → List[List[float]]
```

#### Validaciones

- ✅ Texto vacío → `ValueError`
- ✅ Dimensiones incorrectas → `ValueError`
- ✅ Error API → `Exception` con mensaje descriptivo
- ✅ Singleton pattern para reutilización de cliente

## Motor de Ingesta

**Archivo**: `services/rag/ingest.py`

### DocumentIngestor

Procesa documentos completos: chunking + embeddings + almacenamiento.

#### Configuración de Chunking

```python
RecursiveCharacterTextSplitter(
    chunk_size=1000,          # Caracteres (~250 tokens)
    chunk_overlap=200,        # Overlap para mantener contexto
    separators=[
        "\n\n",  # Párrafos (preferido)
        "\n",    # Líneas
        ". ",    # Oraciones
        " ",     # Palabras
        "",      # Caracteres (último recurso)
    ]
)
```

**Justificación**:
- 1000 chars ≈ 250 tokens → chunks pequeños para precisión
- Overlap 200 chars → conceptos que cruzan límites no se pierden
- Separadores jerárquicos → prioriza divisiones naturales (párrafos > oraciones)

#### Detección de Cambios

Sistema inteligente basado en hash SHA256:

1. **Hash igual** → Reutiliza vectores existentes (ahorro de costo)
2. **Hash diferente** → Elimina chunks antiguos (CASCADE) y reindexar
3. **Flag `--force`** → Reindexar incluso si hash igual (útil para testing)

```python
from services.rag.ingest import DocumentIngestor
from db.session import get_session

ingestor = DocumentIngestor()

async for session in get_session():
    result = await ingestor.ingest_document(
        filename="manual_producto_x.md",
        content=texto_completo,
        session=session,
        meta_json={"source": "supplier_docs", "product_id": 123},
        force_reindex=False
    )
    await session.commit()
    break

# Resultado:
# {
#     "source_id": 5,
#     "chunks_created": 12,
#     "total_tokens_estimated": 3000
# }
```

#### Batch Processing

```python
documents = [
    {"filename": "doc1.md", "content": "...", "meta_json": {...}},
    {"filename": "doc2.txt", "content": "...", "meta_json": {...}},
]

result = await ingestor.ingest_documents_batch(
    documents=documents,
    session=session,
    force_reindex=False
)

# Resultado:
# {
#     "total_documents": 2,
#     "total_chunks": 18,
#     "failed_documents": [],
#     "success_count": 2
# }
```

**Manejo de errores**:
- Si un documento falla, se loggea y continúa con los siguientes
- La transacción se hace commit solo si **todos** los chunks procesan exitosamente
- Los fallos se reportan en `failed_documents`

## Script de Carga

**Archivo**: `scripts/index_docs.py`

### Uso

```powershell
# Indexar todos los documentos en docs/knowledge_base/
python scripts/index_docs.py

# Forzar reindexación (actualizar documentos modificados)
python scripts/index_docs.py --force

# Ruta personalizada
python scripts/index_docs.py --path "ruta/a/otros/docs"
```

### Salida de Ejemplo

```
================================================================================
INDEXACIÓN DE DOCUMENTOS RAG
================================================================================
Directorio: C:\Proyectos\NiceGrow\Growen\docs\knowledge_base
Forzar reindexación: False
OpenAI API Key configurada: ✓

Escaneando directorio de conocimiento...
✓ Encontrado: README.md (4091 caracteres)
✓ Encontrado: test_document.md (4006 caracteres)
📚 Encontrados 2 documentos

Iniciando ingesta de 'README.md' (4091 caracteres)
Creada fuente de conocimiento: 'README.md' (ID: 2, hash: a874be41...)
Documento dividido en 6 chunks
Generando embeddings para 6 chunks...
✅ Ingesta completada: 'README.md' -> 6 chunks (~1147 tokens estimados)

Iniciando ingesta de 'test_document.md' (4006 caracteres)
Creada fuente de conocimiento: 'test_document.md' (ID: 3, hash: 8ce57dbf...)
Documento dividido en 5 chunks
Generando embeddings para 5 chunks...
✅ Ingesta completada: 'test_document.md' -> 5 chunks (~1009 tokens estimados)

================================================================================
RESUMEN DE INDEXACIÓN
================================================================================
Total documentos procesados: 2
Documentos exitosos: 2
Documentos fallidos: 0
Total chunks creados: 11

Tokens estimados: ~2,023
Costo estimado: ~$0.000040 USD
================================================================================
✅ Indexación completada exitosamente
```

### Formatos Soportados

- `.md` (Markdown): Documentación técnica, tutoriales, guías
- `.txt` (Texto plano): Notas, especificaciones

### Prerequisitos

1. **PostgreSQL corriendo** con extensión pgvector
2. **OPENAI_API_KEY** configurada en `.env`
3. **Dependencias instaladas**:
   ```powershell
   pip install pgvector langchain-text-splitters tiktoken
   ```

## Consultas PostgreSQL Útiles

### Estadísticas por documento

```sql
SELECT 
    s.filename,
    COUNT(c.id) as chunks,
    AVG(LENGTH(c.content))::int as avg_chunk_size,
    pg_size_pretty(pg_total_relation_size('knowledge_chunks')) as table_size
FROM knowledge_sources s
JOIN knowledge_chunks c ON c.source_id = s.id
GROUP BY s.filename
ORDER BY chunks DESC;
```

### Ver chunks de un documento

```sql
SELECT 
    chunk_index,
    LENGTH(content) as size,
    SUBSTRING(content, 1, 100) || '...' as preview
FROM knowledge_chunks
WHERE source_id = 2
ORDER BY chunk_index;
```

### Búsqueda de similitud (ejemplo básico)

```sql
-- Suponiendo que tienes un query_vector ya generado
SELECT 
    c.id,
    c.content,
    s.filename,
    1 - (c.embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON s.id = c.source_id
ORDER BY c.embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;
```

**Operadores pgvector**:
- `<=>` : Distancia coseno (0 = idénticos, 2 = opuestos)
- `<->` : Distancia euclidiana
- `<#>` : Producto interno negativo

## Costos de OpenAI

### Modelo: text-embedding-3-small

| Volumen        | Costo           |
|----------------|-----------------|
| 1K tokens      | $0.00002        |
| 10K tokens     | $0.0002         |
| 100K tokens    | $0.002          |
| 1M tokens      | $0.02           |

### Estimaciones por documento

| Tamaño documento | Tokens aprox. | Costo aprox.  |
|------------------|---------------|---------------|
| 1 KB texto       | ~250          | $0.000005     |
| 10 KB texto      | ~2,500        | $0.00005      |
| 100 KB texto     | ~25,000       | $0.0005       |
| 1 MB texto       | ~250,000      | $0.005        |

**Nota**: El script `index_docs.py` muestra el costo estimado al finalizar.

## Testing Actual

### Resultados de Validación

✅ **Infraestructura**:
- PostgreSQL 17 con pgvector 0.8.1 funcionando
- Extensión habilitada correctamente
- Tablas creadas sin errores

✅ **Indexación**:
- 2 documentos procesados (README.md + test_document.md)
- 11 chunks generados (6 + 5)
- ~2K tokens procesados
- Costo real: $0.00004 USD

✅ **Base de datos**:
```sql
-- Verificado con:
SELECT COUNT(*) FROM knowledge_chunks WHERE embedding IS NOT NULL;
-- Resultado: 11 chunks con embeddings válidos
```

✅ **Detección de cambios**:
```powershell
# Segunda ejecución (sin --force) reutilizó vectores existentes:
python scripts/index_docs.py
# Salida: "Documento 'README.md' ya existe con mismo contenido (hash: a874be41...)"
```

## Próximos Pasos (Etapa 3+)

### 1. Endpoint de Búsqueda

**Archivo**: `services/routers/rag.py` (nuevo)

```python
from fastapi import APIRouter, Depends
from ai.embeddings import get_embedding_service
from sqlalchemy import select

router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])

@router.post("/search")
async def search_knowledge(
    query: str,
    top_k: int = 5,
    session: AsyncSession = Depends(get_session)
):
    """Búsqueda semántica en base de conocimiento."""
    # 1. Generar embedding de la pregunta
    embedding_service = get_embedding_service()
    query_vector = await embedding_service.generate_embedding(query)
    
    # 2. Búsqueda por similitud
    stmt = select(KnowledgeChunk).order_by(
        KnowledgeChunk.embedding.cosine_distance(query_vector)
    ).limit(top_k)
    
    results = await session.execute(stmt)
    chunks = results.scalars().all()
    
    # 3. Retornar con metadatos
    return {
        "query": query,
        "results": [
            {
                "content": chunk.content,
                "source": chunk.source.filename,
                "chunk_index": chunk.chunk_index,
                "similarity": 1 - chunk.embedding.cosine_distance(query_vector)
            }
            for chunk in chunks
        ]
    }
```

### 2. Integración con Chatbot

**Flujo sugerido**:

1. Usuario envía pregunta al chatbot
2. Sistema detecta si requiere información interna (policy/NLU)
3. Si sí: ejecutar búsqueda RAG → obtener top 3-5 chunks
4. Inyectar chunks en system prompt:
   ```
   Contexto relevante de documentación interna:
   ---
   {chunk_1}
   ---
   {chunk_2}
   ---
   Responde basándote SOLO en el contexto anterior.
   ```
5. Enviar prompt completo a OpenAI Chat
6. Retornar respuesta con citas de fuentes

### 3. Reranking (Mejora de Precisión)

Problema: La similitud coseno puede traer resultados parcialmente relevantes.

Solución: Usar modelo de reranking (ej: `cross-encoder/ms-marco-MiniLM-L-12-v2`):

```python
# Después de búsqueda inicial (top 20)
from sentence_transformers import CrossEncoder

reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-12-v2')
pairs = [(query, chunk.content) for chunk in top_20_chunks]
scores = reranker.predict(pairs)

# Reordenar por score del cross-encoder
reranked = sorted(zip(top_20_chunks, scores), key=lambda x: x[1], reverse=True)
final_top_5 = [chunk for chunk, score in reranked[:5]]
```

### 4. Monitoreo y Observabilidad

Métricas a trackear:

- **Latencia**: p50/p95/p99 de búsquedas
- **Costos**: Tokens consumidos por día/mes
- **Cache hit ratio**: Preguntas repetidas
- **Top queries**: Qué documentos se consultan más
- **Relevancia**: Feedback del usuario (útil/no útil)

### 5. Optimizaciones Futuras

- **Índice IVFFlat**: Cuando haya >10K vectores
- **Hybrid search**: Combinar búsqueda vectorial + BM25 (texto)
- **Metadata filtering**: Filtrar por `product_id`, `category`, etc.
- **Chunk overlap dinámico**: Ajustar según tipo de documento
- **Múltiples embeddings**: Probar `text-embedding-3-large` (3072 dims) para mejor calidad

## Troubleshooting

### Error: "psycopg cannot use ProactorEventLoop"

**Solución**: Agregar al inicio del script:
```python
import sys
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

### Error: "OPENAI_API_KEY no configurada"

**Solución**: Verificar `.env`:
```bash
OPENAI_API_KEY=sk-proj-...
```

### Error: "No such table: knowledge_sources"

**Solución**: Aplicar migración:
```powershell
alembic upgrade head
```

### Chunks muy pequeños/grandes

**Solución**: Ajustar `chunk_size` en `DocumentIngestor`:
```python
self.text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,  # Aumentar para chunks más grandes
    chunk_overlap=300
)
```

## Referencias

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [OpenAI Embeddings API](https://platform.openai.com/docs/guides/embeddings)
- [LangChain Text Splitters](https://python.langchain.com/docs/modules/data_connection/document_transformers/)
- [RAG Best Practices](https://www.pinecone.io/learn/retrieval-augmented-generation/)

---

**Última actualización**: 2025-11-25  
**Mantenedor**: Backend Team  
**Estado**: ✅ Infraestructura completa, listo para Etapa 3 (búsqueda + integración chatbot)
