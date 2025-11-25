# NG-HEADER: Nombre de archivo: test_document.md
# NG-HEADER: Ubicación: docs/knowledge_base/test_document.md
# NG-HEADER: Descripción: Documento de prueba para testing de ingesta RAG
# NG-HEADER: Lineamientos: Ver AGENTS.md

# Documento de Prueba para RAG

Este es un documento de prueba para validar el sistema de ingesta de documentos RAG.

## Objetivo

Verificar que el sistema puede:

1. **Leer archivos** desde el directorio `docs/knowledge_base/`
2. **Dividir texto** en chunks usando RecursiveCharacterTextSplitter
3. **Generar embeddings** para cada chunk usando OpenAI text-embedding-3-small
4. **Almacenar vectores** en PostgreSQL con pgvector

## Contenido de Ejemplo

El sistema RAG (Retrieval-Augmented Generation) permite a los modelos de lenguaje acceder a información externa específica del dominio. En lugar de depender únicamente del conocimiento incorporado durante el entrenamiento, el modelo puede consultar una base de datos vectorial para recuperar contexto relevante.

### Ventajas de RAG

- **Actualización dinámica**: El conocimiento se puede actualizar sin reentrenar el modelo
- **Fuentes específicas**: Acceso a documentación interna, políticas, datos propietarios
- **Reducción de alucinaciones**: El modelo se basa en información verificable
- **Trazabilidad**: Se puede rastrear de dónde proviene cada respuesta

### Arquitectura Técnica

El sistema consta de tres componentes principales:

1. **Ingesta**: Procesa documentos fuente y genera embeddings vectoriales
2. **Almacenamiento**: Base de datos PostgreSQL con extensión pgvector
3. **Recuperación**: Búsqueda por similitud coseno para encontrar chunks relevantes

### Configuración de Chunking

Los documentos se dividen en fragmentos con los siguientes parámetros:

- **chunk_size**: 1000 caracteres (aproximadamente 250 tokens)
- **chunk_overlap**: 200 caracteres (para mantener contexto entre chunks)
- **separadores**: Párrafos, líneas, oraciones, palabras, caracteres

Este overlap garantiza que conceptos que cruzan límites de chunks no se pierdan.

### Modelo de Embeddings

Se utiliza **text-embedding-3-small** de OpenAI:

- Dimensiones: 1536
- Costo: $0.02 por 1M tokens
- Velocidad: ~2000 chunks por minuto en batch mode
- Calidad: Excelente para búsqueda semántica en español

### Proceso de Indexación

```python
# Pseudocódigo del flujo de indexación
for document in knowledge_base:
    # 1. Calcular hash para detectar cambios
    hash = sha256(document.content)
    
    # 2. Crear o actualizar fuente
    source = get_or_create_source(filename, hash)
    
    # 3. Dividir en chunks
    chunks = text_splitter.split_text(document.content)
    
    # 4. Generar embeddings
    embeddings = openai.embeddings.create(input=chunks)
    
    # 5. Guardar en PostgreSQL
    for chunk, embedding in zip(chunks, embeddings):
        save_to_db(source_id, chunk, embedding)
```

### Consultas de Similitud

Una vez indexados los documentos, se pueden hacer consultas semánticas:

```sql
-- Buscar los 5 chunks más similares a una pregunta
SELECT content, 1 - (embedding <=> query_embedding) AS similarity
FROM knowledge_chunks
ORDER BY embedding <=> query_embedding
LIMIT 5;
```

El operador `<=>` de pgvector calcula la distancia coseno entre vectores.

## Testing

Este documento debería generar aproximadamente 8-10 chunks al ser procesado por el script `scripts/index_docs.py`.

Para verificar:

```powershell
# 1. Indexar este documento
python scripts/index_docs.py

# 2. Consultar base de datos
docker exec growen-postgres psql -U growen -d growen -c "
  SELECT filename, COUNT(*) as chunks
  FROM knowledge_sources s
  JOIN knowledge_chunks c ON c.source_id = s.id
  GROUP BY filename;
"
```

## Próximos Pasos

1. Implementar endpoint de búsqueda semántica en la API
2. Integrar recuperación RAG en el chatbot
3. Agregar reranking para mejorar relevancia
4. Implementar cache de embeddings frecuentes
5. Monitorear costos de OpenAI API

---

Documento generado para testing de sistema RAG - Etapa 2.
