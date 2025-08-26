"""Local development server runner.

Ensures Windows uses the Selector event loop policy before Uvicorn starts,
so psycopg async works correctly.
"""

from __future__ import annotations

import os
import sys
import asyncio
import uvicorn


def _apply_windows_loop_policy() -> None:
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            # If anything goes wrong, proceed with default policy
            pass


def main() -> None:
    _apply_windows_loop_policy()
    host = os.getenv("GROWEN_HOST", "127.0.0.1")
    port = int(os.getenv("GROWEN_PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    uvicorn.run(
        "services.api:app",
        host=host,
        port=port,
        reload=True,
        log_level=log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
