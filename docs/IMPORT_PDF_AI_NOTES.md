<!-- NG-HEADER: Nombre de archivo: IMPORT_PDF_AI_NOTES.md -->
<!-- NG-HEADER: Ubicación: docs/IMPORT_PDF_AI_NOTES.md -->
<!-- NG-HEADER: Descripción: Backlog y próximas mejoras para IA en importación de remitos -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Backlog IA Import Remitos (Futuras Iteraciones)

## Próximas mejoras propuestas
1. Cálculo de confianza "clásica" (heurística):
   - Métrica basada en proporción de líneas con SKU detectado, densidad de dígitos en título y consistencia qty>0.
   - Disparar IA también si `classic_confidence < threshold` aunque existan líneas.
2. Prompt enriquecido:
   - Incluir encabezado detectado y primeras N líneas tabulares del parser bruto.
   - Pasar ejemplos de formato para robustecer JSON estricto.
3. Fusión inteligente (fase 2):
   - Permitir agregar sólo líneas nuevas por SKU/título que IA descubra y parser no.
   - Estrategia fuzzy SKU: si IA detecta título cercano >90 fuzz y sin SKU, reutilizar SKU de catálogo.
4. Métricas y observabilidad:
   - Registrar tokens usados (input/output) cuando OpenAI lo exponga en response.
   - Endpoint `/admin/services/pdf_import/ai_stats` con agregados (llamadas, tasa éxito, líneas añadidas, latencia media).
5. Hardening:
   - Sanitizar big numbers fuera de rango (qty>5000 o unit_cost>1e6) -> descartar.
   - Limitar longitud acumulada de títulos IA (p.e. 8k chars) para proteger DB.
6. Alternativa de modelo offline:
   - Evaluar `ollama` + modelo local (ej. llama3.1) para entornos sin Internet.
7. Tests adicionales:
   - Caso JSON corrupto (inyectar respuesta malformada simulada).
   - Caso mezcla de líneas clásicas + IA.

## Notas de diseño
- IA nunca debe degradar la precisión introduciendo líneas con baja confianza (< umbral) ni sobrescribir decisiones humanas posteriores.
- Se preferirá métrica simple de confianza antes que pipeline complejo de validación estadística en fase 2.

## Mantenimiento
- Revisar trimestralmente librerías OCR/tabla (pdfplumber, camelot) y ajustar heurísticas para reducir necesidad de IA.
