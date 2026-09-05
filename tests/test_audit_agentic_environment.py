#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_audit_agentic_environment.py
# NG-HEADER: Ubicación: tests/test_audit_agentic_environment.py
# NG-HEADER: Descripción: Pruebas del auditor del entorno agéntico.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from pathlib import Path

import pytest

from scripts.audit_agentic_environment import (
    audit_agentic_environment,
    classify_closing_request,
    extract_direct_closing_triggers,
)


pytestmark = pytest.mark.no_db


def test_agentic_audit_accepts_canonical_skill_and_governance(tmp_path: Path) -> None:
    (tmp_path / ".agents" / "skills" / "demo").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Use when testing demo behavior.\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# README\n", encoding="utf-8")
    (tmp_path / "Roadmap.md").write_text("# Roadmap\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "AGENT_SKILLS.md").write_text("# Skills\n", encoding="utf-8")

    assert audit_agentic_environment(tmp_path) == []


def test_agentic_audit_defaults_to_current_working_directory(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".agents" / "skills" / "demo").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Use when testing demo behavior.\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# README\n", encoding="utf-8")
    (tmp_path / "Roadmap.md").write_text("# Roadmap\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "AGENT_SKILLS.md").write_text("# Skills\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert audit_agentic_environment() == []


def test_agentic_audit_detects_missing_governance(tmp_path: Path) -> None:
    (tmp_path / ".agents" / "skills" / "demo").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Use when testing demo behavior.\n---\n",
        encoding="utf-8",
    )

    findings = audit_agentic_environment(tmp_path)
    assert "missing:AGENTS.md" in findings
    assert "missing:README.md" in findings


def test_agentic_audit_rejects_frontmatter_without_immediate_closing_delimiter(
    tmp_path: Path,
) -> None:
    (tmp_path / ".agents" / "skills" / "demo").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Use when testing demo behavior.\n"
        "# Cuerpo sin cierre\n---\n",
        encoding="utf-8",
    )
    for relative in ("AGENTS.md", "README.md", "Roadmap.md"):
        (tmp_path / relative).write_text(f"# {relative}\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "AGENT_SKILLS.md").write_text("# Skills\n", encoding="utf-8")

    findings = audit_agentic_environment(tmp_path)

    relative_skill = Path(".agents/skills/demo/SKILL.md")
    assert f"invalid_frontmatter:{relative_skill}" in findings


def test_agentic_audit_requires_ephemeral_git_and_closing_contracts(
    tmp_path: Path,
) -> None:
    for relative in ("AGENTS.md", "README.md", "Roadmap.md"):
        (tmp_path / relative).write_text(f"# {relative}\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "AGENT_SKILLS.md").write_text(
        "# Skills\n", encoding="utf-8"
    )
    for name in ("git-commit-push", "retrospectiva-tecnica-sesion"):
        skill_dir = tmp_path / ".agents" / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Use when testing.\n---\n",
            encoding="utf-8",
        )

    findings = audit_agentic_environment(tmp_path)

    assert "missing_contract:git-commit-push:ephemeral_branch" in findings
    assert "missing_contract:retrospectiva-tecnica-sesion:closing_triggers" in findings


def test_agentic_audit_accepts_explicit_superpowers_references_without_legacy_copy(
    tmp_path: Path,
) -> None:
    (tmp_path / ".agents" / "skills" / "demo").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Use when testing demo behavior.\n---\n\n"
        "**REQUIRED BACKGROUND:** Use superpowers:systematic-debugging.\n",
        encoding="utf-8",
    )
    for relative in ("AGENTS.md", "README.md", "Roadmap.md"):
        (tmp_path / relative).write_text(f"# {relative}\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "AGENT_SKILLS.md").write_text(
        "# Skills\n", encoding="utf-8"
    )

    assert audit_agentic_environment(tmp_path) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    (
        ("Cerrar sesión", "close"),
        ("CERREMOS SESIÓN.", "close"),
        ("Cerrar sesión,", "close"),
        ("Cerrar sesión:", "close"),
        ("Cerrar sesión…", "close"),
        ("Cerremos sesión;", "close"),
        ("Terminamos la sesión", "ignore"),
        ("Este es el final del chat", "ignore"),
        ("Usa retrospectiva-tecnica-sesion", "ignore"),
        ("Por favor, cerrar sesión", "ignore"),
    ),
)
def test_closing_request_accepts_only_exact_triggers(
    text: str, expected: str
) -> None:
    assert classify_closing_request(text) == expected


