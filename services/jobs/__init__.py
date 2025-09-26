# NG-HEADER: Nombre de archivo: __init__.py
# NG-HEADER: Ubicación: services/jobs/__init__.py
# NG-HEADER: Descripción: Inicializa jobs asíncronos del backend.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os

try:  # Hacer opcional dramatiq para que la API levante sin la lib en dev ligero
	import dramatiq  # type: ignore
	from dramatiq.brokers.redis import RedisBroker  # type: ignore
	from dramatiq.brokers.stub import StubBroker  # type: ignore
	_dramatiq_available = True
except Exception:  # pragma: no cover - entorno sin dramatiq
	dramatiq = None  # type: ignore
	_dramatiq_available = False


if _dramatiq_available:
	_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
	try:
		if os.getenv("RUN_INLINE_JOBS", "0") == "1":
			# Development mode: avoid touching Redis entirely
			dramatiq.set_broker(StubBroker())  # type: ignore
		else:
			broker = RedisBroker(url=_redis_url)  # type: ignore
			dramatiq.set_broker(broker)  # type: ignore
	except Exception as e:  # pragma: no cover
		# Fallback a stub si falla Redis u otra condición
		try:
			dramatiq.set_broker(StubBroker())  # type: ignore
		except Exception:
			pass
else:
	# No dramatiq: los decoradores en modules que lo usan fallarán si se evalúan.
	# Modo mínimo: definir un decorador no-op para evitar ImportError en import time.
	def _noop_decorator(*dargs, **dkwargs):  # type: ignore
		def _wrap(func):
			return func
		return _wrap
	class _StubModule:  # type: ignore
		actor = staticmethod(_noop_decorator)
	dramatiq = _StubModule()  # type: ignore

