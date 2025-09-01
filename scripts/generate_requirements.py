# NG-HEADER: Nombre de archivo: generate_requirements.py
# NG-HEADER: Ubicación: scripts/generate_requirements.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parent.parent
pyproject = root / "pyproject.toml"
req_file = root / "requirements.txt"

project = tomllib.loads(pyproject.read_text(encoding="utf-8"))

base_deps = project.get("project", {}).get("dependencies", [])
optional = project.get("project", {}).get("optional-dependencies", {})

seen = set()
lines = []
for dep in base_deps:
    if dep not in seen:
        lines.append(dep)
        seen.add(dep)
for group, deps in optional.items():
    lines.append("")
    lines.append(f"# extras: {group}")
    for dep in deps:
        if dep not in seen:
            lines.append(dep)
            seen.add(dep)

content = "\n".join(lines) + "\n"
if req_file.exists() and req_file.read_text(encoding="utf-8") == content:
    pass
else:
    req_file.write_text(content, encoding="utf-8")
