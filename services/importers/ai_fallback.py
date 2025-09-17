#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: ai_fallback.py
# NG-HEADER: Ubicación: services/importers/ai_fallback.py
# NG-HEADER: Descripción: Cliente y lógica de fallback IA para parsing de remitos
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Módulo de integración mínima con modelo de lenguaje para extraer líneas de remitos.

Objetivos:
- Sólo se invoca como fallback cuando la etapa clásica produce 0 líneas o baja confianza.
- Respuesta estrictamente JSON validada contra modelos Pydantic.
- No lanza excepciones hacia arriba: retorna estructura controlada para logging.

NOTA: Implementación inicial; el cálculo de confianza clásica todavía no existe, se
disparará únicamente por "no_lines" hasta que se añada métrica de confianza.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import json
import time
from decimal import Decimal

from agent_core.config import settings
from .ai_models import RemitoAIPayload, RemitoAIItem

try:  # httpx ya está en requirements
    import httpx
except Exception:  # pragma: no cover - entorno degradado
    httpx = None  # type: ignore


class AIFallbackResult:
    def __init__(self, ok: bool, payload: RemitoAIPayload | None, raw: str | None, error: str | None, events: list[dict]):
        self.ok = ok
        self.payload = payload
        self.raw = raw
        self.error = error
        self.events = events


SYSTEM_PROMPT = (
    "Eres un asistente que extrae ítems de un remito de proveedor argentino. "
    "Debes devolver JSON válido y nada más. Campos: lines[], cada línea: supplier_sku (opcional), title, qty (float), unit_cost_bonif (float), pct_bonif (float), confidence (0-1). "
    "Opcional remito_number (formato serie-numero) y remito_date (YYYY-MM-DD). Sin comentarios ni texto adicional."
)


def _build_prompt(text_excerpt: str, classic_lines_hint: int | None = None, classic_confidence: float | None = None) -> List[Dict[str, str]]:
    # Mensajes estilo OpenAI Chat Completions
    hint = ""
    if classic_lines_hint is not None:
        hint += f"Líneas clásicas detectadas: {classic_lines_hint}. "
    if classic_confidence is not None:
        hint += f"Confianza clásica: {classic_confidence:.2f}. "
    user_content = (
        hint + "Extrae los ítems del remito. Si hay dudas deja la línea fuera (no inventar). "
        "Devuelve sólo JSON. Texto fuente (recortado):\n" + text_excerpt[:7000]
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def run_ai_fallback(*, correlation_id: str, text_excerpt: str, classic_lines_hint: int | None = None, classic_confidence: float | None = None) -> AIFallbackResult:
    events: List[Dict[str, Any]] = []
    if not settings.import_ai_enabled or not settings.openai_api_key:
        events.append({"level": "INFO", "stage": "ai", "event": "skip_disabled", "details": {"enabled": settings.import_ai_enabled}})
        return AIFallbackResult(False, None, None, "disabled", events)
    if httpx is None:  # pragma: no cover
        events.append({"level": "ERROR", "stage": "ai", "event": "httpx_missing", "details": {}})
        return AIFallbackResult(False, None, None, "httpx_missing", events)

    model = settings.import_ai_model
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": _build_prompt(text_excerpt, classic_lines_hint=classic_lines_hint, classic_confidence=classic_confidence),
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }
    attempts = 0
    raw_text: str | None = None
    last_err: str | None = None
    while attempts <= settings.import_ai_max_retries:
        attempts += 1
        start = time.time()
        try:
            timeout = settings.import_ai_timeout
            events.append({"level": "INFO", "stage": "ai", "event": "request", "details": {"attempt": attempts, "model": model}})
            with httpx.Client(timeout=timeout) as client:  # type: ignore
                r = client.post(url, headers=headers, json=payload)
            dur = time.time() - start
            if r.status_code >= 500:
                last_err = f"server_error_{r.status_code}"
                events.append({"level": "WARN", "stage": "ai", "event": "server_error", "details": {"status": r.status_code, "duration_s": round(dur, 2)}})
                continue
            if r.status_code != 200:
                last_err = f"http_{r.status_code}"
                events.append({"level": "WARN", "stage": "ai", "event": "bad_status", "details": {"status": r.status_code, "body": r.text[:400]}})
                break
            data = r.json()
            raw_text = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content")
            if not raw_text:
                last_err = "empty_content"
                events.append({"level": "WARN", "stage": "ai", "event": "empty_content", "details": {}})
                continue
            try:
                parsed = json.loads(raw_text)
            except Exception as e:  # JSON inválido
                last_err = f"json_error:{e.__class__.__name__}"
                events.append({"level": "WARN", "stage": "ai", "event": "json_decode_fail", "details": {"err": str(e), "excerpt": raw_text[:200]}})
                continue
            try:
                payload_obj = RemitoAIPayload(**parsed)
                payload_obj.compute_overall()
            except Exception as e:  # Validación Pydantic
                last_err = f"validation_error:{e.__class__.__name__}"
                events.append({"level": "WARN", "stage": "ai", "event": "validation_fail", "details": {"err": str(e)[:300]}})
                continue
            events.append({"level": "INFO", "stage": "ai", "event": "ok", "details": {"lines": len(payload_obj.lines), "overall": payload_obj.overall_confidence}})
            return AIFallbackResult(True, payload_obj, raw_text, None, events)
        except Exception as e:  # pragma: no cover (difícil de forzar)
            last_err = f"exception:{e.__class__.__name__}"
            events.append({"level": "ERROR", "stage": "ai", "event": "exception", "details": {"err": str(e)[:300]}})
    return AIFallbackResult(False, None, raw_text, last_err, events)


def merge_ai_lines(classic_lines: list, ai_payload: RemitoAIPayload, min_conf: float) -> tuple[list, dict]:
    """Fusiona líneas clásicas con IA sin duplicar SKU exacto; prioriza clásicas.

    Retorna: (merged_lines, stats)
    """
    if not ai_payload.lines:
        return classic_lines, {"added": 0, "ignored_low_conf": 0}
    existing_skus = {l.supplier_sku for l in classic_lines if getattr(l, 'supplier_sku', None)}
    added = 0
    ignored_low = 0
    for it in ai_payload.lines:
        if it.confidence < min_conf:
            ignored_low += 1
            continue
        if it.supplier_sku and it.supplier_sku in existing_skus:
            continue
        # Adaptar a ParsedLine (solo subset usado aguas abajo)
        from .santaplanta_pipeline import ParsedLine  # import local para evitar ciclo en import
        pl = ParsedLine(
            supplier_sku=it.supplier_sku,
            title=it.title,
            qty=Decimal(str(it.qty)),
            unit_cost_bonif=Decimal(str(it.unit_cost_bonif)),
            pct_bonif=Decimal(str(it.pct_bonif)),
        )
        classic_lines.append(pl)
        if it.supplier_sku:
            existing_skus.add(it.supplier_sku)
        added += 1
    return classic_lines, {"added": added, "ignored_low_conf": ignored_low}


__all__ = [
    "run_ai_fallback",
    "merge_ai_lines",
    "AIFallbackResult",
]
