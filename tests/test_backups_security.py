#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_backups_security.py
# NG-HEADER: Ubicación: tests/test_backups_security.py
# NG-HEADER: Descripción: Verifica que pg_dump no exponga contraseñas ni use shell.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import subprocess

from services.backups import DBConn, _run_docker_pg_dump


def test_docker_pg_dump_uses_argument_vector_without_password(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    secret = "clave con espacios y $metacaracteres"
    result = _run_docker_pg_dump(
        "growen-db",
        DBConn(user="growen", password=secret, host="db", port=5432, dbname="growen"),
        tmp_path / "backup.dump",
    )

    assert result.returncode == 0
    assert calls[0][:4] == ["docker", "exec", "growen-db", "pg_dump"]
    assert "bash" not in calls[0]
    assert "-lc" not in calls[0]
    assert all(secret not in argument for call in calls for argument in call)
