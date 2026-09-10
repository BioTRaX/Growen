#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_auth_session_cookie.py
# NG-HEADER: Ubicación: tests/test_auth_session_cookie.py
# NG-HEADER: Descripción: Regresión del SID crudo usado por las cookies de sesión.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest
from datetime import date
from fastapi.testclient import TestClient

from db.models import Purchase, PurchaseAttachment, Sale, SaleAttachment, Supplier, User
from services.api import app
from services.auth import hash_pw


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_login_cookie_resuelve_la_sesion_real_y_descarga_privada(
    db_session, tmp_path, monkeypatch
):
    user = User(
        identifier="admin-cookie-test",
        password_hash=hash_pw("segura-test-123"),
        role="admin",
    )
    db_session.add(user)
    supplier = Supplier(slug="proveedor-seguridad", name="Proveedor Seguridad")
    db_session.add(supplier)
    await db_session.commit()
    await db_session.refresh(supplier)

    purchase = Purchase(
        supplier_id=supplier.id,
        remito_number="SEG-001",
        remito_date=date(2026, 9, 9),
    )
    db_session.add(purchase)
    await db_session.commit()
    await db_session.refresh(purchase)

    private_file = tmp_path / "remito-privado.pdf"
    private_file.write_bytes(b"contenido-privado")
    attachment = PurchaseAttachment(
        purchase_id=purchase.id,
        filename=private_file.name,
        mime="application/pdf",
        size=private_file.stat().st_size,
        path=str(private_file),
    )
    db_session.add(attachment)
    sale = Sale()
    db_session.add(sale)
    await db_session.commit()
    await db_session.refresh(attachment)
    await db_session.refresh(sale)

    sale_file = tmp_path / "comprobante-venta.pdf"
    sale_file.write_bytes(b"venta-privada")
    monkeypatch.setenv("PRIVATE_MEDIA_ROOT", str(tmp_path))
    sale_attachment = SaleAttachment(
        sale_id=sale.id,
        filename=sale_file.name,
        mime="application/pdf",
        size=sale_file.stat().st_size,
        path=sale_file.name,
    )
    db_session.add(sale_attachment)
    await db_session.commit()
    await db_session.refresh(sale_attachment)

    monkeypatch.chdir(tmp_path)
    log_dir = tmp_path / "purchases" / str(purchase.id) / "logs"
    log_dir.mkdir(parents=True)
    log_file = log_dir / "iaval_changes_seguridad.json"
    log_file.write_bytes(b'{"resultado":"privado"}')

    with TestClient(app) as client:
        anonymous = client.get(
            f"/purchases/{purchase.id}/attachments/{attachment.id}/file"
        )
        assert anonymous.status_code in {401, 403, 404}
        anonymous_log = client.get(
            f"/purchases/{purchase.id}/logs/files/{log_file.name}"
        )
        assert anonymous_log.status_code in {401, 403, 404}
        anonymous_sale = client.get(
            f"/sales/{sale.id}/attachments/{sale_attachment.id}/file"
        )
        assert anonymous_sale.status_code in {401, 403, 404}

        login = client.post(
            "/auth/login",
            json={"identifier": user.identifier, "password": "segura-test-123"},
        )
        assert login.status_code == 200

        current = client.get("/auth/me")
        assert current.status_code == 200
        assert current.json()["is_authenticated"] is True
        assert current.json()["role"] == "admin"

        csrf = client.cookies.get("csrf_token")
        rejected = client.post(
            "/suppliers",
            headers={"X-CSRF-Token": "incorrecto"},
            json={"slug": "sesion-rechazada", "name": "Sesión Rechazada"},
        )
        assert rejected.status_code == 403

        created = client.post(
            "/suppliers",
            headers={"X-CSRF-Token": csrf},
            json={"slug": "sesion-real", "name": "Sesión Real"},
        )
        assert created.status_code == 200

        wrong_purchase = client.get(
            f"/purchases/{purchase.id + 1}/attachments/{attachment.id}/file"
        )
        assert wrong_purchase.status_code == 404

        downloaded = client.get(
            f"/purchases/{purchase.id}/attachments/{attachment.id}/file"
        )
        assert downloaded.status_code == 200
        assert downloaded.content == b"contenido-privado"

        downloaded_log = client.get(
            f"/purchases/{purchase.id}/logs/files/{log_file.name}"
        )
        assert downloaded_log.status_code == 200
        assert downloaded_log.content == b'{"resultado":"privado"}'

        downloaded_sale = client.get(
            f"/sales/{sale.id}/attachments/{sale_attachment.id}/file"
        )
        assert downloaded_sale.status_code == 200
        assert downloaded_sale.content == b"venta-privada"

        reset = client.post(
            f"/auth/users/{user.id}/reset-password",
            headers={"X-CSRF-Token": csrf},
        )
        assert reset.status_code == 200
        after_reset = client.get("/auth/me")
        assert after_reset.status_code == 200
        assert after_reset.json()["is_authenticated"] is False

        relogin = client.post(
            "/auth/login",
            json={"identifier": user.identifier, "password": reset.json()["password"]},
        )
        assert relogin.status_code == 200
        new_csrf = client.cookies.get("csrf_token")
        disabled = client.patch(
            f"/auth/users/{user.id}",
            headers={"X-CSRF-Token": new_csrf},
            json={"is_active": False},
        )
        assert disabled.status_code == 200
        assert client.get("/auth/me").json()["is_authenticated"] is False
