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


@pytest.fixture(autouse=True)
def healthy_catalog_audit_heartbeat(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "_catalog_audit_heartbeat_status",
        lambda: (True, "heartbeat vigente"),
        raising=False,
    )


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


class FakeListSession(FakeSession):
    def __init__(self, rows: list[object]) -> None:
        super().__init__()
        self.rows = rows

    async def execute(self, _statement):
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: self.rows)
        )


def service_row() -> SimpleNamespace:
    return SimpleNamespace(
        status="stopped",
        started_at=None,
        uptime_s=0,
        meta={},
        last_error=None,
    )


class FakeObservedProcess:
    def __init__(self, pid: int, ppid: int, cwd, *, module: str = "services.jobs.catalog_audit_jobs") -> None:
        self.info = {
            "pid": pid,
            "ppid": ppid,
            "cwd": str(cwd),
            "create_time": 1_700_000_000.0,
            "cmdline": [
                "python.exe", "-m", "dramatiq", module,
                "--processes", "1", "--threads", "1", "--queues", "catalog_audit",
            ],
        }


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


def test_docker_probe_allows_normal_desktop_latency(monkeypatch, tmp_path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}", encoding="utf-8")
    captured: dict[str, object] = {}

    monkeypatch.setattr(orchestrator, "COMPOSE_FILE", compose_file)
    monkeypatch.setattr(orchestrator.shutil, "which", lambda _name: "docker.exe")
    monkeypatch.delenv("DOCKER_PROBE_TIMEOUT_S", raising=False)

    def fake_run(*_args, **kwargs):
        captured["timeout"] = kwargs["timeout"]
        return SimpleNamespace(returncode=0, stdout="29.6.1", stderr="")

    monkeypatch.setattr(orchestrator.subprocess, "run", fake_run)

    assert orchestrator._has_docker() is True
    assert captured["timeout"] == 8.0


@pytest.mark.asyncio
async def test_list_reconciles_market_worker_started_outside_panel(monkeypatch) -> None:
    market = SimpleNamespace(
        id=9,
        name="market_worker",
        status="failed",
        auto_start=False,
        started_at=None,
        uptime_s=0,
        meta={},
        last_error="Docker no disponible",
    )
    db = FakeListSession([market])

    async def fake_ensure_row(_db, _name):
        return market

    async def fake_to_thread(func, *args, **kwargs):
        assert func is services_admin._status
        return ServiceStatus(name="market_worker", status="running", ok=True, detail="healthy")

    monkeypatch.setattr(services_admin, "_ensure_row", fake_ensure_row)
    monkeypatch.setattr(services_admin.asyncio, "to_thread", fake_to_thread)

    response = await services_admin.list_services(db=db)

    assert response["items"][0]["status"] == "running"
    assert market.last_error is None
    assert market.started_at is not None


