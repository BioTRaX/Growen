#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_token_optimization_and_ignore_rules.py
# NG-HEADER: Ubicación: tests/test_token_optimization_and_ignore_rules.py
# NG-HEADER: Descripción: Pruebas unitarias para validar reglas de exclusión, lazy loading de skills y acceso a logs.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

EXPECTED_SUPERPOWERS_SKILLS = [
    "brainstorming",
    "dispatching-parallel-agents",
    "executing-plans",
    "finishing-a-development-branch",
    "receiving-code-review",
    "requesting-code-review",
    "subagent-driven-development",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "using-superpowers",
    "verification-before-completion",
    "writing-plans",
    "writing-skills",
]

MANDATORY_EXCLUSIONS = [
    "media/",
    "node_modules/",
    "frontend-vue/dist/",
    ".venv/",
    ".git/",
    "logs/",
]


def test_exclusion_files_exist():
    """Valida la presencia de archivos de exclusión para Copilot, Gemini, Cursor y Aider."""
    assert (ROOT_DIR / ".copilotignore").is_file(), "Falta .copilotignore en raíz"
    assert (ROOT_DIR / ".geminiignore").is_file(), "Falta .geminiignore en raíz"
    assert (ROOT_DIR / ".cursorignore").is_file(), "Falta .cursorignore en raíz"
    assert (ROOT_DIR / ".aiderignore").is_file(), "Falta .aiderignore en raíz"


def test_mandatory_exclusions_present():
    """Valida que los patrones críticos obligatorios estén configurados."""
    copilot_content = (ROOT_DIR / ".copilotignore").read_text(encoding="utf-8")
    gemini_content = (ROOT_DIR / ".geminiignore").read_text(encoding="utf-8")

    for pattern in MANDATORY_EXCLUSIONS:
        assert pattern in copilot_content, f"Patrón obligatorio '{pattern}' ausente en .copilotignore"
        assert pattern in gemini_content, f"Patrón obligatorio '{pattern}' ausente en .geminiignore"


def test_superpowers_catalog_contains_all_14_skills():
    """Valida que CATALOG.md incluya las 14 skills de Superpowers en formato minimalista."""
    catalog_path = ROOT_DIR / "docs" / "superpowers" / "CATALOG.md"
    assert catalog_path.is_file(), "Falta docs/superpowers/CATALOG.md"
    content = catalog_path.read_text(encoding="utf-8")

    for skill in EXPECTED_SUPERPOWERS_SKILLS:
        assert f"`{skill}`" in content, f"Skill '{skill}' no indexada en CATALOG.md"


def test_logs_directory_accessible_on_demand():
    """Valida que la carpeta logs/ sea accesible en disco para debugging bajo demanda."""
    logs_dir = ROOT_DIR / "logs"
    assert logs_dir.is_dir(), "Directorio logs/ no existe"
    # Puede listarse y leerse sin restricciones de permisos
    items = list(logs_dir.iterdir())
    assert len(items) > 0, "logs/ debe contener archivos para debugging"


def test_ng_headers_in_new_documentation():
    """Valida que los nuevos documentos cumplan con la directiva NG-HEADER."""
    docs_to_check = [
        ROOT_DIR / "docs" / "development" / "TOKEN_OPTIMIZATION.md",
        ROOT_DIR / "docs" / "superpowers" / "CATALOG.md",
    ]
    for doc in docs_to_check:
        assert doc.is_file(), f"Documento no encontrado: {doc}"
        lines = doc.read_text(encoding="utf-8").splitlines()
        first_lines = "\n".join(lines[:5])
        assert "<!-- NG-HEADER: Nombre de archivo:" in first_lines, f"Falta NG-HEADER en {doc}"
        assert "<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->" in first_lines, f"Falta lineamiento en {doc}"
