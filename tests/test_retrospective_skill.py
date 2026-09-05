#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_retrospective_skill.py
# NG-HEADER: Ubicación: tests/test_retrospective_skill.py
# NG-HEADER: Descripción: Verifica que el cierre materialice mejoras agénticas.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from pathlib import Path

import pytest

from scripts.audit_agentic_environment import extract_direct_closing_triggers


ROOT = Path(__file__).parents[1]
pytestmark = pytest.mark.no_db


def _skill(name: str) -> str:
    return (ROOT / ".agents" / "skills" / name / "SKILL.md").read_text(
        encoding="utf-8"
    )


def test_retrospective_requires_materialized_agentic_improvement() -> None:
    skill = _skill("retrospectiva-tecnica-sesion")
    assert "materializar" in skill.lower()
    assert "entorno agéntico" in skill.lower()


def test_retrospective_has_only_the_two_direct_closing_triggers() -> None:
    skill = _skill("retrospectiva-tecnica-sesion")

    assert extract_direct_closing_triggers(skill) == frozenset(
        {"cerrar sesión", "cerremos sesión"}
    )
    assert "Frases como `Terminamos la sesión`" in skill
    assert "no activa este flujo" in skill


def test_retrospective_confirms_ambiguous_pending_work_before_closing() -> None:
    skill = _skill("retrospectiva-tecnica-sesion").lower()

    assert "trabajo pendiente ambiguo" in skill
    assert "solicitar confirmación" in skill


def test_retrospective_enforces_risk_gate_and_sequential_closing() -> None:
    skill = _skill("retrospectiva-tecnica-sesion").lower()
    ordered_terms = (
        "análisis retrospectivo",
        "evolución agéntica",
        "compuerta de riesgo",
        "actualización de documentación",
        "flujo de auto-merge",
        "output final",
    )

    positions = [skill.index(term) for term in ordered_terms]
    assert positions == sorted(positions)
    assert "riesgo muy alto" in skill
    assert "detener el flujo" in skill


def test_retrospective_documents_the_required_terminal_git_flow() -> None:
    skill = _skill("retrospectiva-tecnica-sesion")

    for command in (
        "git fetch",
        "git merge origin/dev",
        "git diff --name-only --diff-filter=U",
        "git add .",
        "git switch dev",
        "git push origin dev",
    ):
        assert command in skill
    for marker in ("<<<<<<<", "=======", ">>>>>>>"):
        assert marker in skill
    assert skill.index("crear los commits atómicos de trabajo") < skill.index(
        "git fetch"
    )


def test_retrospective_final_output_is_the_exclusive_five_item_checklist() -> None:
    skill = _skill("retrospectiva-tecnica-sesion")
    output_section = skill.split("### 6. Output final", maxsplit=1)[1]
    checklist = [
        line.removeprefix("- [x] ").strip()
        for line in output_section.splitlines()
        if line.startswith("- [x] ")
    ]

    assert "exclusivamente" in output_section
    assert checklist == [
        "Análisis retrospectivo completado",
        "Evolución agéntica implementada/propuesta",
        "Actualización de documentación",
        "Merge a Dev",
        "Final de sesión",
    ]


def test_git_skill_requires_ephemeral_branch_and_forbids_direct_dev_commits() -> None:
    skill = _skill("git-commit-push")
    lines = {line.strip() for line in skill.splitlines()}

    assert "rama efímera" in skill.lower()
    assert "git switch -c" in skill
    assert (
        "- Está prohibido hacer un commit directo en `dev`. `dev` sólo recibe el merge final de una rama efímera validada."
        in lines
    )


def test_git_skill_resolves_verifiable_conflicts_without_force_push() -> None:
    skill = _skill("git-commit-push")

    assert "resolver" in skill.lower()
    assert "git diff --name-only --diff-filter=U" in skill
    assert "intención" in skill
    assert "Nunca usar `git push --force`" in skill
