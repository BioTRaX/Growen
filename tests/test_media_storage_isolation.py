#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_media_storage_isolation.py
# NG-HEADER: Ubicación: tests/test_media_storage_isolation.py
# NG-HEADER: Descripción: Regresiones de separación entre almacenamiento público y privado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import UploadFile

from services.media import (
    get_private_media_root,
    get_public_media_root,
    save_private_upload,
)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_private_upload_never_uses_the_public_root(monkeypatch, tmp_path):
    public_root = tmp_path / "public"
    private_root = tmp_path / "private"
    monkeypatch.setenv("PUBLIC_MEDIA_ROOT", str(public_root))
    monkeypatch.setenv("PRIVATE_MEDIA_ROOT", str(private_root))

    uploaded = UploadFile(filename="remito.pdf", file=BytesIO(b"%PDF-privado"))
    path, digest = await save_private_upload("sales", uploaded.filename, uploaded)

    assert get_public_media_root() == public_root
    assert get_private_media_root() == private_root
    assert path.is_relative_to(private_root)
    assert not path.is_relative_to(public_root)
    assert digest == "c5601e569da5bc655b877cea73890aaaf06d5d5efaa63924e15254dce131c678"
