"""
Pipeline de ingesta RAG · B · OCR CONTROLADO (español)
Ruta: Backend-RAGs/pipeline/stages/b_ocr.py

OCR de las páginas escaneadas que marca a_extraction_validator.py, EN ESPAÑOL
(por defecto `spa+eng` — Tesseract combina idiomas, robusto para docs mixtos),
en vez del auto-OCR de pymupdf4llm que corre en INGLÉS y destroza tildes/ñ
(probado: "daños" -> "danos", que es otra palabra).

Requiere Tesseract + los traineddata de idiomas:
  macOS:  brew install tesseract tesseract-lang
  Linux:  apt-get install tesseract-ocr tesseract-ocr-spa

La carpeta `tessdata` se autodetecta (o se respeta TESSDATA_PREFIX).

Motores de OCR disponibles (`list_ocr_engines()`, elegible por ingesta):
  tesseract                 · local, gratis, spa+eng (default)
  llama_parse_<tier>        · LlamaParse v2 en la nube (fast · cost_effective ·
                              agentic · agentic_plus). Solo se envían las páginas
                              escaneadas, en un PDF recortado.
"""

from __future__ import annotations

import os
from typing import Any

import pymupdf

# `spa+eng`: español primero, con inglés de respaldo para PDFs mixtos.
DEFAULT_LANGUAGE = "spa+eng"
DEFAULT_DPI = 200  # 200-300 dpi da buen OCR sin disparar el costo/tiempo

# Ubicaciones típicas de la carpeta tessdata (idiomas).
_TESSDATA_CANDIDATES = (
    "/opt/homebrew/share/tessdata",              # macOS Apple Silicon (Homebrew)
    "/usr/local/share/tessdata",                 # macOS Intel / Linux manual
    "/usr/share/tessdata",
    "/usr/share/tesseract-ocr/5/tessdata",       # Debian/Ubuntu (tesseract 5)
    "/usr/share/tesseract-ocr/4.00/tessdata",    # Debian/Ubuntu (tesseract 4)
)


def resolve_tessdata() -> str | None:
    """Ubica la carpeta `tessdata`. Respeta TESSDATA_PREFIX si está definido."""
    env = os.getenv("TESSDATA_PREFIX")
    if env and os.path.isdir(env):
        return env
    for cand in _TESSDATA_CANDIDATES:
        if os.path.isdir(cand):
            return cand
    return None


def ocr_diagnostics() -> dict[str, Any]:
    """Estado del OCR: dónde está tessdata y si están los idiomas necesarios.
    Útil para un health-check antes de procesar (fallar temprano y claro)."""
    tessdata = resolve_tessdata()
    langs: list[str] = []
    if tessdata:
        try:
            langs = sorted(
                f[: -len(".traineddata")]
                for f in os.listdir(tessdata)
                if f.endswith(".traineddata")
            )
        except OSError:
            langs = []
    return {
        "tessdata": tessdata,
        "available": tessdata is not None and "spa" in langs,
        "num_languages": len(langs),
        "has_spanish": "spa" in langs,
        "has_english": "eng" in langs,
    }


# --------------------------------------------------------------------------- #
# Catálogo de motores de OCR
# --------------------------------------------------------------------------- #
DEFAULT_OCR_ENGINE = "tesseract"


def _ocr_engines() -> dict[str, dict[str, Any]]:
    """Tesseract + un motor por tier de LlamaParse (import diferido: el catálogo
    de loaders es la fuente de verdad de los tiers y sus precios)."""
    from loaders import LLAMAPARSE_TIERS, llamaparse_cost_per_1k_pages

    engines: dict[str, dict[str, Any]] = {
        "tesseract": {
            "name": "Tesseract (spa+eng)",
            "provider": "Open source (creado por HP, impulsado por Google)",
            "group": "no_api",
            "engine": "Tesseract 5 vía PyMuPDF",
            "cost_usd_per_1k_pages": 0.0,
            "description": (
                "OCR local y gratuito, en español con inglés de respaldo. Bueno con "
                "escaneos limpios; flojo con fotocopias, sellos, manuscrito y tablas."
            ),
        },
    }
    for tier, cfg in LLAMAPARSE_TIERS.items():
        engines[f"llama_parse_{tier}"] = {
            "name": f"LlamaParse · {cfg['label']}",
            "provider": "LlamaIndex (LlamaCloud)",
            "group": "api",
            "engine": f"LlamaCloud v2 · tier={tier}",
            "cost_usd_per_1k_pages": llamaparse_cost_per_1k_pages(tier),
            "description": (
                f"OCR en la nube con LlamaParse ({cfg['credits_per_page']} créditos/pág.). "
                "Solo se envían las páginas escaneadas. Requiere LLAMA_CLOUD_API_KEY."
            ),
        }
    return engines


