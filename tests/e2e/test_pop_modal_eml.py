# NG-HEADER: Nombre de archivo: test_pop_modal_eml.py
# NG-HEADER: Ubicación: tests/e2e/test_pop_modal_eml.py
# NG-HEADER: Descripción: E2E UI Playwright para importar POP desde archivo .eml usando el modal en Compras
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import time 
from pathlib import Path
from playwright.sync_api import expect

DEV_EML = os.environ.get("E2E_POP_EML", str(Path(__file__).resolve().parents[2] / "Devs" / "Pedido 488344 Completado.eml"))


def _wait_server(page, base_url: str, tries: int = 10):
    for _ in range(tries):
        try:
            page.goto(f"{base_url}/login", wait_until="load")
            return
        except Exception:
            time.sleep(0.5)
    raise AssertionError("Servidor no responde en base_url")


def _login_admin(page, base_url: str):
    ident = os.environ.get("E2E_USER", "admin")
    pwd = os.environ.get("E2E_PASS", "admin1234")
    _wait_server(page, base_url)
    # Login por la UI para asegurar cookies y estado SPA
    page.goto(f"{base_url}/login", wait_until="load")
    page.get_by_placeholder("Usuario o email").fill(ident)
    page.get_by_placeholder("Contraseña").fill(pwd)
    page.get_by_role("button", name="Ingresar", exact=True).click()
    # Esperar navegación inicial y confirmar autenticación/rol vía /auth/me
    page.wait_for_url("**/", timeout=15000)
    page.wait_for_timeout(200)
    def _check_auth():
        return page.evaluate("async (u)=>{ const r = await fetch(u+'/auth/me', {credentials:'include'}); if(!r.ok) return null; return await r.json() }", base_url)
    for _ in range(20):
        me = _check_auth()
        if me and me.get('is_authenticated') and me.get('role') in ("admin", "colaborador"):
            break
        page.wait_for_timeout(250)
    else:
        raise AssertionError("Login no estableció sesión admin/colaborador en /auth/me")
    # Persistir marcador de autenticación para rehidratación del FE tras recargas SPA
    page.evaluate("() => { try { localStorage.setItem('auth', JSON.stringify({ role: 'admin', exp: Math.floor(Date.now()/1000) + 6*60*60 })); } catch(e){} }")


def _ensure_supplier_pop(page, base_url: str):
    # Crear proveedor POP con CSRF (idempotente)
    page.goto(f"{base_url}/", wait_until="load")
    page.wait_for_timeout(400)
    page.evaluate(
        "async (u)=>{ try { const r = await fetch(u+'/suppliers', {credentials:'include'}); if(!r.ok) return; const lst = await r.json(); if(Array.isArray(lst) && lst.find(s=> (s.slug||'').toLowerCase()==='pop')) return; const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/); const csrf = m? decodeURIComponent(m[1]): null; await fetch(u+'/suppliers', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json', ...(csrf? {'X-CSRF-Token': csrf}: {})}, body: JSON.stringify({slug:'pop', name:'POP'})}); } catch(e){} }",
        base_url
    )


def test_pop_email_import_eml(page, base_url):
    assert Path(DEV_EML).exists(), f"No se encuentra el .eml de prueba en {DEV_EML}"

    # Login admin y asegurar proveedor POP
    _login_admin(page, base_url)
    _ensure_supplier_pop(page, base_url)

    # Ir directo a Compras (ruta SPA)
    page.goto(f"{base_url}/compras")
    # Esperar a que la página de Compras esté lista y el botón sea visible
    expect(page.get_by_text("Compras")).to_be_visible(timeout=15000)
    expect(page.get_by_role("button", name="Cargar compra")).to_be_visible(timeout=15000)
    # Abrir "Cargar compra" y elegir "POP (Email)"
    page.get_by_role("button", name="Cargar compra").click()
    page.get_by_role("button", name="POP (Email)").click()

    # En el modal: seleccionar proveedor POP en autocompletado
    # Buscamos el input por placeholder "Proveedor"
    page.get_by_placeholder("Proveedor").fill("POP")
    page.wait_for_timeout(200)
    page.get_by_text("POP").first.click()

    # Seleccionar modo EML y cargar archivo
    page.get_by_text("Subir .eml").click()
    # Input file
    file_input = page.locator("input[type='file']").first
    file_input.set_input_files(DEV_EML)

    # Ejecutar importación
    page.get_by_role("button", name="Procesar").click()

    # Esperar redirección a detalle de compra (url contiene /purchases/ID)
    page.wait_for_url("**/purchases/*", timeout=10000)
    expect(page).to_have_url(lambda url: "/purchases/" in url)

    # Verificar que se renderiza estado BORRADOR y SKUs POP-
    expect(page.get_by_text("BORRADOR")).to_be_visible()
    # Algunos listados de líneas podrían requerir scroll o esperan render: breve espera
    page.wait_for_timeout(500)
    # Heurística: buscar al menos un SKU que empiece con POP-
    has_pop = page.locator("text=/POP-\\d{8}-\\d{3}/").count()
    assert has_pop >= 1, "No se encontraron SKUs sintéticos POP- en la UI"
