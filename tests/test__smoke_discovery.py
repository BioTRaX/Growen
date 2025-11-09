"""
Smoke test para validar que pytest descubre y ejecuta al menos un test.

Si esto no corre, hay un problema de discovery/configuración de pytest en el entorno.
"""

def test_discovery_sanity():
    assert True
