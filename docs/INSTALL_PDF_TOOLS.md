# Instalación de Herramientas PDF

Guía para instalar las herramientas necesarias para el servicio `pdf_import` en Windows.

## Herramientas Requeridas

| Herramienta | Uso | Requerido |
|-------------|-----|-----------|
| **QPDF** | Manipulación de PDFs | ✅ Sí |
| **Tesseract** | OCR de texto | ✅ Sí |
| **Ghostscript** | Renderizado de PDFs | ✅ Sí |
| **ocrmypdf** | Pipeline OCR (Python) | ✅ Sí |

---

## Instalación en Windows

### QPDF

1. Descargar desde: https://github.com/qpdf/qpdf/releases
2. Ejecutar el instalador `.exe` o `.msi`
3. Por defecto se instala en: `C:\Program Files\qpdf X.X.X\`

**Opcional**: Agregar al PATH:
```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\qpdf 12.2.0\bin", "User")
```

### Tesseract

1. Descargar desde: https://github.com/UB-Mannheim/tesseract/wiki
2. Ejecutar el instalador
3. **Importante**: Durante la instalación, seleccionar idioma "Spanish"
4. Por defecto se instala en: `C:\Program Files\Tesseract-OCR\`

### Ghostscript

1. Descargar desde: https://ghostscript.com/releases/gsdnld.html
2. Seleccionar versión "Ghostscript AGPL Release" para Windows 64-bit
3. Por defecto se instala en: `C:\Program Files\gs\gsX.XX.X\`

### ocrmypdf (Python)

```bash
pip install ocrmypdf
```

---

## Verificación

Desde la UI, navegar a **Admin → Servicios** y verificar que el servicio "Importador PDF (OCR)" muestre:
- Estado: `running`
- Salud: `OK` (no `FALLA`)
- Sin hints de instalación

También podés verificar desde la API:
```bash
curl http://127.0.0.1:8000/health/service/pdf_import
```

Debería devolver:
```json
{
  "service": "pdf_import",
  "ok": true,
  "deps": {
    "ocrmypdf": true,
    "tesseract": true,
    "qpdf": true,
    "ghostscript": true
  },
  "hints": []
}
```

---

## Rutas de Detección Automática

El sistema busca automáticamente en estas ubicaciones de Windows:

- **QPDF**: `C:\Program Files\qpdf*\bin\qpdf.exe`
- **Tesseract**: `C:\Program Files\Tesseract-OCR\tesseract.exe`
- **Ghostscript**: `C:\Program Files\gs\gs*\bin\gswin64c.exe`

No es necesario agregar al PATH si están instaladas en ubicaciones estándar.
