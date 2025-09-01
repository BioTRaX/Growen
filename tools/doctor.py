# NG-HEADER: Nombre de archivo: doctor.py
# NG-HEADER: Ubicación: tools/doctor.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Project doctor: validates env, Python deps, quick syntax, and optional auto-fix.

Run manually:
  python -m tools.doctor

Environment:
  RUN_DOCTOR_ON_BOOT=1               # services.api imports and runs this (light)
  DOCTOR_FAIL_ON_ERROR=1|0           # fail fast when missing critical deps
  ALLOW_AUTO_PIP_INSTALL=true|false  # install missing packages from requirements.txt
  RUN_QUICK_LINT=0|1                 # optional ruff/black quick check if present
"""
from __future__ import annotations

import os
import sys
import subprocess
import importlib
import traceback
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REQ_FILE = ROOT / "requirements.txt"


CRITICAL: list[str] = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "alembic",
    "psycopg",
    "httpx",
]

IMPORTANT: list[str] = [
    "pydantic_settings",
    "passlib",
    "python_multipart",
    "pandas",
    "openpyxl",
    "pillow",  # Pillow
]

OPTIONAL: list[str] = [
    "dramatiq",
    "rembg",
    "clamd",
    "aiosqlite",
    # OCR/Tablas (opcionales, recomendados para import PDF robusto)
    "camelot",
    "pdfplumber",
    "pdf2image",
    "pytesseract",
]


def _import_name(name: str) -> tuple[str, bool, str | None]:
    try:
        importlib.import_module(name)
        ver = None
        try:
            mod = sys.modules.get(name)
            ver = getattr(mod, "__version__", None)
        except Exception:
            ver = None
        return name, True, ver
    except Exception:
        return name, False, None


def _read_requirements(path: Path) -> set[str]:
    items: set[str] = set()
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = line.split("[")[0].split("=")[0].split("<")[0].split(">")[0].strip()
        if pkg:
            items.add(pkg.lower())
    return items


def _pip_install_requirements() -> int:
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(REQ_FILE)]
    try:
        return subprocess.call(cmd)
    except Exception:
        return 1


def _quick_py_syntax(paths: Iterable[Path]) -> list[str]:
    errs: list[str] = []
    for p in paths:
        if not p.exists():
            continue
        for file in p.rglob("*.py"):
            try:
                py_compile = importlib.import_module("py_compile")
                py_compile.compile(str(file), doraise=True)
            except Exception as e:  # noqa: BLE001
                errs.append(f"Syntax error: {file}: {e}")
    return errs


def _maybe_quick_lint() -> list[str]:
    if os.getenv("RUN_QUICK_LINT", "0") != "1":
        return []
    msgs: list[str] = []
    def _run(cmd: list[str]) -> int:
        try:
            return subprocess.call(cmd, cwd=str(ROOT))
        except Exception:
            return 1
    if importlib.util.find_spec("ruff") is not None:
        rc = _run([sys.executable, "-m", "ruff", "check", "services", "db", "ai"])
        if rc != 0:
            msgs.append("ruff check reported issues")
    if importlib.util.find_spec("black") is not None:
        rc = _run([sys.executable, "-m", "black", "--check", "services", "db", "ai"])
        if rc != 0:
            msgs.append("black check reported issues")
    return msgs


def run_doctor(fail_on_error: bool = False) -> int:
    print("[doctor] Python", sys.version.replace("\n", " "))
    # 1) Imports
    missing_crit = []
    def report(group: str, names: list[str]) -> None:
        ok = 0
        miss = 0
        for n in names:
            name, success, ver = _import_name(n)
            if success:
                ok += 1
                if ver:
                    print(f"[doctor] {group:9s} OK   {name} {ver}")
                else:
                    print(f"[doctor] {group:9s} OK   {name}")
            else:
                miss += 1
                print(f"[doctor] {group:9s} MISS {name}")
                if group == "CRITICAL":
                    missing_crit.append(name)
        if miss == 0:
            print(f"[doctor] {group}: all present ({ok})")
    report("CRITICAL", CRITICAL)
    report("IMPORTANT", IMPORTANT)
    report("OPTIONAL", OPTIONAL)

    # 2) requirements.txt comparison (best-effort)
    declared = _read_requirements(REQ_FILE)
    if declared:
        wanted = {p.split("[")[0].lower() for p in declared}
        found = {m.split("[")[0].lower() for m in CRITICAL + IMPORTANT + OPTIONAL}
        extras = sorted(wanted - found)
        if extras:
            print(f"[doctor] requirements contains {len(extras)} entries not probed by doctor (ok):", ", ".join(extras))

    # 3) Optional auto-install if allowed and there are missing critical deps
    if missing_crit and os.getenv("ALLOW_AUTO_PIP_INSTALL", "false").lower() == "true":
        print("[doctor] Attempting auto-install of requirements.txt ...")
        rc = _pip_install_requirements()
        if rc == 0:
            # retry once
            missing_crit = [n for n in missing_crit if not _import_name(n)[1]]
        else:
            print("[doctor] pip install failed; see output above")

    # 4) Quick syntax scan
    errs = _quick_py_syntax([ROOT / "services", ROOT / "db", ROOT / "ai"])
    for e in errs:
        print("[doctor]", e)

    lint_msgs = _maybe_quick_lint()
    for m in lint_msgs:
        print("[doctor]", m)

    problems = len(missing_crit) + len(errs)
    if problems:
        print(f"[doctor] Summary: {problems} problem(s) detected")
        if fail_on_error:
            return 2
    else:
        print("[doctor] Summary: OK")
        return 0
    return 1


if __name__ == "__main__":
    # Default fail_on_error depends on ENV
    env = os.getenv("ENV", "dev")
    fail = os.getenv("DOCTOR_FAIL_ON_ERROR", "1" if env == "production" else "0") == "1"
    try:
        code = run_doctor(fail_on_error=fail)
        raise SystemExit(code)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
