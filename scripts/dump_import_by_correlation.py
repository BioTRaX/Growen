"""Utility: Dump AuditLog and ImportLog entries for a given correlation_id.

Usage (from repo root):
  python scripts/dump_import_by_correlation.py <correlation_id>

This connects using the project's DB settings and prints JSON of relevant rows.
"""
import sys
import json
from sqlalchemy import create_engine, text
from sqlalchemy import select
from sqlalchemy.engine import Engine
from agent_core.config import settings
from db.models import AuditLog, ImportLog


def _sync_engine_from_db_url(db_url: str) -> Engine:
    # Convert async driver names to sync equivalents when possible
    # e.g. 'postgresql+asyncpg://' -> 'postgresql://', 'sqlite+aiosqlite://' -> 'sqlite:///'
    if db_url.startswith('sqlite+aiosqlite:'):
        return create_engine(db_url.replace('sqlite+aiosqlite:', 'sqlite:'), future=True)
    if '+asyncpg' in db_url:
        return create_engine(db_url.replace('+asyncpg', ''), future=True)
    if '+aiosqlite' in db_url:
        return create_engine(db_url.replace('+aiosqlite', ''), future=True)
    # Fallback: try to create engine directly
    return create_engine(db_url, future=True)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/dump_import_by_correlation.py <correlation_id>")
        sys.exit(2)
    cid = sys.argv[1]
    db_url = settings.db_url
    eng = _sync_engine_from_db_url(db_url)
    audits = []
    import_logs = []
    with eng.connect() as conn:
        # AuditLog: JSON meta filter depends on DB dialect; use text query fallback
        try:
            # Try JSON extraction for Postgres
            q = text('SELECT id, action, "table", entity_id, metadata, created_at FROM audit_log WHERE metadata->>\'correlation_id\' = :cid ORDER BY created_at ASC')
            rows = conn.execute(q, {"cid": cid}).fetchall()
            for r in rows:
                audits.append({
                    "id": r[0],
                    "action": r[1],
                    "table": r[2],
                    "entity_id": r[3],
                    "meta": r[4],
                    "created_at": str(r[5]),
                })
        except Exception:
            # Fallback: pull all audit rows and filter in Python (slower)
            q = text('SELECT id, action, "table", entity_id, metadata, created_at FROM audit_log ORDER BY created_at ASC LIMIT 1000')
            rows = conn.execute(q).fetchall()
            for r in rows:
                meta = r[4] or {}
                if meta.get('correlation_id') == cid:
                    audits.append({
                        "id": r[0],
                        "action": r[1],
                        "table": r[2],
                        "entity_id": r[3],
                        "meta": meta,
                        "created_at": str(r[5]),
                    })

        try:
            q2 = text("SELECT id, purchase_id, correlation_id, level, stage, event, details, created_at FROM import_logs WHERE correlation_id = :cid ORDER BY created_at ASC")
            rows2 = conn.execute(q2, {"cid": cid}).fetchall()
            for r in rows2:
                import_logs.append({
                    "id": r[0],
                    "purchase_id": r[1],
                    "correlation_id": r[2],
                    "level": r[3],
                    "stage": r[4],
                    "event": r[5],
                    "details": r[6],
                    "created_at": str(r[7]),
                })
        except Exception:
            pass

    out = {"correlation_id": cid, "audit_logs": audits, "import_logs": import_logs}
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