def test_closing_request_confirms_only_valid_trigger_with_ambiguous_work() -> None:
    assert classify_closing_request(
        "Cerrar sesión", ambiguous_open_work=True
    ) == "confirm"
    assert classify_closing_request(
        "Terminamos", ambiguous_open_work=True
    ) == "ignore"


def test_direct_trigger_extraction_rejects_an_added_third_trigger() -> None:
    assert extract_direct_closing_triggers(
        "Los únicos triggers directos son `Cerrar sesión` y `Cerremos sesión`."
    ) == frozenset({"cerrar sesión", "cerremos sesión"})
    assert extract_direct_closing_triggers(
        "Los únicos triggers directos son `Cerrar sesión`, `Terminamos` y `Cerremos sesión`."
    ) == frozenset()


def test_agentic_audit_rejects_a_negated_direct_commit_rule(tmp_path: Path) -> None:
    for relative in ("AGENTS.md", "README.md", "Roadmap.md"):
        (tmp_path / relative).write_text(f"# {relative}\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "AGENT_SKILLS.md").write_text(
        "# Skills\n", encoding="utf-8"
    )
    skill_dir = tmp_path / ".agents" / "skills" / "git-commit-push"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: git-commit-push\ndescription: Use when testing.\n---\n\n"
        "Todo trabajo comienza desde el estado actual de `dev` en una rama efímera nueva.\n"
        "Usar git switch -c.\n"
        "No está prohibido hacer un commit directo en `dev`. `dev` sólo recibe el merge final de una rama efímera validada.\n",
        encoding="utf-8",
    )

    findings = audit_agentic_environment(tmp_path)

    assert "missing_contract:git-commit-push:no_direct_commit_to_dev" in findings


def test_agentic_audit_rejects_negated_ambiguity_and_risk_rules(
    tmp_path: Path,
) -> None:
    for relative in ("AGENTS.md", "README.md", "Roadmap.md"):
        (tmp_path / relative).write_text(f"# {relative}\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "AGENT_SKILLS.md").write_text(
        "# Skills\n", encoding="utf-8"
    )
    skill_dir = tmp_path / ".agents" / "skills" / "retrospectiva-tecnica-sesion"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: retrospectiva-tecnica-sesion\ndescription: Use when testing.\n---\n\n"
        "Los únicos triggers directos son `Cerrar sesión` y `Cerremos sesión`.\n"
        "No solicitar confirmación ante trabajo pendiente ambiguo.\n"
        "Ante riesgo muy alto, no detener el flujo.\n"
        "2. Ejecutar `git fetch` y `git merge origin/dev`.\n"
        "6. Ejecutar `git switch dev`, fusionar la rama efímera y ejecutar `git push origin dev`.\n",
        encoding="utf-8",
    )

    findings = audit_agentic_environment(tmp_path)

    assert "missing_contract:retrospectiva-tecnica-sesion:ambiguous_work" in findings
    assert "missing_contract:retrospectiva-tecnica-sesion:high_risk_gate" in findings


def test_agentic_audit_rejects_unconditional_git_add_all(tmp_path: Path) -> None:
    for relative in ("AGENTS.md", "README.md", "Roadmap.md"):
        (tmp_path / relative).write_text(f"# {relative}\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "AGENT_SKILLS.md").write_text(
        "# Skills\n", encoding="utf-8"
    )
    skill_dir = tmp_path / ".agents" / "skills" / "git-commit-push"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: git-commit-push\ndescription: Use when testing.\n---\n\n"
        "- Todo trabajo comienza desde el estado actual de `dev` en una rama efímera nueva: `feat/<tarea>`, `fix/<tarea>`, `docs/<tarea>` o `chore/<tarea>`.\n"
        "- Está prohibido hacer un commit directo en `dev`. `dev` sólo recibe el merge final de una rama efímera validada.\n"
        "4. Resolver de forma autónoma sólo cuando contratos, contexto y pruebas permiten demostrar la intención. Si es ambigua o de riesgo muy alto, detener el flujo.\n"
        "6. Tras una resolución, usar `git add .` sin revisar el worktree.\n",
        encoding="utf-8",
    )

    findings = audit_agentic_environment(tmp_path)

    assert "missing_contract:git-commit-push:safe_staging" in findings
