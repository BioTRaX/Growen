#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: chat_rollout_gate.py
# NG-HEADER: Ubicación: scripts/chat_rollout_gate.py
# NG-HEADER: Descripción: Interfaz de despliegue para consultar y registrar gates de rollout.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import ChatRolloutCheck
from db.session import SessionLocal
from agent_core.config import settings
from services.chat.rollout import get_rollout_state, transition


async def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    require = sub.add_parser("require-phase")
    require.add_argument("phase")
    record = sub.add_parser("record-check")
    record.add_argument("name")
    record.add_argument("status", choices=("passed", "failed"))
    record.add_argument("--code")
    record.add_argument("--latency-ms", type=int)
    activate = sub.add_parser("mark-vue-active")
    activate.add_argument("--apply", action="store_true")
    rollback_vue = sub.add_parser("rollback-vue")
    rollback_vue.add_argument("--apply", action="store_true")
    preflight = sub.add_parser("initialize-preflight")
    preflight.add_argument("--apply", action="store_true")
    preflight.add_argument(
        "--development",
        action="store_true",
        help="Activa sólo el canary y deshabilita el autoavance; exclusivo de dev/test",
    )
    args = parser.parse_args()

    async with SessionLocal() as db:
        state = await get_rollout_state(db, lock=args.command in {"mark-vue-active", "rollback-vue", "initialize-preflight"})
        if args.command == "require-phase":
            print(json.dumps({"eligible": state.phase == args.phase and state.status == "active", "phase": state.phase, "status": state.status}))
            return 0 if state.phase == args.phase and state.status == "active" else 3
        if args.command == "record-check":
            db.add(ChatRolloutCheck(check_name=args.name, phase=state.phase, status=args.status, code=args.code, latency_ms=args.latency_ms))
            await db.commit()
            print(json.dumps({"recorded": True, "phase": state.phase, "status": args.status}))
            return 0
        if not args.apply:
            print(json.dumps({"dry_run": True, "from_phase": state.phase, "command": args.command}))
            return 0
        if args.command == "mark-vue-active":
            if state.phase != "vue_eligible" or state.status != "active":
                return 4
            await transition(db, state, "vue_active", decision="deployment", result="advanced", reason_code="vue_smokes_passed")
        elif args.command == "rollback-vue":
            await transition(db, state, "admin_capped", decision="deployment", result="rollback", reason_code="vue_smoke_failed", pause=True)
        else:
            if state.phase != "disabled" or state.status != "paused":
                return 4
            if args.development and settings.env not in {"dev", "test", "testing"}:
                print(json.dumps({"applied": False, "code": "development_preflight_forbidden"}))
                return 5
            state.auto_advance = not args.development
            await transition(
                db,
                state,
                "preflight",
                decision="development" if args.development else "deployment",
                result="advanced",
                reason_code="development_canary_initialized" if args.development else "preflight_initialized",
            )
        print(json.dumps({"applied": True, "phase": state.phase, "status": state.status}))
        return 0


if __name__ == "__main__":
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    raise SystemExit(asyncio.run(main(), loop_factory=loop_factory))
