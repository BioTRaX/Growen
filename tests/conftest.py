# NG-HEADER: Nombre de archivo: conftest.py
# NG-HEADER: Ubicación: tests/conftest.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import sys
from pathlib import Path

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

sys.path.append(str(Path(__file__).resolve().parents[1]))
