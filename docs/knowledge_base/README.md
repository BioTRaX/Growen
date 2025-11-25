# Knowledge Base - Documentos de Conocimiento para RAG

Este directorio almacena documentos que serán indexados en la base de datos vectorial para el sistema RAG (Retrieval-Augmented Generation).

## Formatos Soportados

- **Markdown** (`.md`): Documentación técnica, guías, tutoriales
- **Texto plano** (`.txt`): Notas, especificaciones, logs procesados

## Estructura Recomendada

```
docs/knowledge_base/
├── documentacion/          # Documentación general del proyecto
│   ├── AGENTS.md
│   ├── README.md
│   └── ...
├── apis/                   # Documentación de APIs
│   ├── API_MARKET.md
│   ├── API_PRODUCTS.md
│   └── ...
├── guias/                  # Guías de uso y tutoriales
│   └── ...
└── notas/                  # Notas de desarrollo, decisiones
    └── ...
```

## Indexación

### Primera vez (indexar todos los documentos)

```powershell
python scripts/index_docs.py
```

### Forzar reindexación (actualizar documentos modificados)

```powershell
python scripts/index_docs.py --force
```

### Ruta personalizada

```powershell
python scripts/index_docs.py --path "ruta/a/otros/docs"
```

## Proceso de Indexación

1. **Escaneo**: El script busca todos los archivos `.md` y `.txt` recursivamente
2. **Chunking**: Cada documento se divide en fragmentos de ~1000 caracteres (overlap 200)
3. **Embeddings**: Se generan embeddings para cada chunk usando OpenAI `text-embedding-3-small`
4. **Almacenamiento**: Los chunks y vectores se guardan en PostgreSQL con pgvector

## Detección de Cambios

El sistema calcula un hash SHA256 del contenido de cada documento:

- Si el **hash es igual**: Se reutiliza la versión existente (sin reindexar)
- Si el **hash cambió**: Se elimina la versión anterior y se reindexan los chunks
- Flag `--force`: Fuerza reindexación incluso si el hash no cambió

## Costos Estimados

Modelo: `text-embedding-3-small` ($0.02 por 1M tokens)

| Tamaño documento | Tokens aprox. | Costo aprox. |
|------------------|---------------|--------------|
| 1 KB texto       | ~250 tokens   | $0.000005    |
| 10 KB texto      | ~2,500 tokens | $0.00005     |
| 100 KB texto     | ~25,000 tokens| $0.0005      |
| 1 MB texto       | ~250,000 tokens| $0.005      |

El script muestra el costo estimado al finalizar.

## Logs

Los logs de indexación se muestran en consola. Para guardarlos:

```powershell
python scripts/index_docs.py > logs/indexing_$(Get-Date -Format 'yyyy-MM-dd_HHmmss').log 2>&1
```

## Base de Datos

Los documentos indexados se almacenan en:

- **Tabla `knowledge_sources`**: Metadatos del documento (filename, hash, fecha)
- **Tabla `knowledge_chunks`**: Chunks de texto con sus embeddings (vector 1536 dims)

Ver estructura completa en `db/models.py`.

## Ejemplo de Uso

```powershell
# 1. Agregar documentos a esta carpeta
Copy-Item "README.md" "docs/knowledge_base/documentacion/"
Copy-Item "docs/API_MARKET.md" "docs/knowledge_base/apis/"

# 2. Indexar
python scripts/index_docs.py

# Salida esperada:
# ================================================================================
# INDEXACIÓN DE DOCUMENTOS RAG
# ================================================================================
# Directorio: C:\Proyectos\NiceGrow\Growen\docs\knowledge_base
# ...
# 📚 Encontrados 2 documentos
# ✓ Encontrado: documentacion/README.md (15234 caracteres)
# ✓ Encontrado: apis/API_MARKET.md (8432 caracteres)
# ...
# ================================================================================
# RESUMEN DE INDEXACIÓN
# ================================================================================
# Total documentos procesados: 2
# Documentos exitosos: 2
# Total chunks creados: 23
# Tokens estimados: ~5,916
# Costo estimado: ~$0.000118 USD
# ================================================================================
# ✅ Indexación completada exitosamente
```

## Requisitos

- PostgreSQL con extensión `pgvector` instalada
- Variable de entorno `OPENAI_API_KEY` configurada
- Paquetes Python: `pgvector`, `langchain-text-splitters`, `tiktoken`

Ver `requirements.txt` y `docs/DEVELOPMENT_WORKFLOW.md` para más detalles.
