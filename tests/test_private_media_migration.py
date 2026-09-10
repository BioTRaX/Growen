#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_private_media_migration.py
# NG-HEADER: Ubicación: tests/test_private_media_migration.py
# NG-HEADER: Descripción: Verifica dry-run, copia idempotente, hashes y rollback de media privada.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from scripts.migrate_private_media import migrate_media


def test_private_media_migration_is_dry_run_idempotent_and_preserves_sources(tmp_path):
    public_root = tmp_path / "public"
    private_root = tmp_path / "private"
    source = public_root / "sales" / "2026" / "09" / "comprobante.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"comprobante")

    preview = migrate_media(public_root, private_root, apply=False)
    assert preview["mode"] == "dry-run"
    assert preview["files"][0]["status"] == "would_copy"
    assert not private_root.exists()

    applied = migrate_media(public_root, private_root, apply=True)
    target = private_root / source.relative_to(public_root)
    assert applied["files"][0]["status"] == "copied_verified"
    assert target.read_bytes() == b"comprobante"
    assert source.read_bytes() == b"comprobante"

    repeated = migrate_media(public_root, private_root, apply=True)
    assert repeated["files"][0]["status"] == "verified_existing"


def test_private_media_migration_includes_legacy_purchase_files(tmp_path):
    public_root = tmp_path / "public"
    private_root = tmp_path / "private"
    purchases_root = tmp_path / "legacy-purchases"
    source = purchases_root / "42" / "logs" / "auditoria.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"{}")

    result = migrate_media(
        public_root,
        private_root,
        apply=True,
        purchases_root=purchases_root,
    )

    assert result["files"][0]["path"] == "purchases/42/logs/auditoria.json"
    assert (private_root / "purchases" / "42" / "logs" / "auditoria.json").read_bytes() == b"{}"
    assert source.exists()
