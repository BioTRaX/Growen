# NG-HEADER: Nombre de archivo: env.py
# NG-HEADER: Ubicación: db/migrations/env.py
# NG-HEADER: Descripción: Script de entorno Alembic: carga .env, prepara logging y ejecuta migraciones
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import logging
import traceback
from datetime import datetime
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import engine_from_config, text, String
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
from urllib.parse import urlsplit

# Logger estandar para todas las operaciones del módulo
logger = logging.getLogger("alembic.env")

# Config Alembic
config = context.config

# Logging (si alembic.ini tiene secciones de logging)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# === Preparar logging detallado ===
log_level = os.getenv("ALEMBIC_LOG_LEVEL", "INFO").upper()
logs_dir = Path("logs") / "migrations"
logs_dir.mkdir(parents=True, exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = logs_dir / f"alembic_{ts}.log"
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(),
    ],
)
logger.info("Usando nivel de log %s", log_level)
logger.info("Archivo de log: %s", log_file)

script = ScriptDirectory.from_config(config)

# === Cargar variables desde .env ===
# Cargar .env explícitamente desde la raíz del repo (dos niveles hacia arriba)
REPO_ROOT = Path(__file__).resolve().parents[2]
dotenv_path = REPO_ROOT / ".env"
pre_env_db_url = os.environ.get("DB_URL")
load_dotenv(dotenv_path, override=True)  # override=True para forzar lo definido en .env
post_env_db_url = os.environ.get("DB_URL")
logger.info("Archivo .env: %s (exists=%s, override=True)", dotenv_path, dotenv_path.exists())
if pre_env_db_url and pre_env_db_url != post_env_db_url:
    logger.info(
        "DB_URL en proceso fue sobreescrita por .env (antes vs después): %s -> %s",
        "(oculta)" if pre_env_db_url else None,
        "(oculta)" if post_env_db_url else None,
    )

# === Cargar DB_URL desde entorno ===
db_url = os.getenv("DB_URL")
if not db_url:
    raise RuntimeError("DB_URL no definida en entorno/.env")
else:
    # Log seguro del DB_URL sin credenciales
    try:
        parts = urlsplit(db_url)
        netloc = parts.netloc
        if "@" in netloc and ":" in netloc.split("@")[0]:
            user = netloc.split("@")[0].split(":")[0]
            host = netloc.split("@")[1]
            netloc = f"{user}:***@{host}"
        safe = parts._replace(netloc=netloc).geturl()
        logger.info("DB_URL: %s", safe)
    except Exception:
        logger.info("DB_URL: (formato no imprimible)")

# === Importar metadatos del proyecto ===
try:
    from db.base import Base
    import db.models  # noqa: F401

    target_metadata = Base.metadata
except Exception:
    # Fallback seguro: sin metadata, autogenerate no funcionará
    target_metadata = None


def _coerce_bool(val) -> bool:
    return str(val).lower() in {"1", "true", "t", "yes", "y", "on"}


def _ensure_alembic_version_column(conn):
    """Amplía alembic_version.version_num a VARCHAR(255) si es muy corto o si la tabla no existe todavía.

    Nota: Alembic crea la tabla con VARCHAR(32) por defecto. Configuramos además
    version_table_column_type en context.configure para futuras creaciones, pero
    aquí hacemos un ALTER preventivo si ya existe con longitud insuficiente.
    """
    try:  # pragma: no cover - se ejecuta en runtime de migraciones
        # 1. Detectar existencia de la tabla
        tbl_exists = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name = 'alembic_version'
                LIMIT 1
                """
            )
        ).scalar() is not None

        if not tbl_exists:
            # Crear manualmente con longitud extendida para que Alembic no la cree con VARCHAR(32)
            conn.execute(
                text(
                    """
                    CREATE TABLE alembic_version (
                        version_num VARCHAR(255) NOT NULL PRIMARY KEY
                    )
                    """
                )
            )
            logger.info(
                "Creada tabla alembic_version manualmente con version_num VARCHAR(255)"
            )
            return  # Nada más que hacer en esta fase (está vacía todavía)

        # 2. Si existe, evaluar longitud de la columna y ampliar si es necesario
        q = text(
            """
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'alembic_version'
              AND column_name = 'version_num'
              AND table_schema = current_schema()
            LIMIT 1
            """
        )
        res = conn.execute(q).scalar()
        if res is None:
            logger.info(
                "No se pudo obtener longitud de version_num; se omite ajuste preventivo"
            )
            return
        try:
            curr_len = int(res)
        except (TypeError, ValueError):
            curr_len = None
        if curr_len is None:
            logger.info("No se pudo determinar longitud actual de alembic_version.version_num (res=%s)", res)
            return
        if curr_len < 64:
            conn.execute(
                text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)")
            )
            logger.info(
                "Ajustado alembic_version.version_num de len=%s a VARCHAR(255)",
                curr_len,
            )
        else:
            logger.info(
                "alembic_version.version_num ya es suficientemente amplio (len=%s)",
                curr_len,
            )
    except Exception as e:  # pragma: no cover - diagnóstico defensivo
        logger.warning("No se pudo ajustar alembic_version.version_num: %s", e)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        version_table_column_type=String(255),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    try:
        x_args = context.get_x_argument(as_dictionary=True)
    except TypeError:  # compatibilidad con Alembic antiguo
        raw_args = context.get_x_argument()
        x_args = {}
        for arg in raw_args:
            if "=" in arg:
                k, v = arg.split("=", 1)
                x_args[k] = v
            else:
                x_args[arg] = None

    log_sql = _coerce_bool(x_args.get("log_sql"))
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = db_url
    if log_sql:
        section["sqlalchemy.echo"] = "true"
    logger.info(
        "sqlalchemy.url inyectada via sección de config (sin set_main_option)"
    )
    logger.info("sqlalchemy.echo activado: %s", log_sql)
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        # Forzar uso del esquema 'public' para evitar escribir en esquemas por-usuario
        try:
            curr_sp = connection.exec_driver_sql("show search_path").scalar()
            connection.exec_driver_sql("set search_path to public")
            logger.info("search_path anterior: %s -> nuevo: public", curr_sp)
        except Exception as e:
            logger.warning("No se pudo fijar search_path=public: %s", e)
        # Preflight sin iniciar otra transacción explícita para evitar conflictos
        try:
            _ensure_alembic_version_column(connection)
            logger.info("Preflight alembic_version OK")
        except Exception as e:
            logger.warning(
                "Preflight alembic_version omitido o ya aplicado: %s", e
            )

        current_rev = MigrationContext.configure(connection).get_current_revision()
        heads = script.get_heads()
        logger.info("Revisión actual: %s", current_rev)
        logger.info("Heads: %s", ", ".join(heads))
        hist = [rev.revision for rev in list(script.walk_revisions())[:30]]
        logger.info("Historial reciente: %s", ", ".join(hist))

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            version_table_column_type=String(255),
        )

        try:
            with context.begin_transaction():
                context.run_migrations()
            # Asegurar commit explícito del connection si hay una transacción implícita abierta
            try:
                connection.commit()
                logger.info("Commit explícito aplicado tras migraciones")
            except Exception as e:
                logger.warning("No se pudo aplicar commit explícito: %s", e)
            logger.info("Migraciones aplicadas con éxito")
        except Exception:  # pragma: no cover - logging
            logger.error("Error al ejecutar migraciones:\n%s", traceback.format_exc())
            raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
