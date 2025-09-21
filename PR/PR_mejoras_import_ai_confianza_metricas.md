<!-- NG-HEADER: Nombre de archivo: PR_mejoras_import_ai_confianza_metricas.md -->
<!-- NG-HEADER: Ubicación: PR/PR_mejoras_import_ai_confianza_metricas.md -->
<!-- NG-HEADER: Descripción: Pull Request - mejoras fallback IA importación PDF, confianza y métricas -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# PR: Observabilidad y Robustez en Importación de Remitos (Fallback IA + Confianza + Métricas)

## Resumen
Este PR introduce una segunda fase sólida para el pipeline de importación de remitos (PDF) agregando:
- Heurística `classic_confidence` refinada (agrega densidad numérica y sanitización de outliers) para evaluar calidad de extracción clásica.
- Fallback IA ampliado: ahora se dispara cuando no hay líneas o cuando la confianza clásica es baja.
- Registro estructurado de la confianza y eventos IA en `ImportLog`.
- Endpoint de métricas agregadas para monitoreo de performance del parser y la IA.
- Tests adicionales que garantizan merge correcto de líneas y estabilidad de la heurística.
- Documentación extendida en `docs/IMPORT_PDF.md` y entradas en `CHANGELOG.md`.

## Motivación
Mejorar precisión y trazabilidad: reducir riesgo de importaciones silenciosamente pobres (pocas líneas válidas) y habilitar un circuito de mejora continua observando métricas concretas sobre la calidad del parsing y el valor agregado de la IA.

## Cambios Clave
### 1. Heurística de Confianza (`classic_confidence`)
- Componentes: SKU presence, qty>0, cost>0, diversidad de SKU, densidad numérica.
- Sanitización de outliers (cantidad >10k clamped, costo unitario >10M excluido) para evitar distorsiones.
- Valor registrado por importación en `ImportLog` (`stage=heuristic`, `event=classic_confidence`).

### 2. Fallback IA (Fase 2)
- Trigger previo: cero líneas.
- Nuevo trigger: `classic_confidence < IMPORT_AI_CLASSIC_MIN_CONFIDENCE`.
- Prompt enriquecido con líneas detectadas y valor de confianza.
- Merge no destructivo: sólo agrega líneas IA con `confidence >= IMPORT_AI_MIN_CONFIDENCE` sin duplicar SKU.

### 3. Métricas Agregadas
Nuevo endpoint: `GET /admin/services/pdf_import/metrics`.
Devuelve (global y últimas 24h):
- total_imports
- avg_classic_confidence
- ai_invocations / ai_success / ai_success_rate
- ai_lines_added

### 4. Logging y Observabilidad
Eventos IA (`ai:request`, `ai:ok`, `ai:merged`, `ai:no_data`, `ai:skip_disabled`, `ai:exception`) y heurística listos para análisis per compra.

### 5. Documentación
`docs/IMPORT_PDF.md` actualizado con:
- Densidad numérica
- Sanitización de outliers
- Ejemplo endpoint métricas
- Detalles de logging de confianza

### 6. Tests
- `test_classic_confidence.py`: ajustado umbral alto para nueva ponderación.
- `test_ai_fallback_merge.py`: verifica merge, duplicados y confidencias.
- `test_pdf_import_metrics.py`: smoke del endpoint de métricas.
- Suite total: 65 tests pasando.

## Variables de Entorno Nuevas / Relevantes
| Variable | Descripción |
|----------|-------------|
| IMPORT_AI_CLASSIC_MIN_CONFIDENCE | Umbral para disparar IA con líneas presentes |
| IMPORT_AI_MIN_CONFIDENCE | Umbral por línea IA para merge |
| IMPORT_AI_ENABLED | Habilita fallback IA |

(Otras ya documentadas: modelo, timeout, retries, API key.)

## Riesgos y Mitigación
| Riesgo | Mitigación |
|--------|-----------|
| Sesgos de heurística | Métricas agregadas para recalibrar pesos | 
| IA agrega ruido | Umbral `IMPORT_AI_MIN_CONFIDENCE` y no reemplazo de líneas clásicas |
| Outliers distorsionan confianza | Sanitización y clamps |
| Falta de datos históricos | Registro estructurado de cada importación |

## Checklist
- [x] Código listo y probado (65 tests OK)
- [x] `ImportLog` registra `classic_confidence`
- [x] Endpoint métricas funcionando
- [x] Documentación y CHANGELOG actualizados
- [x] NG-HEADER en archivos nuevos
- [ ] Revisión de pares pendiente

## Ejemplo Respuesta Métricas
```json
{
  "total_imports": 42,
  "avg_classic_confidence": 0.72,
  "ai_invocations": 5,
  "ai_success": 4,
  "ai_success_rate": 0.8,
  "ai_lines_added": 11,
  "last_24h": {
    "avg_classic_confidence": 0.70,
    "ai_invocations": 2,
    "ai_success": 2,
    "ai_success_rate": 1.0,
    "ai_lines_added": 5
  }
}
```

## Próximos Pasos (Opcionales)
- Ajustar pesos de la heurística con datos reales (monitor 2–4 semanas).
- Alertas automáticas si `avg_classic_confidence` cae > X% día/día.
- Registro de razones de descarte de líneas IA (motivo agregado más granular).
- Endpoint histórico (serie temporal) para dashboards.

## Conclusión
El pipeline gana resiliencia (fallback IA contextual), transparencia (logging detallado) y capacidad de evolución basada en métricas. Se sientan bases para optimizar pesos y evaluar impacto real de la IA.

---
_Indicá cualquier comentario o ajuste y preparo versión final._
