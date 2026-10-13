"""
LlamaParse v2 (LlamaCloud): parsing con IA en la nube, en 4 tiers de precio.

Lo usan DOS consumidores, por eso vive aparte:
  - el catálogo de loaders (catalogo.py), una entrada por tier;
  - el OCR del pipeline (pipeline/etapas/e03_ocr.py), cuando se elige LlamaParse
    como motor para las páginas escaneadas.

Requiere LLAMA_CLOUD_API_KEY (ver config.py) y el SDK llama-cloud>=1.0.
"""

from __future__ import annotations

from typing import Any, Callable

import config

# Tabla oficial de precios: 1,000 créditos = 1.25 USD.
# https://developers.llamaindex.ai/llamaparse/general/pricing/
LLAMAPARSE_USD_PER_CREDIT = 1.25 / 1000

# tier (valor exacto de la API v2) -> créditos por página y formato de salida.
# `fast` no soporta Markdown (solo texto), el resto devuelve Markdown.
LLAMAPARSE_TIERS: dict[str, dict[str, Any]] = {
    "fast": {"label": "Fast", "credits_per_page": 1, "expand": "text"},
    "cost_effective": {"label": "Cost-effective", "credits_per_page": 3, "expand": "markdown"},
    "agentic": {"label": "Agentic", "credits_per_page": 10, "expand": "markdown"},
    "agentic_plus": {"label": "Agentic Plus", "credits_per_page": 45, "expand": "markdown"},
}

# Idiomas para el OCR de LlamaParse (el orden importa: el principal primero).
LLAMAPARSE_OCR_LANGUAGES = ["es", "en"]


def llamaparse_cost_per_1k_pages(tier: str) -> float:
    """Costo en USD por cada 1,000 páginas de un tier de LlamaParse."""
    return round(LLAMAPARSE_TIERS[tier]["credits_per_page"] * LLAMAPARSE_USD_PER_CREDIT * 1000, 2)


def _llamacloud_client():
    """Cliente del SDK v2 (`llama-cloud>=1.0`). Error claro si falta la key o el SDK
    instalado es el viejo (0.x, API v1 sin tiers)."""
    api_key = config.LLAMA_CLOUD_API_KEY
    if not api_key:
        raise RuntimeError(
            "Falta LLAMA_CLOUD_API_KEY. Consíguela en https://cloud.llamaindex.ai "
            "y colócala en el archivo .env para usar LlamaParse."
        )
    from importlib.metadata import PackageNotFoundError, version

    try:
        major = int(version("llama-cloud").split(".")[0])
    except PackageNotFoundError:
        major = 0
    if major < 1:
        raise RuntimeError(
            "LlamaParse v2 (tiers) necesita el SDK llama-cloud>=1.0. Instálalo con: "
            "pip install -U 'llama-cloud>=1.0'"
        )
    from llama_cloud import LlamaCloud

    return LlamaCloud(api_key=api_key)


def parse_with_llamaparse(raw: bytes, filename: str, tier: str) -> list[dict[str, Any]]:
    """Parsea un archivo con LlamaParse v2 en el `tier` indicado. Un documento por
    página. Lo usa el catálogo de loaders y también el OCR del pipeline
    (pipeline/etapas/e03_ocr.py) cuando se elige LlamaParse como motor de OCR."""
    if tier not in LLAMAPARSE_TIERS:
        raise KeyError(f"Tier de LlamaParse desconocido: {tier}")
    expand = LLAMAPARSE_TIERS[tier]["expand"]

    result = _llamacloud_client().parsing.parse(
        upload_file=(filename or "documento.pdf", raw),
        tier=tier,
        version="latest",
        expand=[expand],
        processing_options={"ocr_parameters": {"languages": LLAMAPARSE_OCR_LANGUAGES}},
    )
    # result.markdown.pages[].markdown  ·  result.text.pages[].text
    # Una página fallida viene sin contenido y con `error`: se conserva el aviso.
    pages = getattr(getattr(result, expand, None), "pages", None) or []
    docs: list[dict[str, Any]] = []
    for i, page in enumerate(pages):
        meta: dict[str, Any] = {
            "page": getattr(page, "page_number", None) or i + 1,
            "llamaparse_tier": tier,
        }
        if getattr(page, "error", None):
            meta["error"] = page.error
        docs.append({"text": getattr(page, expand, None) or "", "metadata": meta})
    return docs


def make_llamaparse_loader(tier: str) -> Callable[[bytes, str], list[dict[str, Any]]]:
    """Loader (raw, filename) -> documentos, fijado a un tier de LlamaParse."""

    def _load(raw: bytes, filename: str) -> list[dict[str, Any]]:
        return parse_with_llamaparse(raw, filename, tier)

    return _load
