# NG-HEADER: Nombre de archivo: test_pop_email_overflow.py
# NG-HEADER: Ubicación: tests/test_pop_email_overflow.py
# NG-HEADER: Descripción: Tests del parser POP para evitar overflow y filtrar ruido (WhatsApp/disclaimers)
# NG-HEADER: Lineamientos: Ver AGENTS.md

from services.importers.pop_email import parse_pop_email


def test_parser_filters_whatsapp_disclaimer_rows():
    html = """
    <html><body>
      <table>
        <tr><th>Producto</th><th>Cantidad</th><th>Precio</th></tr>
        <tr><td>Maceta 12cm Negra</td><td>2</td><td>$1.500,00</td></tr>
        <tr><td>WhatsApp de Atención al cliente: +54 9 11 3952-8296 Esta es una órden de pedido, los precios pueden sufrir modificaciones. Distribuidora Pop © 2023. Todos Derechos Reservados</td><td>5491139528296.202</td><td>$0</td></tr>
      </table>
    </body></html>
    """
    parsed = parse_pop_email(html, kind="html")
    titles = [ln.title.lower() for ln in parsed.lines]
    assert any("maceta 12cm negra" in t for t in titles)
    # No debe incluir la fila de WhatsApp/disclaimer
    assert not any("whatsapp" in t for t in titles)
    # Y la cantidad de la fila válida debe ser 2
    mac_line = next(ln for ln in parsed.lines if "maceta 12cm negra" in ln.title.lower())
    assert str(mac_line.qty) == "2"


def test_parser_qty_clamp_when_unreasonable():
    html = """
    <html><body>
      <table>
        <tr><th>Producto</th><th>Cantidad</th><th>Precio</th></tr>
        <tr><td>Producto X</td><td>1000000</td><td>$10.000,00</td></tr>
      </table>
    </body></html>
    """
    parsed = parse_pop_email(html, kind="html")
    assert len(parsed.lines) == 1
    # Debe clamp a 1 por ser > 100000
    assert str(parsed.lines[0].qty) == "1"
