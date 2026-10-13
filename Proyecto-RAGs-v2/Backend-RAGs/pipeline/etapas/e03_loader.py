"""
Pipeline de ingesta RAG · 03 (rama No) · LOADER de texto nativo
Ruta: Backend-RAGs/pipeline/etapas/e03_loader.py

Extrae las páginas con texto nativo (las que e02_validacion.py NO manda a OCR) con
el loader elegido (`loader` de POST /ingest). Por defecto, INGEST_LOADER:
PyMuPDF4LLM, que da Markdown estructurado, local y sin IA, con su auto-OCR
APAGADO (corre en inglés y destroza tildes/ñ; las escaneadas van a e03_ocr.py).

Solo se pueden elegir los loaders que devuelven UN documento por página
(PAGE_LOADERS): la etapa les pasa un PDF con únicamente las páginas de texto nativo
y reasigna cada resultado a su página original. Los que devuelven otra cosa (un
documento por archivo, solo tablas o chunks) siguen comparables en la pestaña
Document Loaders (componentes/loaders).

El chunking por defecto (e06_chunking.py) aprovecha los headers Markdown: con un
loader de texto plano funciona igual, pero sin secciones.
"""

from __future__ import annotations

from typing import Any

import pymupdf

from componentes.loaders import LLAMAPARSE_TIERS, extract_markdown_pages, load_document

INGEST_LOADER = "pymupdf4llm"

# Loaders del catálogo que devuelven exactamente un documento por página.
PAGE_LOADERS = {
    "pypdf",
    "pdf_reader",
    "pymupdf",
    "pymupdf4llm",
    *(f"llama_parse_{tier}" for tier in LLAMAPARSE_TIERS),
}


def is_valid_loader(key: str) -> bool:
    """True si el loader se puede usar en la ingesta (un documento por página)."""
    return key in PAGE_LOADERS


def pdf_pages_subset(raw: bytes, pages: list[int]) -> tuple[bytes, list[int]]:
    """PDF con SOLO las páginas pedidas (índices 0-based), en ese orden, y la lista
    de índices válidos que contiene. Así no se procesa (ni se paga, en los loaders
    de la nube) ninguna página que no toque."""
    src = pymupdf.open(stream=raw, filetype="pdf")
    try:
        targets = [i for i in pages if 0 <= i < src.page_count]
        subset = pymupdf.open()
        try:
            for i in targets:
                subset.insert_pdf(src, from_page=i, to_page=i)
            return (subset.tobytes() if targets else b""), targets
        finally:
            subset.close()
    finally:
        src.close()


def extract_text_pages(
    raw: bytes, filename: str, pages: list[int], loader: str = INGEST_LOADER
) -> list[dict[str, Any]]:
    """Texto de las páginas indicadas (índices 0-based), una entrada por página y en
    el mismo orden que `pages`."""
    if loader == INGEST_LOADER:
        # PyMuPDF4LLM recibe las páginas directamente y permite apagar su auto-OCR.
        return extract_markdown_pages(raw, filename, pages=pages, use_ocr=False)

    subset_raw, targets = pdf_pages_subset(raw, pages)
    if not targets:
        return []
    docs = load_document(loader, subset_raw, filename)
    if len(docs) != len(targets):
        raise RuntimeError(
            f"El loader {loader} devolvió {len(docs)} documentos para {len(targets)} "
            "páginas: no se puede saber a qué página corresponde cada uno."
        )
    return docs
