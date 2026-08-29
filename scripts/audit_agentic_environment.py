#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: audit_agentic_environment.py
# NG-HEADER: Ubicación: scripts/audit_agentic_environment.py
# NG-HEADER: Descripción: Auditoría determinista del entorno agéntico de Growen.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import re
from pathlib import Path


REQUIRED_FILES = ("AGENTS.md", "README.md", "Roadmap.md", "docs/AGENT_SKILLS.md")
SKILL_RE = re.compile(
    r"\A---\r?\nname: ([a-z0-9-]+)\r?\ndescription: ([^\r\n]+)\r?\n---(?:\r?\n|\Z)"
)


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
