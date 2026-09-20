#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_agent_lock.py
# NG-HEADER: Ubicación: tests/test_agent_lock.py
# NG-HEADER: Descripción: Pruebas del coordinador de locks entre agentes concurrentes.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import time
from pathlib import Path

import pytest

from scripts.agent_lock import (
    LockConflictError,
    acquire,
    release,
    renew,
    status,
)

pytestmark = pytest.mark.no_db


def test_acquire_creates_lock_file(tmp_path: Path) -> None:
    record = acquire(tmp_path, ".agents/skills/create-service", "codex", reason="scaffold")

    lock_path = tmp_path / ".agents" / "state" / "locks" / ".agents__skills__create-service.json"
    assert lock_path.is_file()
    assert record.agent == "codex"
    assert record.scope == ".agents/skills/create-service"


def test_acquire_conflicts_when_locked_by_another_agent(tmp_path: Path) -> None:
    acquire(tmp_path, "db/models.py", "codex", ttl_minutes=30)

    with pytest.raises(LockConflictError):
        acquire(tmp_path, "db/models.py", "gemini-cli", ttl_minutes=30)


def test_acquire_is_idempotent_for_same_agent(tmp_path: Path) -> None:
    first = acquire(tmp_path, "db/models.py", "codex", ttl_minutes=30)
    second = acquire(tmp_path, "db/models.py", "codex", ttl_minutes=30)

    assert first.acquired_at == second.acquired_at


def test_acquire_allows_takeover_when_expired(tmp_path: Path) -> None:
    acquire(tmp_path, "db/models.py", "codex", ttl_minutes=-1)

    record = acquire(tmp_path, "db/models.py", "gemini-cli", ttl_minutes=30)
    assert record.agent == "gemini-cli"


def test_release_removes_lock_owned_by_agent(tmp_path: Path) -> None:
    acquire(tmp_path, "db/models.py", "codex", ttl_minutes=30)

    assert release(tmp_path, "db/models.py", "codex") is True
    assert status(tmp_path, "db/models.py") == []


def test_release_refuses_when_owned_by_other_agent(tmp_path: Path) -> None:
    acquire(tmp_path, "db/models.py", "codex", ttl_minutes=30)

    with pytest.raises(LockConflictError):
        release(tmp_path, "db/models.py", "gemini-cli")

    assert release(tmp_path, "db/models.py", "gemini-cli", force=True) is True


def test_release_missing_lock_returns_false(tmp_path: Path) -> None:
    assert release(tmp_path, "db/models.py", "codex") is False


def test_renew_extends_active_lock_owned_by_agent(tmp_path: Path) -> None:
    original = acquire(tmp_path, "git-worktree", "codex", ttl_minutes=1)

    renewed = renew(tmp_path, "git-worktree", "codex", ttl_minutes=60)

    assert renewed.acquired_at == original.acquired_at
    assert renewed.expires_at > original.expires_at
    assert status(tmp_path, "git-worktree")[0].expires_at == renewed.expires_at


def test_renew_rejects_lock_owned_by_another_agent(tmp_path: Path) -> None:
    acquire(tmp_path, "git-worktree", "codex", ttl_minutes=30)

    with pytest.raises(LockConflictError):
        renew(tmp_path, "git-worktree", "gemini-cli", ttl_minutes=30)


def test_renew_rejects_expired_lock(tmp_path: Path) -> None:
    acquire(tmp_path, "git-worktree", "codex", ttl_minutes=-1)

    with pytest.raises(LockConflictError):
        renew(tmp_path, "git-worktree", "codex", ttl_minutes=30)


def test_status_lists_active_and_expired(tmp_path: Path) -> None:
    acquire(tmp_path, "scope-a", "codex", ttl_minutes=30)
    acquire(tmp_path, "scope-b", "gemini-cli", ttl_minutes=-1)

    records = status(tmp_path)
    scopes = {record.scope: record for record in records}
    assert set(scopes) == {"scope-a", "scope-b"}
    assert scopes["scope-a"].is_expired(now=time.time()) is False
    assert scopes["scope-b"].is_expired(now=time.time()) is True
