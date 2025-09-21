# NG-HEADER: Nombre de archivo: test_chat_price_card.py
# NG-HEADER: Ubicación: tests/e2e/test_chat_price_card.py
# NG-HEADER: Descripción: Prueba E2E Playwright para la tarjeta de precios
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import time
import psycopg
from sqlalchemy.engine import make_url
import requests
from playwright.sync_api import expect
from datetime import datetime

from tests.e2e.test_pop_modal_text import _login_admin


def _seed_product(base_url: str, price: float) -> dict:
    sku_stub = f"E2E-{int(time.time() * 1000)}"
    supplier_slug = f"supplier-{sku_stub.lower()}"
    supplier_name = f"Proveedor {sku_stub}"
    product_title = f"Producto {sku_stub}"

    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise AssertionError("DB_URL no definido")
    url = make_url(db_url)
    conn = psycopg.connect(
        dbname=url.database,
        user=url.username,
        password=url.password,
        host=url.host or "127.0.0.1",
        port=url.port or 5432,
    )
    now = datetime.utcnow()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO suppliers (slug, name, created_at) VALUES (%s, %s, %s) RETURNING id",
                (supplier_slug, supplier_name, now),
            )
            supplier_id = cur.fetchone()[0]

            cur.execute(
                "INSERT INTO products (sku_root, title, stock, created_at, updated_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (sku_stub, product_title, 0, now, now),
            )
            product_id = cur.fetchone()[0]

            cur.execute(
                "INSERT INTO variants (product_id, sku, created_at, updated_at) VALUES (%s, %s, %s, %s) RETURNING id",
                (product_id, sku_stub, now, now),
            )
            variant_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO supplier_products (
                    supplier_id,
                    supplier_product_id,
                    title,
                    current_purchase_price,
                    current_sale_price,
                    internal_product_id,
                    internal_variant_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    supplier_id,
                    sku_stub,
                    product_title,
                    price,
                    price,
                    product_id,
                    variant_id,
                ),
            )
            cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    # Asegurar que el backend tenga proveedor/producto en cache (opcional via /auth/me)
    session = requests.Session()
    try:
        ident = os.environ.get("E2E_USER", "admin")
        pwd = os.environ.get("E2E_PASS", "admin1234")
        session.post(f"{base_url}/auth/login", json={"identifier": ident, "password": pwd}, timeout=10)
    finally:
        session.close()

    return {
        "title": product_title,
        "price": price,
        "sku": sku_stub,
        "supplier": supplier_name,
    }


def test_chat_price_card(page, base_url):
    page.route("**/ws", lambda route: route.abort())
    page.route("**/auth/login", lambda route: route.fulfill(status=200, body="{\"status\":\"mock\"}"))
    _login_admin(page, base_url)
    page.goto(f"{base_url}/")
    page.wait_for_timeout(300)

    data = _seed_product(base_url, 321.5)

    input_box = page.get_by_placeholder("Escribe un mensaje o /help")
    expect(input_box).to_be_visible()
    input_box.fill(f"Cuál es el precio de {data['title']}?")
    page.get_by_role("button", name="Enviar").click()

    page.wait_for_timeout(2000)
    debug_messages = page.evaluate("Array.from(document.querySelectorAll('div strong')).map(n => n.parentElement.textContent)")
    print('CONVERSATION:', debug_messages)

    growen_block = page.locator('div:has(strong:text-is("Growen"))').filter(has_text=f"El precio de {data['title']}")
    expect(growen_block).to_be_visible(timeout=15000)
    list_item = growen_block.locator('li').filter(has_text=data['supplier'])
    expect(list_item).to_contain_text('ARS')
    expect(list_item).to_contain_text(data['supplier'])
    expect(list_item).to_contain_text(data['sku'])
