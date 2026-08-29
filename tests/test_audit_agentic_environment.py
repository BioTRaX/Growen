#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_audit_agentic_environment.py
# NG-HEADER: Ubicación: tests/test_audit_agentic_environment.py
# NG-HEADER: Descripción: Pruebas del auditor del entorno agéntico.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from pathlib import Path

from scripts.audit_agentic_environment import audit_agentic_environment


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
