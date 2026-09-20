#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_create_service_skill.py
# NG-HEADER: Ubicación: tests/test_create_service_skill.py
# NG-HEADER: Descripción: Contrato agéntico para mutaciones estructuradas de SiYuan por MCP.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_create_service_routes_siyuan_mutations_to_dedicated_reference() -> None:
    skill = (ROOT / ".agents/skills/create-service/SKILL.md").read_text(
        encoding="utf-8"
    )
    reference = ROOT / ".agents/skills/create-service/references/siyuan-mcp-mutations.md"

    assert "siyuan-mcp-mutations.md" in skill
    assert reference.is_file()

    guidance = reference.read_text(encoding="utf-8").lower()
    for required_contract in (
        "historial antes de mutar",
        "mcp real",
        "api semántica",
        "verificación visual",
        "select",
        "estado incierto",
    ):
        assert required_contract in guidance
