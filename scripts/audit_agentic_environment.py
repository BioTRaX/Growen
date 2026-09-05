#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: audit_agentic_environment.py
# NG-HEADER: Ubicación: scripts/audit_agentic_environment.py
# NG-HEADER: Descripción: Auditoría determinista del entorno agéntico de Growen.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


REQUIRED_FILES = ("AGENTS.md", "README.md", "Roadmap.md", "docs/AGENT_SKILLS.md")
SKILL_RE = re.compile(
    r"\A---\r?\nname: ([a-z0-9-]+)\r?\ndescription: ([^\r\n]+)\r?\n---(?:\r?\n|\Z)"
)
CLOSING_TRIGGERS = frozenset({"cerrar sesión", "cerremos sesión"})
DIRECT_TRIGGER_RE = re.compile(
    r"Los únicos triggers directos son `([^`]+)` y `([^`]+)`",
    re.IGNORECASE,
)
SKILL_REQUIRED_LINES = {
    "git-commit-push": {
        "ephemeral_branch": (
            "- Todo trabajo comienza desde el estado actual de `dev` en una rama efímera nueva: `feat/<tarea>`, `fix/<tarea>`, `docs/<tarea>` o `chore/<tarea>`.",
        ),
        "no_direct_commit_to_dev": (
            "- Está prohibido hacer un commit directo en `dev`. `dev` sólo recibe el merge final de una rama efímera validada.",
        ),
        "verified_conflict_resolution": (
            "4. Resolver de forma autónoma sólo cuando contratos, contexto y pruebas permiten demostrar la intención. Si es ambigua o de riesgo muy alto, detener el flujo.",
        ),
        "safe_staging": (
            "6. Tras una resolución, usar `git add .` sólo si el inventario demuestra que todo el worktree pertenece al cierre; si no, agregar rutas explícitas. Crear el commit de fusión cuando Git lo requiera.",
        ),
    },
    "retrospectiva-tecnica-sesion": {
        "ambiguous_work": (
            "Si aparece un trigger válido y existe trabajo pendiente ambiguo, solicitar confirmación breve sobre si debe completarse o descartarse antes de cerrar. La respuesta despeja la ambigüedad; no reemplaza el trigger.",
        ),
        "high_risk_gate": (
            "Implementar las mejoras de riesgo bajo o medio. Ante riesgo muy alto, informar únicamente el estado y la propuesta, preguntar si se avanza y detener el flujo hasta recibir respuesta explícita.",
        ),
        "auto_merge": (
            "2. Ejecutar `git fetch` y `git merge origin/dev`.",
            "6. Ejecutar `git switch dev`, fusionar la rama efímera y ejecutar `git push origin dev`.",
        ),
    },
}


def _strip_final_punctuation(text: str) -> str:
    normalized = text.strip()
    while normalized and unicodedata.category(normalized[-1]).startswith("P"):
        normalized = normalized[:-1].rstrip()
    return normalized


def classify_closing_request(text: str, *, ambiguous_open_work: bool = False) -> str:
    normalized = _strip_final_punctuation(text.casefold())
    if normalized not in CLOSING_TRIGGERS:
        return "ignore"
    return "confirm" if ambiguous_open_work else "close"


def extract_direct_closing_triggers(content: str) -> frozenset[str]:
    match = DIRECT_TRIGGER_RE.search(content)
    if not match:
        return frozenset()
    return frozenset(value.casefold() for value in match.groups())


def audit_agentic_environment(root: Path | None = None) -> list[str]:
    root = root or Path.cwd()
    findings: list[str] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            findings.append(f"missing:{relative}")

    skills_root = root / ".agents" / "skills"
    canonical: dict[str, Path] = {}
    if skills_root.is_dir():
        for skill_file in skills_root.glob("*/SKILL.md"):
            match = SKILL_RE.search(skill_file.read_text(encoding="utf-8-sig"))
            if not match:
                findings.append(f"invalid_frontmatter:{skill_file.relative_to(root)}")
                continue
            canonical[skill_file.parent.name] = skill_file
            if match.group(1) != skill_file.parent.name:
                findings.append(f"name_mismatch:{skill_file.relative_to(root)}")
            content = skill_file.read_text(encoding="utf-8-sig").casefold()
            content_lines = {line.strip() for line in content.splitlines()}
            if skill_file.parent.name == "retrospectiva-tecnica-sesion":
                if extract_direct_closing_triggers(content) != CLOSING_TRIGGERS:
                    findings.append(
                        "missing_contract:retrospectiva-tecnica-sesion:closing_triggers"
                    )
            for contract, required_lines in SKILL_REQUIRED_LINES.get(
                skill_file.parent.name, {}
            ).items():
                if not all(
                    required_line.casefold() in content_lines
                    for required_line in required_lines
                ):
                    findings.append(
                        f"missing_contract:{skill_file.parent.name}:{contract}"
                    )
    else:
        findings.append("missing:.agents/skills")

    legacy_root = root / ".agent" / "skills"
    if legacy_root.is_dir():
        for legacy in legacy_root.glob("*/SKILL.md"):
            name = legacy.parent.name
            if name not in canonical:
                findings.append(f"legacy_without_canonical:{legacy.relative_to(root)}")
                continue
            content = legacy.read_text(encoding="utf-8-sig")
            expected = f".agents/skills/{name}/SKILL.md"
            if expected not in content or len(content.splitlines()) > 12:
                findings.append(f"legacy_diverges:{legacy.relative_to(root)}")
    return sorted(findings)


if __name__ == "__main__":
    result = audit_agentic_environment()
    for finding in result:
        print(finding)
    raise SystemExit(1 if result else 0)
