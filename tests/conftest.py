import os
import sys
from pathlib import Path

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

sys.path.append(str(Path(__file__).resolve().parents[1]))