def list_ocr_engines() -> list[dict[str, Any]]:
    """Catálogo de motores de OCR para el frontend (del más barato al más caro)."""
    items = sorted(_ocr_engines().items(), key=lambda kv: kv[1]["cost_usd_per_1k_pages"])
    return [
        {
            "key": key,
            **cfg,
            "pricing": (
                {"kind": "paid", "label": f"${cfg['cost_usd_per_1k_pages']:.2f} / 1k pág."}
                if cfg["cost_usd_per_1k_pages"]
                else {"kind": "free", "label": "Gratis (local)"}
            ),
            "requires_api_key": cfg["group"] == "api",
            "default": key == DEFAULT_OCR_ENGINE,
        }
        for key, cfg in items
    ]


# --------------------------------------------------------------------------- #
# OCR
# --------------------------------------------------------------------------- #
def ocr_pages(
    raw: bytes,
    pages: list[int] | None = None,
    engine: str = DEFAULT_OCR_ENGINE,
    language: str = DEFAULT_LANGUAGE,
    dpi: int = DEFAULT_DPI,
) -> dict[int, str]:
    """OCR de las páginas indicadas (índices 0-based) de un PDF en bytes.

    Args:
      raw:      bytes del PDF.
      pages:    índices 0-based a OCRear (típicamente el `ocr_pages` del validador).
                None → OCR de TODAS las páginas.
      engine:   clave de `list_ocr_engines()` (tesseract | llama_parse_<tier>).
      language: idioma(s) Tesseract, p.ej. "spa", "eng", "spa+eng" (solo tesseract).
      dpi:      resolución de render para el OCR (solo tesseract).

    Devuelve {indice_pagina: texto_ocr}.
    """
    if engine not in _ocr_engines():
        raise KeyError(f"Motor de OCR desconocido: {engine}")
    if engine == "tesseract":
        return _ocr_tesseract(raw, pages, language=language, dpi=dpi)
    return _ocr_llamaparse(raw, pages, tier=engine.removeprefix("llama_parse_"))


def _target_pages(doc: pymupdf.Document, pages: list[int] | None) -> list[int]:
    """Índices válidos a procesar (todas las páginas si `pages` es None)."""
    targets = pages if pages is not None else list(range(doc.page_count))
    return [i for i in targets if 0 <= i < doc.page_count]


def _ocr_tesseract(raw: bytes, pages: list[int] | None, language: str, dpi: int) -> dict[int, str]:
    """OCR local con Tesseract. Lanza RuntimeError si falta tessdata."""
    tessdata = resolve_tessdata()
    if tessdata is None:
        raise RuntimeError(
            "No se encontró la carpeta 'tessdata' de Tesseract. Instálalo con: "
            "brew install tesseract tesseract-lang (macOS) o define TESSDATA_PREFIX."
        )

    doc = pymupdf.open(stream=raw, filetype="pdf")
    try:
        out: dict[int, str] = {}
        for i in _target_pages(doc, pages):
            page = doc[i]
            tp = page.get_textpage_ocr(
                language=language, dpi=dpi, full=True, tessdata=tessdata
            )
            out[i] = page.get_text(textpage=tp)
        return out
    finally:
        doc.close()


def _ocr_llamaparse(raw: bytes, pages: list[int] | None, tier: str) -> dict[int, str]:
    """OCR con LlamaParse: arma un PDF SOLO con las páginas pedidas (se paga por
    página), lo parsea y reasigna cada resultado a su índice original."""
    from loaders import parse_with_llamaparse

    src = pymupdf.open(stream=raw, filetype="pdf")
    try:
        targets = _target_pages(src, pages)
        if not targets:
            return {}
        subset = pymupdf.open()
        try:
            for i in targets:
                subset.insert_pdf(src, from_page=i, to_page=i)
            subset_raw = subset.tobytes()
        finally:
            subset.close()
    finally:
        src.close()

    docs = parse_with_llamaparse(subset_raw, "paginas_escaneadas.pdf", tier)
    return {orig: docs[j]["text"] for j, orig in enumerate(targets) if j < len(docs)}


def ocr_page_text(
    raw: bytes,
    page_index: int,
    engine: str = DEFAULT_OCR_ENGINE,
    language: str = DEFAULT_LANGUAGE,
    dpi: int = DEFAULT_DPI,
) -> str:
    """Atajo: OCR de una sola página. Devuelve su texto (o '' si no aplica)."""
    return ocr_pages(raw, [page_index], engine=engine, language=language, dpi=dpi).get(page_index, "")
