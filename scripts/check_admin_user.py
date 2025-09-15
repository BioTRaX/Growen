#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_admin_user.py
# NG-HEADER: Ubicación: scripts/check_admin_user.py
# NG-HEADER: Descripción: Script para verificar existencia de usuario admin en la base
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os, json
from dotenv import load_dotenv
from urllib.parse import urlsplit
import psycopg

load_dotenv()

url = os.environ['DB_URL']
parts = urlsplit(url)
userpass, hostport = parts.netloc.split('@')
user, pwd = userpass.split(':',1)
host, port = hostport.split(':',1)
db = parts.path.lstrip('/')

with psycopg.connect(host=host, port=port, user=user, password=pwd, dbname=db) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id, identifier, role FROM users WHERE identifier=%s OR role='admin' ORDER BY id ASC LIMIT 5", ('admin',))
        rows = cur.fetchall()
        print(json.dumps(rows, default=str))