def test_enrichment_worker_start_and_stop_orchestration(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_ENRICHMENT_WORKER_PROC", None)
    monkeypatch.setattr(orchestrator.psutil, "process_iter", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "_ensure_local_redis", lambda: (True, "Redis OK"))

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script = scripts_dir / "start_worker_enrichment.cmd"
    script.write_text("@echo off\n", encoding="utf-8")

    class FakeProc:
        pid = 7788
        def poll(self):
            return None
        def terminate(self):
            pass
        def wait(self, timeout=None):
            pass

    fake_proc = FakeProc()
    monkeypatch.setattr(orchestrator, "_start_process_with_log", lambda cmd, log: (fake_proc, tmp_path / "logs" / log))

    status_start = orchestrator.start_service("enrichment_worker", correlation_id="test-cid")
    assert status_start.ok is True
    assert status_start.status == "running"
    assert "7788" in status_start.detail

    status_curr = orchestrator.status_service("enrichment_worker")
    assert status_curr.status == "running"
    assert status_curr.pid == 7788

    status_stop = orchestrator.stop_service("enrichment_worker", correlation_id="test-cid")
    assert status_stop.ok is True
    assert status_stop.status == "stopped"


def test_catalog_audit_worker_uses_local_launcher_without_compose(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_CATALOG_AUDIT_WORKER_PROC", None, raising=False)
    monkeypatch.setattr(orchestrator.psutil, "process_iter", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "_ensure_local_redis", lambda: (True, "Redis OK"))
    monkeypatch.setattr(orchestrator, "_has_docker", lambda: True)
    monkeypatch.setattr(orchestrator, "_compose", lambda _args: (_ for _ in ()).throw(AssertionError("no debe usar Compose")))

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "start_worker_catalog_audit.cmd").write_text("@echo off\n", encoding="utf-8")

    fake_proc = SimpleNamespace(pid=8899, poll=lambda: None)
    monkeypatch.setattr(
        orchestrator,
        "_start_process_with_log",
        lambda command, log: (fake_proc, tmp_path / "logs" / log),
    )

    result = orchestrator.start_service("catalog_audit_worker", correlation_id="audit-cid")

    assert result.status == "running"
    assert result.pid == 8899
    assert result.meta == {
        "runtime_mode": "local",
        "runtime_root": str(tmp_path.resolve()),
        "process_pids": [8899],
        "managed": True,
    }


def test_catalog_audit_status_groups_dramatiq_parent_and_child(monkeypatch, tmp_path) -> None:
    processes = [
        FakeObservedProcess(9100, 100, tmp_path),
        FakeObservedProcess(9101, 9100, tmp_path),
    ]
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_CATALOG_AUDIT_WORKER_PROC", None, raising=False)
    monkeypatch.setattr(orchestrator.psutil, "process_iter", lambda *_args, **_kwargs: processes)

    result = orchestrator.status_service("catalog_audit_worker")

    assert result.status == "running"
    assert result.pid == 9100
    assert result.meta["process_pids"] == [9100, 9101]
    assert result.meta["runtime_root"] == str(tmp_path.resolve())


def test_catalog_audit_start_is_idempotent_for_existing_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_CATALOG_AUDIT_WORKER_PROC", None, raising=False)
    monkeypatch.setattr(
        orchestrator.psutil,
        "process_iter",
        lambda *_args, **_kwargs: [
            FakeObservedProcess(9120, 100, tmp_path),
            FakeObservedProcess(9121, 9120, tmp_path),
        ],
    )
    monkeypatch.setattr(
        orchestrator,
        "_start_process_with_log",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no debe iniciar otro worker")),
    )

    result = orchestrator.start_service("catalog_audit_worker", correlation_id="audit-cid")

    assert result.status == "running"
    assert result.pid == 9120
    assert result.meta["process_pids"] == [9120, 9121]
    assert result.detail == "noop: already running PID 9120"


def test_catalog_audit_status_degrades_when_heartbeat_is_stale(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_CATALOG_AUDIT_WORKER_PROC", None, raising=False)
    monkeypatch.setattr(
        orchestrator,
        "_catalog_audit_heartbeat_status",
        lambda: (False, "heartbeat ausente"),
    )
    monkeypatch.setattr(
        orchestrator.psutil,
        "process_iter",
        lambda *_args, **_kwargs: [FakeObservedProcess(9150, 100, tmp_path)],
    )

    result = orchestrator.status_service("catalog_audit_worker")

    assert result.status == "degraded"
    assert result.ok is False
    assert "heartbeat ausente" in result.detail
    assert result.meta["managed"] is True


def test_catalog_audit_detection_requires_exact_queue() -> None:
    assert orchestrator._is_catalog_audit_process([
        "python", "-m", "dramatiq", "services.jobs.catalog_audit_jobs", "--queues", "catalog_audit_retry",
    ]) is False
    assert orchestrator._is_catalog_audit_process([
        "python", "-m", "dramatiq", "services.jobs.catalog_audit_jobs", "--queues=catalog_audit",
    ]) is True


def test_catalog_audit_status_rejects_worker_from_another_worktree(monkeypatch, tmp_path) -> None:
    foreign_root = tmp_path.parent / "foreign-worktree"
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_CATALOG_AUDIT_WORKER_PROC", None, raising=False)
    monkeypatch.setattr(
        orchestrator.psutil,
        "process_iter",
        lambda *_args, **_kwargs: [FakeObservedProcess(9200, 100, foreign_root)],
    )

    result = orchestrator.status_service("catalog_audit_worker")

    assert result.status == "degraded"
    assert result.ok is False
    assert result.meta["runtime_root"] == str(foreign_root.resolve())
    assert "otro worktree" in result.detail


def test_catalog_audit_status_rejects_multiple_worker_roots(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_CATALOG_AUDIT_WORKER_PROC", None, raising=False)
    monkeypatch.setattr(
        orchestrator.psutil,
        "process_iter",
        lambda *_args, **_kwargs: [
            FakeObservedProcess(9300, 100, tmp_path),
            FakeObservedProcess(9400, 200, tmp_path),
        ],
    )

    result = orchestrator.status_service("catalog_audit_worker")

    assert result.status == "degraded"
    assert result.ok is False
    assert result.meta["process_pids"] == [9300, 9400]
    assert "2 consumidores" in result.detail


def test_catalog_audit_stop_refuses_ambiguous_consumers(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_CATALOG_AUDIT_WORKER_PROC", None, raising=False)
    monkeypatch.setattr(
        orchestrator.psutil,
        "process_iter",
        lambda *_args, **_kwargs: [
            FakeObservedProcess(9500, 100, tmp_path),
            FakeObservedProcess(9600, 200, tmp_path),
        ],
    )
    terminated: list[int] = []
    monkeypatch.setattr(orchestrator, "_terminate_process_tree", lambda pid: terminated.append(pid), raising=False)

    result = orchestrator.stop_service("catalog_audit_worker", correlation_id="audit-cid")

    assert result.status == "degraded"
    assert result.ok is False
    assert terminated == []


def test_catalog_audit_start_fails_closed_when_redis_is_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_CATALOG_AUDIT_WORKER_PROC", None, raising=False)
    monkeypatch.setattr(orchestrator.psutil, "process_iter", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "_ensure_local_redis", lambda: (False, "Redis no disponible"))
    launched: list[object] = []
    monkeypatch.setattr(orchestrator, "_start_process_with_log", lambda *_args: launched.append(True))

    result = orchestrator.start_service("catalog_audit_worker", correlation_id="audit-cid")

    assert result.status == "failed"
    assert result.ok is False
    assert result.detail == "Redis no disponible"
    assert launched == []


def test_catalog_audit_start_fails_closed_when_launcher_is_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_CATALOG_AUDIT_WORKER_PROC", None, raising=False)
    monkeypatch.setattr(orchestrator.psutil, "process_iter", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "_ensure_local_redis", lambda: (True, "Redis OK"))
    launched: list[object] = []
    monkeypatch.setattr(orchestrator, "_start_process_with_log", lambda *_args: launched.append(True))

    result = orchestrator.start_service("catalog_audit_worker", correlation_id="audit-cid")

    assert result.status == "failed"
    assert result.ok is False
    assert result.detail == "Script not found"
    assert launched == []


def test_catalog_audit_stop_terminates_only_the_verified_local_tree(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_CATALOG_AUDIT_WORKER_PROC", None, raising=False)
    monkeypatch.setattr(
        orchestrator.psutil,
        "process_iter",
        lambda *_args, **_kwargs: [
            FakeObservedProcess(9800, 100, tmp_path),
            FakeObservedProcess(9801, 9800, tmp_path),
        ],
    )
    terminated: list[int] = []
    monkeypatch.setattr(orchestrator, "_terminate_process_tree", lambda pid: terminated.append(pid))

    result = orchestrator.stop_service("catalog_audit_worker", correlation_id="audit-cid")

    assert result.status == "stopped"
    assert result.ok is True
    assert terminated == [9800]
    assert result.meta["runtime_mode"] == "none"


def test_catalog_audit_stop_allows_verified_tree_with_stale_heartbeat(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "_CATALOG_AUDIT_WORKER_PROC", None, raising=False)
    monkeypatch.setattr(orchestrator, "_catalog_audit_heartbeat_status", lambda: (False, "heartbeat ausente"))
    monkeypatch.setattr(
        orchestrator.psutil,
        "process_iter",
        lambda *_args, **_kwargs: [FakeObservedProcess(9850, 100, tmp_path)],
    )
    terminated: list[int] = []
    monkeypatch.setattr(orchestrator, "_terminate_process_tree", lambda pid: terminated.append(pid))

    result = orchestrator.stop_service("catalog_audit_worker", correlation_id="audit-cid")

    assert result.status == "stopped"
    assert terminated == [9850]


def test_process_tree_terminates_children_before_parent(monkeypatch) -> None:
    order: list[int] = []

    class FakeProcessTreeNode:
        def __init__(self, pid: int) -> None:
            self.pid = pid

        def children(self, recursive: bool = False):
            assert recursive is True
            return [FakeProcessTreeNode(9901), FakeProcessTreeNode(9902)]

        def terminate(self) -> None:
            order.append(self.pid)

    monkeypatch.setattr(orchestrator.psutil, "Process", FakeProcessTreeNode)
    monkeypatch.setattr(orchestrator.psutil, "wait_procs", lambda processes, timeout: (processes, []))

    orchestrator._terminate_process_tree(9900)

    assert order == [9901, 9902, 9900]


@pytest.mark.asyncio
async def test_list_reconciles_catalog_audit_runtime_metadata(monkeypatch) -> None:
    audit = SimpleNamespace(
        id=10,
        name="catalog_audit_worker",
        status="stopped",
        auto_start=True,
        started_at=None,
        uptime_s=0,
        meta={},
        last_error="compose conflict",
    )
    db = FakeListSession([audit])

    async def fake_ensure_row(_db, _name):
        return audit

    async def fake_to_thread(func, *args, **kwargs):
        assert func is services_admin._status
        return ServiceStatus(
            name="catalog_audit_worker",
            status="running",
            ok=True,
            detail="Running PID 9700",
            pid=9700,
                meta={"runtime_mode": "local", "runtime_root": "C:/Growen", "process_pids": [9700], "managed": True},
        )

    monkeypatch.setattr(services_admin, "_ensure_row", fake_ensure_row)
    monkeypatch.setattr(services_admin.asyncio, "to_thread", fake_to_thread)

    response = await services_admin.list_services(db=db)

    assert response["items"][0]["status"] == "running"
    assert response["items"][0]["runtime_mode"] == "local"
    assert response["items"][0]["pid"] == 9700
    assert response["items"][0]["runtime_root"] == "C:/Growen"
    assert response["items"][0]["can_stop"] is True
    assert audit.last_error is None


def test_service_error_summary_prioritizes_causal_line() -> None:
    detail = "\n".join(
        [
            'level=warning msg="volume growen_pgdata is left untouched"',
            "Container growen-postgres Running",
            'Error response from daemon: Conflict. The container name "/growen-catalog-audit-worker" is already in use.',
        ]
    )

    assert services_admin._summarize_service_error(detail) == (
        'Error response from daemon: Conflict. The container name '
        '"/growen-catalog-audit-worker" is already in use.'
    )

