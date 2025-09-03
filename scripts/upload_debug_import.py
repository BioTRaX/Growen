import requests, sys, os
candidate = os.path.join(os.path.dirname(__file__), '..', 'Devs', 'Remito_00099596_RUIZ DIAZ CLAUDIO ALEJANDRO.pdf')
candidate = os.path.normpath(candidate)
if not os.path.exists(candidate):
    print('File not found:', candidate)
    sys.exit(1)
url = 'http://127.0.0.1:8000/purchases/import/santaplanta?debug=1&force_ocr=1'
with open(candidate, 'rb') as fh:
    files = {'file': ('remito.pdf', fh, 'application/pdf')}
    r = requests.post(url, files=files)
    print('status', r.status_code)
    print(r.text)
