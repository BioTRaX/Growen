#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: migrate_legacy_telegram_sessions.py
# NG-HEADER: Ubicación: scripts/migrate_legacy_telegram_sessions.py
# NG-HEADER: Descripción: Anonimiza sesiones Telegram legacy de forma transaccional.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Convierte telegram:<id> a claves opacas sin imprimir IDs."""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select, update

from db.models import ChatMessage, ChatRun, ChatSession
from db.session import SessionLocal
from services.chat.external_identity import opaque_conversation_key, subject_hmac


async def migrate(*, apply_changes: bool) -> int:
    converted = 0
    async with SessionLocal() as db:
        sessions = (await db.scalars(select(ChatSession).where(ChatSession.session_id.like("telegram:%")))).all()
        for legacy in sessions:
            raw = legacy.session_id.partition(":")[2]
            if not raw.isdigit():
                continue
            digest = subject_hmac("telegram", raw)
            conversation_key = opaque_conversation_key("telegram", raw, raw)
            new_id = f"telegram:{conversation_key[:48]}"
            converted += 1
            if not apply_changes:
                continue
            replacement = ChatSession(
                session_id=new_id,
                user_identifier=f"tg:{digest[:24]}",
                status=legacy.status,
                tags=legacy.tags,
                admin_notes=legacy.admin_notes,
                channel="telegram",
                assigned_user_id=legacy.assigned_user_id,
                detected_intent=legacy.detected_intent,
                sentiment=legacy.sentiment,
                classification_confidence=legacy.classification_confidence,
                classification_model=legacy.classification_model,
                problem_signals=legacy.problem_signals,
                classified_at=legacy.classified_at,
                reviewed_at=legacy.reviewed_at,
                reviewed_by_user_id=legacy.reviewed_by_user_id,
                created_at=legacy.created_at,
                last_message_at=legacy.last_message_at,
                updated_at=legacy.updated_at,
                subject_hmac=digest,
                conversation_key=conversation_key,
            )
            db.add(replacement)
            await db.flush()
            await db.execute(update(ChatMessage).where(ChatMessage.session_id == legacy.session_id).values(session_id=new_id))
            await db.execute(update(ChatRun).where(ChatRun.session_id == legacy.session_id).values(session_id=new_id))
            await db.delete(legacy)
        if apply_changes:
            await db.commit()
        else:
            await db.rollback()
    return converted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Aplica la migración; por defecto sólo dry-run")
    args = parser.parse_args()
    count = asyncio.run(migrate(apply_changes=args.apply))
    print(f"Sesiones candidatas: {count}. Modo: {'apply' if args.apply else 'dry-run'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
