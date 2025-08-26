import json
import os
import sys
import time

import requests


BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
SUPPLIER_ID = int(os.environ.get("SUPPLIER_ID", "1"))
FILE_PATH = os.environ.get(
    "PRICE_FILE",
    os.path.join(os.path.dirname(__file__), "..", "Devs", "ListaPrecios_export_1753909730978.xlsx"),
)


def main():
    s = requests.Session()
    s.headers["Origin"] = "http://localhost:5173"

    # Login admin (assumes seeded admin)
    r = s.post(
        f"{BASE}/auth/login",
        json={"identifier": "admin", "password": "admin1234"},
        timeout=30,
    )
    print("login:", r.status_code, r.text)
    r.raise_for_status()
    csrf = s.cookies.get("csrf_token")
    if not csrf:
        print("No CSRF cookie after login; aborting.")
        sys.exit(1)

    # Dry-run upload to create a job
    with open(FILE_PATH, "rb") as f:
        files = {"file": (os.path.basename(FILE_PATH), f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = s.post(
            f"{BASE}/suppliers/{SUPPLIER_ID}/price-list/upload",
            params={"dry_run": "true"},
            headers={"X-CSRF-Token": csrf},
            files=files,
            timeout=120,
        )
    print("upload dry_run:", r.status_code)
    print(r.text[:500])
    r.raise_for_status()
    data = r.json()
    job_id = data.get("job_id")
    if not job_id:
        print("No job_id in response")
        sys.exit(1)

    # Optional preview
    r = s.get(f"{BASE}/imports/{job_id}/preview", timeout=30)
    print("preview:", r.status_code, "items:", len(r.json().get("items", [])))

    # Commit
    r = s.post(
        f"{BASE}/imports/{job_id}/commit",
        headers={"X-CSRF-Token": csrf},
        timeout=120,
    )
    print("commit:", r.status_code)
    print(r.text)
    r.raise_for_status()


if __name__ == "__main__":
    main()
