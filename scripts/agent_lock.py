#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: agent_lock.py
# NG-HEADER: Ubicación: scripts/agent_lock.py
# NG-HEADER: Descripción: Locks de coordinación entre agentes concurrentes sobre el mismo worktree.
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Coordinación de "Agent Awareness" para agentes concurrentes en Growen.

Todos los agentes (Copilot, Codex, Gemini CLI, Antigravity, etc.) comparten un
único worktree físico. Antes de iniciar un cambio amplio o de larga duración
sobre una skill, doc de gobernanza o área sensible del código, un agente debe
adquirir un lock lógico por ámbito (`scope`). El lock es un archivo JSON creado
de forma atómica bajo `.agents/state/locks/`; no reemplaza a Git ni bloquea el
sistema de archivos, es una señal cooperativa que otro agente puede leer antes
de tocar el mismo ámbito.

Uso:
    python scripts/agent_lock.py acquire <scope> --agent <nombre> --reason <texto> [--ttl-minutes 30]
    python scripts/agent_lock.py renew <scope> --agent <nombre> [--ttl-minutes 30]
    python scripts/agent_lock.py release <scope> --agent <nombre> [--force]
    python scripts/agent_lock.py status [<scope>]
    python scripts/agent_lock.py list
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_TTL_MINUTES = 30
LOCKS_DIRNAME = Path(".agents") / "state" / "locks"


class LockConflictError(RuntimeError):
    """El ámbito ya está tomado por otro agente y no expiró."""


@dataclass
class LockRecord:
    scope: str
    agent: str
    session_id: str
    pid: int
    host: str
    reason: str
    acquired_at: float
    expires_at: float

    def is_expired(self, *, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at


def _slug(scope: str) -> str:
    normalized = scope.strip().strip("/").replace("\\", "/")
    return normalized.replace("/", "__") + ".json"


def _locks_dir(root: Path) -> Path:
    directory = root / LOCKS_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _lock_path(root: Path, scope: str) -> Path:
    return _locks_dir(root) / _slug(scope)


def _read_lock(path: Path) -> LockRecord | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return LockRecord(**data)


def _write_lock(path: Path, record: LockRecord) -> None:
    payload = json.dumps(asdict(record), ensure_ascii=False, indent=2)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, path)


def acquire(
    root: Path,
    scope: str,
    agent: str,
    *,
    session_id: str = "",
    reason: str = "",
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
) -> LockRecord:
    """Crea el lock de forma atómica. Falla si otro agente lo sostiene vigente."""
    path = _lock_path(root, scope)
    existing = _read_lock(path)
    if existing is not None and not existing.is_expired():
        if existing.agent == agent:
            return existing
        raise LockConflictError(
            f"scope '{scope}' bloqueado por '{existing.agent}' "
            f"(motivo: {existing.reason!r}, expira en "
            f"{max(0, int(existing.expires_at - time.time()))}s)"
        )

    now = time.time()
    record = LockRecord(
        scope=scope,
        agent=agent,
        session_id=session_id,
        pid=os.getpid(),
        host=socket.gethostname(),
        reason=reason,
        acquired_at=now,
        expires_at=now + ttl_minutes * 60,
    )
    _write_lock(path, record)
    return record


def renew(
    root: Path,
    scope: str,
    agent: str,
    *,
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
) -> LockRecord:
    """Extiende un lock activo sin cambiar su propietario ni inicio."""
    path = _lock_path(root, scope)
    existing = _read_lock(path)
    if existing is None or existing.is_expired():
        raise LockConflictError(f"scope '{scope}' no tiene un lock activo renovable")
    if existing.agent != agent:
        raise LockConflictError(f"scope '{scope}' pertenece a '{existing.agent}'")
    existing.expires_at = time.time() + ttl_minutes * 60
    existing.pid = os.getpid()
    existing.host = socket.gethostname()
    _write_lock(path, existing)
    return existing


def release(root: Path, scope: str, agent: str, *, force: bool = False) -> bool:
    path = _lock_path(root, scope)
    existing = _read_lock(path)
    if existing is None:
        return False
    if existing.agent != agent and not force:
        raise LockConflictError(
            f"scope '{scope}' pertenece a '{existing.agent}'; use --force sólo si "
            "se confirmó que esa sesión terminó o quedó abandonada"
        )
    path.unlink()
    return True


def status(root: Path, scope: str | None = None) -> list[LockRecord]:
    directory = _locks_dir(root)
    records: list[LockRecord] = []
    for lock_file in sorted(directory.glob("*.json")):
        record = _read_lock(lock_file)
        if record is None:
            continue
        if scope is not None and record.scope != scope:
            continue
        records.append(record)
    return records


def _print_record(record: LockRecord) -> None:
    state = "expirado" if record.is_expired() else "activo"
    print(
        f"[{state}] scope={record.scope} agent={record.agent} "
        f"pid={record.pid} host={record.host} reason={record.reason!r} "
        f"expires_at={time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record.expires_at))}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Locks de coordinación entre agentes Growen.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    acquire_parser = subparsers.add_parser("acquire", help="Adquirir un lock por ámbito")
    acquire_parser.add_argument("scope")
    acquire_parser.add_argument("--agent", required=True)
    acquire_parser.add_argument("--session-id", default="")
    acquire_parser.add_argument("--reason", default="")
    acquire_parser.add_argument("--ttl-minutes", type=int, default=DEFAULT_TTL_MINUTES)

    renew_parser = subparsers.add_parser("renew", help="Renovar un lock activo propio")
    renew_parser.add_argument("scope")
    renew_parser.add_argument("--agent", required=True)
    renew_parser.add_argument("--ttl-minutes", type=int, default=DEFAULT_TTL_MINUTES)

    release_parser = subparsers.add_parser("release", help="Liberar un lock por ámbito")
    release_parser.add_argument("scope")
    release_parser.add_argument("--agent", required=True)
    release_parser.add_argument("--force", action="store_true")

    status_parser = subparsers.add_parser("status", help="Ver el lock de un ámbito")
    status_parser.add_argument("scope", nargs="?")

    subparsers.add_parser("list", help="Listar todos los locks registrados")

    args = parser.parse_args(argv)
    root = Path.cwd()

    if args.command == "acquire":
        try:
            record = acquire(
                root,
                args.scope,
                args.agent,
                session_id=args.session_id,
                reason=args.reason,
                ttl_minutes=args.ttl_minutes,
            )
        except LockConflictError as exc:
            print(f"CONFLICTO: {exc}", file=sys.stderr)
            return 1
        _print_record(record)
        return 0

    if args.command == "release":
        try:
            released = release(root, args.scope, args.agent, force=args.force)
        except LockConflictError as exc:
            print(f"CONFLICTO: {exc}", file=sys.stderr)
            return 1
        print("liberado" if released else "no existía lock para ese scope")
        return 0

    if args.command == "renew":
        try:
            record = renew(
                root,
                args.scope,
                args.agent,
                ttl_minutes=args.ttl_minutes,
            )
        except LockConflictError as exc:
            print(f"CONFLICTO: {exc}", file=sys.stderr)
            return 1
        _print_record(record)
        return 0

    if args.command in ("status", "list"):
        scope = getattr(args, "scope", None)
        records = status(root, scope)
        if not records:
            print("Sin locks registrados" if scope is None else "Sin lock para ese scope")
            return 0
        for record in records:
            _print_record(record)
        return 0

    parser.error(f"comando desconocido: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
