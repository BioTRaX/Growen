<!-- NG-HEADER: Nombre de archivo: KNOWLEDGE_BASE.md -->
<!-- NG-HEADER: Ubicación: docs/KNOWLEDGE_BASE.md -->
<!-- NG-HEADER: Descripción: Documentación del sistema de gestión de Knowledge Base (Cerebro) -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Knowledge Base (Cerebro)

Sistema de gestión de documentos de conocimiento para el chatbot RAG de Growen.

**Estado**: ✅ **Implementado** - 2025-11-30

## Resumen

El sistema "Cerebro" permite gestionar documentos de conocimiento (PDF, Markdown, texto plano) que alimentan el sistema RAG del chatbot. La interfaz de administración facilita:

- Subir documentos a la carpeta `/Conocimientos`
- Indexar documentos individual o masivamente
- Ver estado de indexación y estadísticas
- Eliminar indexaciones sin borrar archivos

## Arquitectura

```
/Conocimientos/                    <- Carpeta de documentos (volumen Docker)
    ├── guia_productos.pdf
    ├── politicas_empresa.md
    └── notas_tecnicas.txt

services/rag/
    ├── ingest.py                  <- Motor de chunking + embeddings
    ├── service.py                 <- KnowledgeService (orquestador)
    └── pdf_parser.py              <- Extracción de texto de PDFs

services/routers/
    └── knowledge.py               <- API endpoints admin

frontend/src/pages/admin/
    └── KnowledgePage.tsx          <- UI de gestión
```

## Formatos Soportados

| Extensión | Descripción | Notas |
|-----------|-------------|-------|
| `.pdf` | Documentos PDF | Texto extraído con PyMuPDF. PDFs escaneados requieren OCR externo |
| `.md` | Markdown | Ideal para documentación técnica |
| `.txt` | Texto plano | Para notas simples |

## Uso desde el Panel Admin

### Acceder al Cerebro

1. Ir a **Admin** → **Cerebro** (o directamente `/admin/cerebro`)
2. Ver estadísticas generales en la parte superior

### Subir Documentos

1. Click en **📤 Subir archivo**
2. Seleccionar archivo (PDF, MD o TXT)
3. El archivo se guarda en `/Conocimientos`
4. Aparece como "Pendiente" en la tabla

### Indexar Documentos

#### Individual
- Click en ▶️ junto al archivo para indexar solo ese documento

#### Carpeta completa
- Click en **🔄 Indexar carpeta** para procesar todos los archivos pendientes

#### Re-indexación forzada
- Click en **⚡ Re-indexar (forzar)** para regenerar TODOS los embeddings
- Útil si se cambió la configuración de chunking

### Estados de Archivos

| Estado | Icono | Significado |
|--------|-------|-------------|
| Pendiente | ⏳ | Archivo nuevo, sin indexar |
| Indexado | ✅ | Procesado y en la base de datos |
| Modificado | ⚠️ | El archivo cambió desde la última indexación |

### Eliminar Indexación

- Click en 🗑️ junto al archivo indexado
- **Solo elimina de la DB**, el archivo permanece en `/Conocimientos`
- Útil para re-indexar desde cero un documento

## API Endpoints

Base: `/admin/knowledge`

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/files` | GET | Lista archivos con estado |
| `/upload` | POST | Sube archivo (multipart) |
| `/index` | POST | Dispara indexación |
| `/tasks/{id}` | GET | Estado de tarea |
| `/tasks` | GET | Lista tareas recientes |
| `/sources` | GET | Fuentes indexadas en DB |
| `/sources/{id}` | DELETE | Elimina fuente de DB |
| `/status` | GET | Estadísticas generales |
| `/files/{filename}` | DELETE | Elimina archivo + indexación |

### Ejemplo: Indexar un archivo

```bash
curl -X POST http://localhost:8000/admin/knowledge/index \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <token>" \
  -d '{"target": "manual.pdf", "force_reindex": false}'
