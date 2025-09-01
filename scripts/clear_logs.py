# NG-HEADER: Nombre de archivo: clear_logs.py
# NG-HEADER: Ubicación: scripts/clear_logs.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"


def _truncate_win32(p: Path):
    try:
        import ctypes
        from ctypes import wintypes

        GENERIC_WRITE = 0x40000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        FILE_SHARE_DELETE = 0x00000004
        OPEN_EXISTING = 3
        FILE_ATTRIBUTE_NORMAL = 0x80
        FILE_BEGIN = 0

        CreateFileW = ctypes.windll.kernel32.CreateFileW
        CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                wintypes.HANDLE]
        CreateFileW.restype = wintypes.HANDLE

        SetFilePointerEx = ctypes.windll.kernel32.SetFilePointerEx
        SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                                     ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
        SetFilePointerEx.restype = wintypes.BOOL

        SetEndOfFile = ctypes.windll.kernel32.SetEndOfFile
        SetEndOfFile.argtypes = [wintypes.HANDLE]
        SetEndOfFile.restype = wintypes.BOOL

        CloseHandle = ctypes.windll.kernel32.CloseHandle
        CloseHandle.argtypes = [wintypes.HANDLE]
        CloseHandle.restype = wintypes.BOOL

        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        h = CreateFileW(str(p), GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                        None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
        if h == INVALID_HANDLE_VALUE:
            return False, "CreateFileW failed"
        try:
            new_pos = ctypes.c_longlong(0)
            if not SetFilePointerEx(h, 0, ctypes.byref(new_pos), FILE_BEGIN):
                return False, "SetFilePointerEx failed"
            if not SetEndOfFile(h):
                return False, "SetEndOfFile failed"
            return True, "cleared (win32)"
        finally:
            CloseHandle(h)
    except Exception as e:
        return False, f"win32 truncate error: {e}"


def truncate_file(p: Path) -> str:
    # Try normal truncate first
    try:
        with open(p, "w", encoding="utf-8"):
            pass
        return f"cleared: {p.name}"
    except PermissionError as e:
        try:
            with open(p, "r+b") as fh:
                fh.truncate(0)
            return f"cleared: {p.name}"
        except Exception:
            if os.name == "nt":
                ok, msg = _truncate_win32(p)
                if ok:
                    return f"cleared: {p.name}"
                return f"skip (locked): {p.name} -> {msg}"
            return f"skip (locked): {p.name} -> {e}"
    except Exception as e:
        return f"skip: {p.name} -> {e}"


def main() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    files = [
        LOGS / "backend.log",
        LOGS / "frontend.log",
        LOGS / "start.log",
        LOGS / "fix_deps.log",
    LOGS / "run_api.log",
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
