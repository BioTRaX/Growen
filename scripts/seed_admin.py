# NG-HEADER: Nombre de archivo: seed_admin.py
# NG-HEADER: Ubicación: scripts/seed_admin.py
# NG-HEADER: Descripción: Script idempotente para crear usuario admin inicial con password Argon2
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
from sqlalchemy import create_engine, text
from passlib.hash import argon2
from agent_core.config import settings

# Compatibilidad: si DB_URL usa driver async de SQLite, usar driver sync para seeding
def _mask_url(u: str) -> str:
    try:
        if '://' in u and '@' in u:
            pre, post = u.split('://', 1)
            creds, rest = post.split('@', 1)
            if ':' in creds:
                user, _pwd = creds.split(':', 1)
                return f"{pre}://{user}:***@{rest}"
        return u
    except Exception:
        return u

print(f"[seed_admin] ENV={settings.env}")
db_url = settings.db_url
print(f"[seed_admin] DB_URL (raw)={_mask_url(db_url)}")
if db_url.startswith("sqlite+aiosqlite:"):
    db_url = db_url.replace("sqlite+aiosqlite:", "sqlite:")
print(f"[seed_admin] DB_URL (normalized)={_mask_url(db_url)}")

engine = create_engine(db_url, future=True)
admin_user = os.getenv('ADMIN_USER','admin')
admin_pass = os.getenv('ADMIN_PASS','REEMPLAZAR_ADMIN_PASS')
reset_admin = os.getenv('RESET_ADMIN_PASS') or ('1' if settings.env == 'dev' else '0')
if admin_pass == 'REEMPLAZAR_ADMIN_PASS':
    print('WARN: ADMIN_PASS placeholder; using temp password: admin1234')
    admin_pass = 'admin1234'

try:
    with engine.begin() as conn:
        row = conn.execute(text("select id, identifier from users where role='admin' limit 1")).first()
        if row is None:
            h = argon2.using(type='ID').hash(admin_pass)
            # Incluimos created_at / updated_at explícitamente para evitar violaciones NOT NULL
            conn.execute(text(
                """
                INSERT INTO users(identifier,email,name,password_hash,role,created_at,updated_at)
                VALUES(:i,:e,:n,:h,'admin', NOW(), NOW())
                """
            ), dict(i=admin_user, e=f"{admin_user}@growen.local", n=admin_user, h=h))
            print('Seeded admin user:', admin_user)
        else:
            if reset_admin and reset_admin not in {'0','false','False','no','NO'}:
                h = argon2.using(type='ID').hash(admin_pass)
                conn.execute(text("update users set password_hash=:h, updated_at=NOW() where id=:id"), dict(h=h, id=row.id))
                print('Admin user exists; password reset applied')
            else:
                print('Admin user already exists')
except Exception as e:
    # Mensaje amigable cuando las tablas no existen aún
    print("ERROR: No se pudo seedear admin. ¿Ejecutaste las migraciones? Detalle:", e)
    raise