```

Respuesta:
```json
{
  "task_id": "abc123def456",
  "status": "pending",
  "message": "Indexación de 'manual.pdf' iniciada"
}
```

### Ejemplo: Consultar estado

```bash
curl http://localhost:8000/admin/knowledge/status
```

Respuesta:
```json
{
  "total_sources": 5,
  "total_chunks": 127,
  "total_tokens_estimated": 31750,
  "files_in_folder": 6,
  "files_pending": 1,
  "files_need_reindex": 0,
  "last_indexed_at": "2025-11-30T10:30:00",
  "knowledge_path": "/app/Conocimientos",
  "tasks_running": 0
}
```

## Docker

La carpeta `/Conocimientos` está montada como volumen en el servicio `api`:

```yaml
# docker-compose.yml
services:
  api:
    volumes:
      - ./Conocimientos:/app/Conocimientos
```

Esto asegura que los documentos persistan entre reinicios de contenedores.

## Flujo de Indexación

```
Archivo en /Conocimientos
         │
         ▼
    KnowledgeService
         │
         ├─► Leer contenido (PDF: PyMuPDF, otros: texto)
         │
         ├─► Calcular hash SHA256
         │
         ├─► DocumentIngestor
         │        │
         │        ├─► RecursiveCharacterTextSplitter
         │        │   (chunk_size=1000, overlap=200)
         │        │
         │        └─► EmbeddingService
         │                │
         │                └─► OpenAI API (text-embedding-3-small)
         │                        │
         │                        ▼ 1536 dimensions
         │
         └─────────────► PostgreSQL (pgvector)
                              │
                              ├─► knowledge_sources (metadatos)
                              └─► knowledge_chunks (texto + vector)
```

## Detección de Cambios

El sistema usa hash SHA256 para detectar cambios:

1. **Hash igual** → Documento sin cambios, no re-indexa (ahorra tokens/costo)
2. **Hash diferente** → Documento modificado, elimina chunks viejos y re-indexa
3. **Flag `force_reindex`** → Ignora hash y re-indexa siempre

## Costos de OpenAI

El servicio usa `text-embedding-3-small`:

| Volumen | Costo |
|---------|-------|
| 1K tokens | $0.00002 |
| 100K tokens | $0.002 |
| 1M tokens | $0.02 |

Estimación aproximada: 1 token ≈ 4 caracteres

## Troubleshooting

### "El PDF no tiene texto extraíble"

El PDF puede ser un documento escaneado (imagen). Soluciones:
- Usar OCR externo (ej: `ocrmypdf`) para convertir a PDF con texto
- Subir versión con texto seleccionable

### "Error de conexión a OpenAI"

Verificar:
1. `OPENAI_API_KEY` configurada en `.env`
2. Créditos disponibles en la cuenta OpenAI
3. Conexión a internet desde el servidor

### "Archivo no aparece en la lista"

Verificar:
1. Extensión soportada (.pdf, .md, .txt)
2. No es archivo oculto (no empieza con `.`)
3. Está dentro de `/Conocimientos` (no en subcarpetas profundas)

### Limpiar todas las indexaciones

```sql
-- En PostgreSQL
TRUNCATE knowledge_chunks CASCADE;
TRUNCATE knowledge_sources CASCADE;
```

O desde la UI: eliminar cada fuente individualmente.

## Script CLI (Legado)

El script `scripts/index_docs.py` sigue disponible para uso avanzado:

```powershell
# Indexar carpeta por defecto
python scripts/index_docs.py

# Forzar re-indexación
python scripts/index_docs.py --force

# Ruta personalizada
python scripts/index_docs.py --path "ruta/a/docs"
```

**Nota**: Se recomienda usar la UI del Admin Panel para operaciones normales.

## Próximos Pasos

- [ ] Soporte para subcarpetas anidadas en `/Conocimientos`
- [ ] Vista previa de contenido de chunks
- [ ] Estadísticas de uso por documento (qué se consulta más)
- [ ] Integración con OCR para PDFs escaneados
- [ ] Drag & drop en la UI de upload

---

**Última actualización**: 2025-11-30  
**Relacionado**: [docs/RAG.md](RAG.md) - Arquitectura completa del sistema RAG

