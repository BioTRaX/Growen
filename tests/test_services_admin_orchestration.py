#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_services_admin_orchestration.py
# NG-HEADER: Ubicación: tests/test_services_admin_orchestration.py
# NG-HEADER: Descripción: Regresiones de ejecución no bloqueante y rollback del panel de servicios.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from types import SimpleNamespace

import pytest

from services.orchestrator import ServiceStatus
from services import orchestrator
from services.routers import services_admin


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def service_row() -> SimpleNamespace:
    return SimpleNamespace(
        status="stopped",
        started_at=None,
        uptime_s=0,
        meta={},
        last_error=None,
    )


@pytest.mark.asyncio
async def test_start_runs_orchestrator_through_to_thread(monkeypatch) -> None:
    db = FakeSession()
    calls: list[tuple[object, tuple, dict]] = []

    async def fake_ensure_row(_db, _name):
        return service_row()

    async def fake_to_thread(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return ServiceStatus(name="dramatiq", status="running", ok=True, detail="ready")

    monkeypatch.setattr(services_admin, "_ensure_row", fake_ensure_row)
    monkeypatch.setattr(services_admin.asyncio, "to_thread", fake_to_thread)

    response = await services_admin.start("dramatiq", mode=None, db=db)

    assert response["ok"] is True
    assert calls == [(services_admin._start, ("dramatiq",), {"correlation_id": response["correlation_id"], "mode": None})]
    assert db.commits == 1


@pytest.mark.asyncio
async def test_start_rolls_back_before_recording_orchestrator_failure(monkeypatch) -> None:
    db = FakeSession()

    async def fake_ensure_row(_db, _name):
        return service_row()

    async def failing_to_thread(_func, *_args, **_kwargs):
        raise RuntimeError("compose falló")

    monkeypatch.setattr(services_admin, "_ensure_row", fake_ensure_row)
    monkeypatch.setattr(services_admin.asyncio, "to_thread", failing_to_thread)

    with pytest.raises(Exception) as captured:
        await services_admin.start("dramatiq", mode=None, db=db)

    assert getattr(captured.value, "status_code", None) == 500
    assert db.rollbacks == 1
    assert db.commits == 1
    assert any(getattr(item, "action", None) == "start" for item in db.added)


def test_catalog_dependency_starts_redis_and_waits_for_host_port(monkeypatch) -> None:
    port_checks = iter([False, False, True])
    compose_calls: list[list[str]] = []

    monkeypatch.setattr(orchestrator, "_tcp_port_open", lambda *_args, **_kwargs: next(port_checks))
    monkeypatch.setattr(orchestrator, "_has_docker", lambda: True)
    monkeypatch.setattr(orchestrator.time, "sleep", lambda _seconds: None)

    def fake_compose(args):
        compose_calls.append(args)
        return SimpleNamespace(returncode=0, stdout="started", stderr="")

    monkeypatch.setattr(orchestrator, "_compose", fake_compose)

    ok, detail = orchestrator._ensure_local_redis(timeout_s=1)

    assert ok is True
    assert "iniciado" in detail
    assert compose_calls == [["--profile", "optional", "up", "-d", "redis"]]


def test_local_worker_redirects_output_to_persistent_log(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 4321

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator.subprocess, "Popen", fake_popen)

    process, log_path = orchestrator._start_process_with_log(["worker.cmd"], "worker_catalog.log")

    assert process.pid == 4321
    assert log_path == tmp_path / "logs" / "worker_catalog.log"
    assert captured["stdout"] is not orchestrator.subprocess.PIPE
    assert captured["stderr"] is orchestrator.subprocess.STDOUT
