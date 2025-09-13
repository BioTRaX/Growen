# NG-HEADER: Nombre de archivo: logging_setup.py
# NG-HEADER: Ubicación: ai/logging_setup.py
# NG-HEADER: Descripción: Configura logger dedicado para IA con rotación
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Inicializa un logger separado para la capa de IA.

Se utiliza RotatingFileHandler en `logs/ai.log` con rotación por tamaño.
Activación controlada por variable de entorno `AI_LOG_FILE=1`.

Formato JSON compacto para fácil parseo posterior.
"""
from __future__ import annotations
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_INITIALIZED = False

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        base = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        # Incluir dict extra si lo hay
        for k, v in getattr(record, "__dict__", {}).items():
            # evita duplicar atributos estándar
            if k in base or k.startswith("_"):
                continue
        extra = getattr(record, "__dict__", {})
        meta = {}
        for k, v in extra.items():
            if k not in base and k not in {"msg", "args", "levelname", "levelno", "pathname", "filename", "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process"}:
                meta[k] = v
        if meta:
            base["extra"] = meta
        return json.dumps(base, ensure_ascii=False)

def setup_ai_logger() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    if os.getenv("AI_LOG_FILE") != "1":
        return
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "ai.log"
    handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger_names = ["services.ai.provider", "services.routers.ws"]
    for name in logger_names:
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)
        lg.addHandler(handler)
        lg.propagate = True  # mantener propagación a root si ya se captura stdout
    _INITIALIZED = True
