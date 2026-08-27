#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_retrospective_skill.py
# NG-HEADER: Ubicación: tests/test_retrospective_skill.py
# NG-HEADER: Descripción: Verifica que el cierre materialice mejoras agénticas.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from pathlib import Path


def test_retrospective_requires_materialized_agentic_improvement() -> None:
    skill = (
        Path(__file__).parents[1]
        / ".agents"
        / "skills"
        / "retrospectiva-tecnica-sesion"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "materializar" in skill.lower()
    assert "entorno agéntico" in skill.lower()
