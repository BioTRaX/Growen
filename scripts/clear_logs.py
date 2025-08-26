import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"


def truncate_file(p: Path) -> str:
    try:
        with open(p, "w", encoding="utf-8"):
            pass
        return f"cleared: {p.name}"
    except Exception as e:
        return f"skip (locked): {p.name} -> {e}"


def main() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    files = [
        LOGS / "backend.log",
        LOGS / "frontend.log",
        LOGS / "start.log",
        LOGS / "fix_deps.log",
    ]
    for f in files:
        if f.exists():
            print(truncate_file(f))
        else:
            # Ensure file exists (empty)
            try:
                f.touch()
                print(f"created: {f.name}")
            except Exception as e:
                print(f"skip (create failed): {f.name} -> {e}")

    migdir = LOGS / "migrations"
    if migdir.exists():
        removed = 0
        for child in migdir.glob("*"):
            try:
                if child.is_file():
                    child.unlink()
                    removed += 1
            except Exception as e:
                print(f"skip (rm): {child.name} -> {e}")
        print(f"cleared migration logs: {removed} files")
    else:
        migdir.mkdir(parents=True, exist_ok=True)
        print("created migrations log dir")


if __name__ == "__main__":
    main()
