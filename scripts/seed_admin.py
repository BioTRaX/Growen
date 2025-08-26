import os
from sqlalchemy import create_engine, text
from passlib.hash import argon2
from agent_core.config import settings

engine = create_engine(settings.db_url, future=True)
admin_user = os.getenv('ADMIN_USER','admin')
admin_pass = os.getenv('ADMIN_PASS','REEMPLAZAR_ADMIN_PASS')
if admin_pass == 'REEMPLAZAR_ADMIN_PASS':
    print('WARN: ADMIN_PASS placeholder; using temp password: admin1234')
    admin_pass = 'admin1234'

with engine.begin() as conn:
    exists = conn.execute(text("select 1 from users where role='admin' limit 1")).first()
    if exists is None:
        h = argon2.using(type='ID').hash(admin_pass)
        conn.execute(text("""
            INSERT INTO users(identifier,email,name,password_hash,role)
            VALUES(:i,:e,:n,:h,'admin')
        """), dict(i=admin_user, e=f"{admin_user}@growen.local", n=admin_user, h=h))
        print('Seeded admin user:', admin_user)
    else:
        print('Admin user already exists')
