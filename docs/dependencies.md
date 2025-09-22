<!-- NG-HEADER: Nombre de archivo: dependencies.md -->
<!-- NG-HEADER: Ubicación: docs/dependencies.md -->
<!-- NG-HEADER: Descripción: Dependencias obligatorias y opcionales, pasos de instalación y verificación -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
Dependencies and Setup
======================

Backend (Python)
- Core runtime: fastapi, uvicorn, sqlalchemy, alembic, psycopg[binary], httpx
- Core support: pydantic-settings, passlib[argon2], python-multipart, pandas, openpyxl, Pillow
- Performance / misc: slowapi, rapidfuzz, aiosqlite
- Background jobs (opcional): dramatiq[redis]
- Media & background removal (opcional): rembg (requiere onnxruntime, numba, llvmlite), Pillow
- Resiliencia/reintentos (core de varias operaciones): tenacity
- Seguridad archivos (opcional): clamd (ClamAV daemon externo)
- Web scraping / parsing HTML (opcional): beautifulsoup4
- PDF / OCR (opcional): pdfplumber, camelot-py[cv], ocrmypdf, pdf2image, pytesseract, opencv-python-headless
	- Nota: se fija `pypdf>=4.3` y `pdfplumber>=0.11` para eliminar warnings de ARC4
- Inferencia modelos (para rembg): onnxruntime
- Navegación headless / scraping avanzado: playwright (+ navegadores instalados con `python -m playwright install <browser>`)
- Otros para PDF avanzado (ya en core/extra): reportlab, weasyprint (no Windows)

Install (entorno limpio):
```
python -m venv .venv && . .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
```

Environment (common):
```
DB_URL=postgresql+psycopg://user:pass@localhost:5432/growen
MEDIA_ROOT=./Imagenes
RUN_DOCTOR_ON_BOOT=1
DOCTOR_FAIL_ON_ERROR=0
ALLOW_AUTO_PIP_INSTALL=false
```

Jobs (optional):
```
REDIS_URL=redis://localhost:6379/0
```

Frontend (Node)
- Core: react, react-dom, vite, typescript
- Scripts: `npm run dev`, `npm run build`, `npm run doctor`

Install:
```
cd frontend
npm ci
```

Node Doctor:
```
npm run doctor
# ALLOW_AUTO_NPM_INSTALL=true npm run doctor  # to auto-fix with npm ci
```

Python Doctor (manual):
```
python -m tools.doctor
```

### Dependencias del sistema (según features)

OCR / PDF:
- Tesseract OCR + language pack spa (español)
- Ghostscript (requerido por ocrmypdf para ciertas conversiones)
- QPDF (optimización y saneamiento PDF para ocrmypdf)

PDF tabulares (camelot):
- poppler (en Windows se puede usar binarios precompilados; alternativamente pypdfium2 ya cubre render en muchos casos)

ClamAV (clamd):
- Servicio clamd corriendo local o remoto (puerto TCP o socket). En Windows puede omitirse si no se requiere scanning.

Background removal (rembg):
- Los pesos de modelo se descargan en primer uso vía pooch; requiere acceso a red.

Playwright (crawler / scraping avanzado):
```
python -m playwright install chromium
```

### Instalación binarios (Windows hints)
1. Tesseract: Instalar desde https://github.com/UB-Mannheim/tesseract/wiki
   - Incluir el paquete de idioma Spanish (spa). Verificar con:
	 ````powershell
	 tesseract --list-langs | Select-String spa
	 ````
2. Ghostscript: https://www.ghostscript.com/download/gsdnld.html (agregar a PATH)
3. QPDF: https://sourceforge.net/projects/qpdf/files/ (agregar `bin` a PATH)
4. (Opcional) Poppler: https://github.com/oschwartz10612/poppler-windows/releases/ (agregar `Library\bin` a PATH) si se necesita compat extra para camelot.

### Validación rápida Python (imports)
Crear archivo temporal `verify_imports.py`:
```
import importlib, sys
mods = ['PIL','dramatiq','rembg','clamd','camelot','pdfplumber','pdf2image','pytesseract','ocrmypdf','onnxruntime']
failed = []
for m in mods:
	try:
		importlib.import_module(m)
		print(f'OK {m}')
	except Exception as e:
		print(f'FAIL {m}: {e}')
		failed.append(m)
print('\nResumen:')
if failed:
	print('Fallaron:', failed)
	sys.exit(1)
else:
	print('Todos los imports exitosos')
```
Ejecutar:
```
python verify_imports.py
```

### Troubleshooting rembg
Si falla `rembg` por `onnxruntime` ausente: instalar `pip install onnxruntime`.
Si hay error de numba/llvmlite (compilación JIT), verificar que la versión de Python coincida con ruedas precompiladas y no exista otra instalación de LLVM en PATH.

### Notas ClamAV
Si `clamd` no está disponible, la aplicación debe degradar graciosamente (stub). Ajustar variable para desactivar scanning si es necesario (ver configuración runtime).

### Playwright
Instalar navegadores (ejemplo Chromium):
```
python -m playwright install chromium
```
Validar:
```
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"
```

### Panel de salud de herramientas (Admin/Servicios)
- La UI consulta `/admin/services/tools/health` y muestra estado de:
	- QPDF: presencia en PATH y versión (`qpdf --version`).
	- Ghostscript: binario `gswin64c`/`gswin32c`/`gs` y versión (`-v`).
	- Tesseract: presencia y versión (`tesseract --version`).
	- Playwright: paquete instalado y si Chromium está disponible.
- Si falta alguna herramienta, se verán hints de instalación en esta doc.

### Actualización de dependencias
Tras agregar nuevas librerías opcionales se debe:
1. Añadir al `requirements.txt` (ya se agregó onnxruntime).
2. Documentar en este archivo.
3. Actualizar CHANGELOG si la funcionalidad es nueva.

### Criterios de aceptación (auto-check)
- Imports principales sin errores.
- Herramientas de sistema en PATH cuando feature habilitado.
- `python -m tools.doctor` no marca MISS críticas para features requeridos.

### Ollama (LLM local)
Ver `docs/ollama.md` para instalación, variables de entorno y pruebas de conectividad. Si `AI_ALLOW_EXTERNAL=false` el router usará Ollama para todas las tareas soportadas.

Logs
- Backend logs rotate at `./logs/backend.log` (10MB x 5 files)
- Utilities:
```
python -m tools.logs --purge
python -m tools.logs --rotate
```

