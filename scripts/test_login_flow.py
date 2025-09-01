# NG-HEADER: Nombre de archivo: test_login_flow.py
# NG-HEADER: Ubicación: scripts/test_login_flow.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import requests, sys
base = 'http://localhost:8000'
s = requests.Session()
s.headers['Origin'] = 'http://localhost:5173'

r = s.get(base + '/auth/me')
print('me before', r.status_code, r.text)

r = s.post(base + '/auth/login', json={'identifier':'admin','password':'admin1234'})
print('login', r.status_code, r.text)
print('cookies after login', s.cookies.get_dict())

r = s.get(base + '/auth/me')
print('me after', r.status_code, r.text)
