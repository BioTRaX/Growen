"""Clear the backend.log file (truncate).

Usage: python scripts/clear_backend_log.py
"""
from pathlib import Path


def main():
    p = Path('logs') / 'backend.log'
    if not p.exists():
        print(f"Log file not found: {p}")
        return
    with p.open('w', encoding='utf-8') as fh:
        fh.truncate(0)
    print(f"Cleared log: {p}")


if __name__ == '__main__':
    main()
