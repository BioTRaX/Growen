#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: smoke_bug_report.py
# NG-HEADER: Ubicación: scripts/smoke_bug_report.py
# NG-HEADER: Descripción: Prueba rápida del endpoint /bug-report y escritura en logs/BugReport.log
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations
import os
from pathlib import Path
from fastapi.testclient import TestClient

from services.api import app


def main() -> int:
    c = TestClient(app)
    r = c.post('/bug-report', json={'message': 'smoke test bug report', 'url': 'http://local/test', 'user_agent': 'smoke/1.0'})
    print('status:', r.status_code)
    print('body:', r.json())
    root = Path(__file__).resolve().parents[1]
    p = root / 'logs' / 'BugReport.log'
    print('log_exists:', p.exists())
    if p.exists():
        try:
            tail = p.read_text(encoding='utf-8', errors='ignore').strip().splitlines()[-3:]
            print('tail:')
            for line in tail:
                print(line)
        except Exception as e:
            print('tail_error:', e)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
