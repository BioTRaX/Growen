#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: auditor.py
# NG-HEADER: Ubicación: services/catalog_audit/rules.py
# NG-HEADER: Descripción: Reglas deterministas y clasificación del auditor autónomo de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Motor determinista, taxonomía y consistencia física del catálogo."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


FLAG_PHYSICAL_DISCREPANCY = "FLAG_PHYSICAL_DISCREPANCY"
FLAG_INVALID_DIMENSIONS = "FLAG_INVALID_DIMENSIONS"
FLAG_DIMENSIONS_MISMATCH = "FLAG_DIMENSIONS_MISMATCH"
FLAG_SUSPICIOUS_DIMENSIONS = "FLAG_SUSPICIOUS_DIMENSIONS"
FLAG_BOILERPLATE = "FLAG_BOILERPLATE"
FLAG_MALFORMED_HTML = "FLAG_MALFORMED_HTML"
FLAG_ENTITY_MISMATCH = "FLAG_ENTITY_MISMATCH"

CRITICAL_FLAGS = {
    FLAG_PHYSICAL_DISCREPANCY,
    FLAG_INVALID_DIMENSIONS,
    FLAG_DIMENSIONS_MISMATCH,
}

GROW_COMPETITOR_BRANDS = {
    "top crop",
    "biobizz",
    "namaste",
    "advanced nutrients",
    "plagron",
    "atami",
    "general hydroponics",
    "treemix",
    "kawsay",
    "feeding",
    "azteka",
    "vam",
    "mad line",
}

SUBSTRATE_KEYWORDS = {
    "sustrato",
    "tierra",
    "growmix",
    "klasmann",
    "humus",
    "perlita",
    "vermiculita",
    "turba",
    "coco",
    "substrato",
    "peat",
}

CONTAINER_KEYWORDS = {"maceta", "contenedor", "matera", "jardinera", "balde", "bandeja"}
LIQUID_KEYWORDS = {
    "fertilizante", "nutriente", "bioestimulante", "líquido", "liquido", "solución", "solucion",
}


class ProductClass(StrEnum):
    LIQUID = "liquid"
    SUBSTRATE = "substrate"
    CONTAINER = "container"
    TENT = "tent"
    WEIGHT_PRODUCT = "weight_product"
    OTHER = "other"

METADISCOURSE_PATTERNS = [
    re.compile(r"(?i)\bsegún la (?:investigación|fuente)\b"),
    re.compile(r"(?i)\blas fuentes describen\b"),
    re.compile(r"(?i)\bse reporta un diseño\b"),
    re.compile(r"(?i)\bcomo modelo de lenguaje\b"),
    re.compile(r"(?i)\bcomo (?:un )?asistente (?:virtual|ia|de inteligencia artificial)\b"),
    re.compile(r"(?i)\bno tengo acceso\b"),
    re.compile(r"(?i)\bno poseo información\b"),
    re.compile(r"(?i)\ben mi base de datos\b"),
]


@dataclass
class QualityAuditResult:
    score: int
    passed: bool
    flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    field_issues: dict[str, list[str]] = field(default_factory=dict)
    product_class: ProductClass = ProductClass.OTHER

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "flags": self.flags,
            "warnings": self.warnings,
            "field_issues": self.field_issues,
            "product_class": self.product_class.value,
        }


