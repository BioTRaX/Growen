# NG-HEADER: Nombre de archivo: conftest.py
# NG-HEADER: Ubicación: tests/e2e/conftest.py
# NG-HEADER: Descripción: Fixtures base para pruebas E2E con Playwright (browser, contexto y autenticación si aplica)
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import pytest
from playwright.sync_api import sync_playwright
import subprocess, sys, time, socket
from pathlib import Path
from dotenv import load_dotenv, dotenv_values


def _project_root() -> str:
    # tests/e2e -> repo root
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# Cargar .env del proyecto en este proceso para propagar DB_URL y otros a subprocesos
_ENV_LOADED = False
try:
    env_path = Path(_project_root()) / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
        _ENV_LOADED = True
except Exception as _e:
    print("[E2E] WARN: No se pudo cargar .env en conftest:", _e)


def _real_db_url() -> str:
    """Obtiene DB_URL preferentemente desde el archivo .env, sin ser afectado por setdefault de tests."""
    try:
        env_path = Path(_project_root()) / ".env"
        vals = dotenv_values(dotenv_path=str(env_path)) if env_path.exists() else {}
        v = vals.get("DB_URL")
        if v and v.strip():
            return v.strip()
        # Construir desde piezas si están presentes
        host = vals.get("DB_HOST") or os.environ.get("DB_HOST")
        name = vals.get("DB_NAME") or os.environ.get("DB_NAME")
        user = vals.get("DB_USER") or os.environ.get("DB_USER")
        pw = vals.get("DB_PASS") or os.environ.get("DB_PASS")
        port = vals.get("DB_PORT") or os.environ.get("DB_PORT") or "5432"
        if host and name and user is not None:
            from urllib.parse import quote_plus as _qp
            if pw:
                return f"postgresql+psycopg://{user}:{_qp(pw)}@{host}:{port}/{name}"
            else:
                return f"postgresql+psycopg://{user}@{host}:{port}/{name}"
    except Exception:
        pass
    # Fallback: SQLite archivo local persistente para E2E
    return "sqlite+aiosqlite:///./e2e.db"


# Forzar DB_URL real en este proceso para evitar :memory: que pone tests/conftest.py
os.environ["DB_URL"] = _real_db_url()

# Skip defensivo en Windows salvo opt-in explícito
if os.name == "nt" and os.environ.get("E2E_WINDOWS_ENABLE", "0") != "1":
    pytest.skip("E2E deshabilitadas en Windows por defecto; exporta E2E_WINDOWS_ENABLE=1 para forzar.", allow_module_level=True)


def _base_env() -> dict:
    env = os.environ.copy()
    env["DB_URL"] = _real_db_url()
    env.setdefault("ENV", os.environ.get("ENV", "dev"))
    return env


def _seed_admin_if_needed():
    try:
        # Ejecuta script de seeding en subproceso para evitar conflictos async
        env = _base_env()
        # Sugerir credenciales por defecto si no están presentes
        env.setdefault("ADMIN_USER", env.get("E2E_USER", "admin"))
        env.setdefault("ADMIN_PASS", env.get("E2E_PASS", "admin1234"))
        subprocess.run([sys.executable, "-m", "scripts.seed_admin"], check=False, cwd=_project_root(), env=env)
    except Exception as e:
        print("[E2E] WARN: No se pudo seedear admin:", e)


def _run_migrations():
    try:
        env = _base_env()
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, cwd=_project_root(), env=env)
    except Exception as e:
        print("[E2E] ERROR: Falló alembic upgrade head:", e)
        raise


def _start_server():
    env = _base_env()
    env.setdefault("LOG_LEVEL", "DEBUG")
    # Evitar dependencias de worker/redis al correr solo API
    # Si el puerto ya está ocupado, asumimos que el servidor está corriendo
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=0.2):
            return None
    except OSError:
        pass
    if os.name == "nt":
        cmd = [
            sys.executable,
            "-c",
            ("import asyncio, uvicorn; "
             "asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()); "
             "uvicorn.run(\'services.api:app\', host=\'127.0.0.1\', port=8000)"),
        ]
    else:
        cmd = [sys.executable, "-m", "uvicorn", "services.api:app", "--host", "127.0.0.1", "--port", "8000"]
    proc = subprocess.Popen(cmd, env=env, cwd=_project_root())
    # Esperar puerto 8000
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", 8000), timeout=0.2):
                return proc
        except OSError:
            time.sleep(0.2)
    raise AssertionError("No se pudo iniciar uvicorn en 127.0.0.1:8000")

# URL base servida por FastAPI (SPA)
BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000")

@pytest.fixture(scope="session")
def browser():
    # Migraciones y backend
    _run_migrations()
    server = _start_server()
    _seed_admin_if_needed()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()
    try:
        if server is not None:
            server.terminate()
    except Exception:
        pass

@pytest.fixture()
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(20000)
    yield page
    context.close()

@pytest.fixture(scope="session")
def base_url():
    return BASE_URL
