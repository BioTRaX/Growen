<!-- NG-HEADER: Nombre de archivo: IMPORT_PDF.md -->
<!-- NG-HEADER: Ubicación: docs/IMPORT_PDF.md -->
<!-- NG-HEADER: Descripción: Flujo de importación de PDF con OCR -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Importación de PDF

El proceso de importación de PDF sigue el siguiente pipeline:
1. `pdfplumber` extrae el texto cuando es posible.
2. `Camelot` procesa tablas embebidas.
3. Si el PDF no contiene texto o se fuerza el proceso, se ejecuta OCR con `ocrmypdf`.

## Flags relevantes
- `debug`: genera información adicional para diagnósticos.
- `force_ocr`: fuerza el uso de OCR incluso si el PDF tiene texto.

## Política de borrador vacío
Si el OCR no logra extraer contenido útil, se genera un borrador vacío para revisión manual.

## Respuesta
Toda respuesta incluye un `correlation_id` para trazabilidad.

## Tips de diagnóstico
- Revisar logs generados en modo `debug`.
- Verificar dependencias externas: Tesseract, Ghostscript y Poppler.
- Utilizar PDFs de ejemplo para pruebas controladas.