def classify_product(
    product_name: str,
    taxonomy: dict[str, Any] | None,
    content: dict[str, Any] | None,
) -> ProductClass:
    """Clasifica antes de ejecutar reglas físicas para evitar inferencias por unidad."""
    taxonomy = taxonomy or {}
    content = content or {}
    fragments = [product_name, taxonomy.get("category"), taxonomy.get("subcategory")]
    fragments.extend(str(value) for value in taxonomy.get("tags") or [])
    text = " ".join(str(value or "") for value in fragments).lower()
    explicit = taxonomy.get("audit_class")
    if explicit:
        try:
            return ProductClass(str(explicit))
        except ValueError:
            pass
    tokens = set(re.findall(r"\b\w+\b", text))
    if tokens & CONTAINER_KEYWORDS:
        return ProductClass.CONTAINER
    if re.search(r"\b(carpa|indoor|tent)\b", text):
        return ProductClass.TENT
    if tokens & SUBSTRATE_KEYWORDS:
        return ProductClass.SUBSTRATE
    if tokens & LIQUID_KEYWORDS:
        return ProductClass.LIQUID
    if extract_weight_kg_from_text(text) is not None and extract_volume_liters(text) is None:
        return ProductClass.WEIGHT_PRODUCT
    if content.get("volume_ml") is not None or content.get("volume_l") is not None:
        return ProductClass.LIQUID
    if extract_volume_liters(text) is not None:
        return ProductClass.LIQUID
    return ProductClass.OTHER


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(str(value).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None


def extract_volume_liters(text: str) -> float | None:
    """Extrae volumen en litros a partir de expresiones como 250ml, 1L, 80 Litros, 500 cc."""
    if not text:
        return None
    match = re.search(
        r"(?:^|[\s_/\-\(\[])(\d+(?:[.,]\d+)?)\s*(ml|cc|cm3|l|lt|lts|litro|litros|dm3)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    val_str, unit = match.groups()
    try:
        val = float(val_str.replace(",", "."))
    except ValueError:
        return None
    unit_lower = unit.lower()
    if unit_lower in {"ml", "cc", "cm3"}:
        return val / 1000.0
    return val


def extract_weight_kg_from_text(text: str) -> float | None:
    """Extrae peso en kg a partir de expresiones como 500g, 1.5kg, 2 kilos."""
    if not text:
        return None
    match = re.search(
        r"(?:^|[\s_/\-\(\[])(\d+(?:[.,]\d+)?)\s*(g|gr|grs|gramo|gramos|kg|kgs|kilo|kilos)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    val_str, unit = match.groups()
    try:
        val = float(val_str.replace(",", "."))
    except ValueError:
        return None
    unit_lower = unit.lower()
    if unit_lower in {"g", "gr", "grs", "gramo", "gramos"}:
        return val / 1000.0
    return val


def _is_substrate(text: str) -> bool:
    tokens = set(re.findall(r"\b\w+\b", text.lower()))
    return bool(tokens & SUBSTRATE_KEYWORDS)


def _check_dimensions_sanity(
    height: float | None,
    width: float | None,
    depth: float | None,
    combined_name: str,
    extracted_volume: float | None,
    result_issues: dict[str, list[str]],
    flags: set[str],
    warnings: list[str],
) -> int:
    penalty = 0
    dims = [("height_cm", height), ("width_cm", width), ("depth_cm", depth)]
    is_tent = bool(re.search(r"\b(carpa|indoor|tent|red)\b", combined_name, re.IGNORECASE))

    # Verificar valores no positivos
    for name, val in dims:
        if val is not None and val <= 0:
            flags.add(FLAG_INVALID_DIMENSIONS)
            result_issues.setdefault(name, []).append("La dimensión debe ser mayor a 0 cm.")
            warnings.append(f"{name} ({val}) no puede ser menor o igual a cero.")
            penalty += 40

    # Verificar dimensiones absurdas
    for name, val in dims:
        if val is not None and val > 0:
            if val > 350 and not is_tent:
                flags.add(FLAG_SUSPICIOUS_DIMENSIONS)
                result_issues.setdefault(name, []).append(f"Dimensión sospechosamente grande ({val} cm).")
                warnings.append(f"{name} ({val} cm) excede el tamaño esperable para artículos no carpas.")
                penalty += 15
            elif val < 0.5:
                flags.add(FLAG_SUSPICIOUS_DIMENSIONS)
                result_issues.setdefault(name, []).append(f"Dimensión sospechosamente pequeña ({val} cm).")
                warnings.append(f"{name} ({val} cm) es inverosímil para paquetería comercial.")
                penalty += 15

    # Consistencia de caja envolvente con volumen
    if height and width and depth and height > 0 and width > 0 and depth > 0:
        box_volume_liters = (height * width * depth) / 1000.0
        if extracted_volume and extracted_volume > 0:
            # Una botella o bolsa no puede ser físicamente menor al volumen que contiene
            if box_volume_liters < extracted_volume * 0.70:
                flags.add(FLAG_DIMENSIONS_MISMATCH)
                msg = (
                    f"Caja envolvente ({box_volume_liters:.2f} L) menor al volumen declarado "
                    f"del producto ({extracted_volume:.2f} L)."
                )
                warnings.append(msg)
                result_issues.setdefault("dimensions", []).append(msg)
                penalty += 35
            # Caja desproporcionadamente gigante para líquidos chicos
            elif extracted_volume >= 0.25 and box_volume_liters > extracted_volume * 20.0 and not is_tent:
                flags.add(FLAG_SUSPICIOUS_DIMENSIONS)
                msg = (
                    f"Dimensiones ({height}x{width}x{depth} cm) implican un volumen ({box_volume_liters:.1f} L) "
                    f"desproporcionado para un contenido de {extracted_volume:.2f} L."
                )
                warnings.append(msg)
                result_issues.setdefault("dimensions", []).append(msg)
                penalty += 15

    return penalty


def _check_weight_sanity(
    weight_kg: float | None,
    combined_name: str,
    extracted_volume: float | None,
    extracted_weight: float | None,
    result_issues: dict[str, list[str]],
    flags: set[str],
    warnings: list[str],
    product_class: ProductClass,
) -> int:
    if weight_kg is None:
        return 0

    penalty = 0
    if weight_kg <= 0:
        flags.add(FLAG_PHYSICAL_DISCREPANCY)
        result_issues.setdefault("weight_kg", []).append("El peso debe ser mayor a 0 kg.")
        warnings.append(f"Peso propuesto ({weight_kg} kg) inválido.")
        return 40

    # Comparación con peso explícito en el título (ej: 500g, 2kg)
    if extracted_weight and extracted_weight > 0:
        ratio = weight_kg / extracted_weight
        # Se permite packaging tara razonable (entre 0.7 y 2.0 veces)
        if ratio < 0.60 or ratio > 2.5:
            flags.add(FLAG_PHYSICAL_DISCREPANCY)
            msg = (
                f"Peso propuesto ({weight_kg:.3f} kg) discrepa del peso especificado en el "
                f"nombre ({extracted_weight:.3f} kg)."
            )
            warnings.append(msg)
            result_issues.setdefault("weight_kg", []).append(msg)
            penalty += 35

    # Comparación con volumen estimado en el título (ej: 80L sustrato, 250ml líquido)
    elif extracted_volume and extracted_volume > 0:
        if product_class in {ProductClass.CONTAINER, ProductClass.TENT, ProductClass.OTHER}:
            return penalty
        if product_class == ProductClass.SUBSTRATE:
            # Densidad aparente típica de sustrato: 0.18 - 0.50 kg/L
            min_expected = extracted_volume * 0.12
            max_expected = extracted_volume * 0.65
            if weight_kg < min_expected or weight_kg > max_expected:
                flags.add(FLAG_PHYSICAL_DISCREPANCY)
                msg = (
                    f"Peso propuesto ({weight_kg:.2f} kg) es inverosímil para un sustrato de "
                    f"{extracted_volume:.0f} L (esperado aprox. entre {min_expected:.1f} y {max_expected:.1f} kg)."
                )
                warnings.append(msg)
                result_issues.setdefault("weight_kg", []).append(msg)
                penalty += 35
        else:
            # Densidad de líquidos/fertilizantes: 0.85 - 1.45 kg/L (+ tara frasco)
            min_expected = extracted_volume * 0.40
            max_expected = (extracted_volume * 2.50) + 0.35
            if weight_kg < min_expected or weight_kg > max_expected:
                flags.add(FLAG_PHYSICAL_DISCREPANCY)
                msg = (
                    f"Peso propuesto ({weight_kg:.3f} kg) contradice el volumen declarado "
                    f"({extracted_volume:.2f} L) para producto líquido/fertilizante."
                )
                warnings.append(msg)
                result_issues.setdefault("weight_kg", []).append(msg)
                penalty += 35

    return penalty


def _check_text_and_brand_sanity(
    description_html: str | None,
    product_brand: str | None,
    combined_name: str,
    result_issues: dict[str, list[str]],
    flags: set[str],
    warnings: list[str],
) -> int:
    if not description_html:
        return 0

    penalty = 0

    # Metadiscurso de investigación o frases de IA
    for pattern in METADISCOURSE_PATTERNS:
        match = pattern.search(description_html)
        if match:
            flags.add(FLAG_BOILERPLATE)
            msg = f"Descripción contiene metadiscurso de investigación o relleno IA: '{match.group(0)}'."
            warnings.append(msg)
            result_issues.setdefault("description_html", []).append(msg)
            penalty += 25
            break

    # Detección de markdown crudo no parseado en HTML
    if re.search(r"(?:^|\n)#{1,4}\s", description_html):
        flags.add(FLAG_MALFORMED_HTML)
        msg = "Descripción HTML contiene encabezados Markdown crudos (ej: '###')."
        warnings.append(msg)
        result_issues.setdefault("description_html", []).append(msg)
        penalty += 20

    # HTML balance básico de párrafos
    open_p = len(re.findall(r"<p\b[^>]*>", description_html, re.IGNORECASE))
    close_p = len(re.findall(r"</p>", description_html, re.IGNORECASE))
    if open_p != close_p:
        flags.add(FLAG_MALFORMED_HTML)
        msg = f"Etiquetas <p> no balanceadas en descripción ({open_p} abiertas, {close_p} cerradas)."
        warnings.append(msg)
        result_issues.setdefault("description_html", []).append(msg)
        penalty += 15

    # Verificación de confusión de marca
    normalized_brand = (product_brand or "").strip().lower()
    desc_lower = description_html.lower()

    if normalized_brand:
        for competitor in GROW_COMPETITOR_BRANDS:
            if competitor != normalized_brand and competitor in desc_lower:
                # Si menciona una marca competidora pero NO menciona la marca propia del producto
                if normalized_brand not in desc_lower and normalized_brand not in combined_name.lower():
                    flags.add(FLAG_ENTITY_MISMATCH)
                    msg = (
                        f"La descripción menciona una marca competidora ('{competitor}') sin referenciar "
                        f"la marca original del producto ('{product_brand}')."
                    )
                    warnings.append(msg)
                    result_issues.setdefault("description_html", []).append(msg)
                    penalty += 25
                    break

    return penalty


def audit_enrichment_proposal(
    product_name: str,
    brand: str | None,
    proposal: dict[str, Any],
    original_name: str | None = None,
) -> QualityAuditResult:
    """Compatibilidad histórica: audita contenido sin depender del flujo Enrich."""
    flags: set[str] = set()
    warnings: list[str] = []
    field_issues: dict[str, list[str]] = {}

    combined_name = f"{product_name or ''} {original_name or ''}".strip()
    product_class = classify_product(combined_name, None, proposal)
    extracted_volume = extract_volume_liters(combined_name)
    extracted_weight = extract_weight_kg_from_text(combined_name)

    total_penalty = 0

    # 1. Sanidad de dimensiones
    height = _to_float(proposal.get("height_cm"))
    width = _to_float(proposal.get("width_cm"))
    depth = _to_float(proposal.get("depth_cm"))
    total_penalty += _check_dimensions_sanity(
        height, width, depth, combined_name, extracted_volume, field_issues, flags, warnings
    )

    # 2. Sanidad de peso y consistencia física
    weight_kg = _to_float(proposal.get("weight_kg"))
    total_penalty += _check_weight_sanity(
        weight_kg, combined_name, extracted_volume, extracted_weight, field_issues, flags, warnings,
        product_class,
    )

    # 3. Sanidad de texto, formato y marca
    description_html = proposal.get("description_html")
    if isinstance(description_html, str):
        total_penalty += _check_text_and_brand_sanity(
            description_html, brand, combined_name, field_issues, flags, warnings
        )

    score = max(0, min(100, 100 - total_penalty))
    has_critical_flag = bool(flags & CRITICAL_FLAGS)
    passed = (score >= 75) and not has_critical_flag

    return QualityAuditResult(
        score=score,
        passed=passed,
        flags=sorted(flags),
        warnings=warnings,
        field_issues=field_issues,
        product_class=product_class,
    )


def audit_catalog_content(
    *, product_name: str, brand: str | None, taxonomy: dict[str, Any] | None, content: dict[str, Any]
) -> QualityAuditResult:
    """Audita contenido efectivo aplicando primero la clasificación del producto."""
    result = audit_enrichment_proposal(product_name=product_name, brand=brand, proposal=content)
    result.product_class = classify_product(product_name, taxonomy, content)
    return result
