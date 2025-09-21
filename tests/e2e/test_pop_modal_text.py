# NG-HEADER: Nombre de archivo: test_pop_modal_text.py
# NG-HEADER: Ubicación: tests/e2e/test_pop_modal_text.py
# NG-HEADER: Descripción: E2E UI Playwright para importar POP pegando HTML/TEXTO en el modal
# NG-HEADER: Lineamientos: Ver AGENTS.md
from playwright.sync_api import expect
import os

SAMPLE_HTML = """
<html><body>
  <h1>Pedido 777777 Completado</h1>
  <table>
    <tr><th>Producto</th><th>Cantidad</th><th>Precio</th></tr>
    <tr><td>Maceta 12cm Negra</td><td>2</td><td>$1.500,00</td></tr>
    <tr><td>Sustrato 5L</td><td>1</td><td>$2.000,00</td></tr>
  </table>
</body></html>
"""


def _wait_server(page, base_url: str, tries: int = 10):
  for _ in range(tries):
    try:
      page.goto(f"{base_url}/login", wait_until="load")
      return
    except Exception:
      import time as _t; _t.sleep(0.5)
  raise AssertionError("Servidor no responde en base_url")


def _login_admin(page, base_url: str):
  ident = os.environ.get("E2E_USER", "admin")
  pwd = os.environ.get("E2E_PASS", "admin1234")
  _wait_server(page, base_url)
  page.goto(f"{base_url}/login", wait_until="load")
  page.get_by_placeholder("Usuario o email").fill(ident)
  page.get_by_placeholder("Contraseña").fill(pwd)
  page.get_by_role("button", name="Ingresar", exact=True).click()
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
  page.evaluate("() => { try { localStorage.setItem('auth', JSON.stringify({ role: 'admin', exp: Math.floor(Date.now()/1000) + 6*60*60 })); } catch(e){} }")


def test_pop_email_import_text(page, base_url):
  _login_admin(page, base_url)
  # Ir a Compras (ruta SPA)
  page.goto(f"{base_url}/compras")
  expect(page.get_by_text("Compras")).to_be_visible(timeout=15000)
  # Esperar a que la página de Compras esté lista y el botón sea visible
  expect(page.get_by_role("button", name="Cargar compra")).to_be_visible(timeout=15000)
  # Abrir "Cargar compra" y elegir "POP (Email)"
  page.get_by_role("button", name="Cargar compra").click()
  page.get_by_role("button", name="POP (Email)").click()

  # Seleccionar proveedor POP
  page.get_by_placeholder("Proveedor").fill("POP")
  page.wait_for_timeout(200)
  page.get_by_text("POP").first.click()

  # Cambiar a modo HTML/TEXTO
  page.get_byText = getattr(page, 'get_by_text') if hasattr(page, 'get_by_text') else page.get_by_text
  page.get_by_text("Pegar HTML").click()
  # Pegar HTML
  page.get_by_placeholder("<html>...pegá acá el cuerpo del email...</html>").fill(SAMPLE_HTML)

  # Procesar
  page.get_by_role("button", name="Procesar").click()

  # Esperar redirección al detalle
  page.wait_for_url("**/purchases/*", timeout=10000)
  expect(page).to_have_url(lambda url: "/purchases/" in url)
  expect(page.get_by_text("BORRADOR")).to_be_visible()
  page.wait_for_timeout(400)
  has_pop = page.locator("text=/POP-\\d{8}-\\d{3}/").count()
  assert has_pop >= 1, "No se encontraron SKUs sintéticos POP- en la UI"
