Dependencies and Setup
======================

Backend (Python)
- Runtime core: fastapi, uvicorn, sqlalchemy, alembic, psycopg[binary], httpx
- Important: pydantic-settings, passlib[argon2], python-multipart, pandas, openpyxl, pillow
- Optional: dramatiq[redis], rembg, clamd, aiosqlite (tests)

Install:
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

Manual Doctor (Python):
```
python -m tools.doctor
```

Logs
- Backend logs rotate at `./logs/backend.log` (10MB x 5 files)
- Utilities:
```
python -m tools.logs --purge
python -m tools.logs --rotate
```

