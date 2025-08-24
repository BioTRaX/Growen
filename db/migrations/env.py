import os
import logging
import traceback
from datetime import datetime
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import engine_from_config, text
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

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
load_dotenv()

# === Cargar DB_URL desde entorno ===
db_url = os.getenv("DB_URL")
if not db_url:
    raise RuntimeError("DB_URL no definida en entorno/.env")

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
    """Amplía alembic_version.version_num a VARCHAR(255) si es muy corto."""
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
        return
    try:
        curr_len = int(res)
    except (TypeError, ValueError):
        curr_len = None
    if curr_len is not None and curr_len < 64:
        conn.execute(
            text(
                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
            )
        )
        logger.info("Ajustado alembic_version.version_num a VARCHAR(255)")
    else:
        logger.info(
            "alembic_version.version_num ya es suficientemente amplio (len=%s)",
            curr_len,
        )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
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
        # Transacción corta AISLADA para preflight
        try:
            with connection.begin():
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
        )

        try:
            with context.begin_transaction():
                context.run_migrations()
            logger.info("Migraciones aplicadas con éxito")
        except Exception:  # pragma: no cover - logging
            logger.error("Error al ejecutar migraciones:\n%s", traceback.format_exc())
            raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
