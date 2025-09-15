import importlib, sys
mods = ['PIL','bs4','dramatiq','rembg','clamd','camelot','pdfplumber','pdf2image','pytesseract','ocrmypdf']
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
