"""
Loaders LOCALES (sin nube): cada uno recibe (raw: bytes, filename: str) y devuelve
[{"text": str, "metadata": dict}], normalmente un documento por página.

`extract_markdown_pages` (PyMuPDF4LLM) es además el loader FIJO de la ingesta:
lo usa pipeline/etapas/e03_loader.py para las páginas con texto nativo.
El catálogo que los describe para la UI está en catalogo.py.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import config


def _ensure_macos_ghostscript_lib() -> None:
    """En macOS, camelot busca la librería `libgs` vía ctypes.find_library, que NO
    mira las carpetas de Homebrew (/opt/homebrew/lib en Apple Silicon,
    /usr/local/lib en Intel). Las añadimos a DYLD_FALLBACK_LIBRARY_PATH para que
    Ghostscript sea detectable sin que el usuario exporte nada."""
    if sys.platform != "darwin":
        return
    candidates = [p for p in ("/opt/homebrew/lib", "/usr/local/lib") if os.path.isdir(p)]
    if not candidates:
        return
    current = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    parts = current.split(":") if current else []
    changed = False
    for path in candidates:
        if path not in parts:
            parts.append(path)
            changed = True
    if changed:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(parts)


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def _write_temp(raw: bytes, filename: str) -> str:
    """Escribe los bytes a un archivo temporal y devuelve su ruta.

    Los Readers de LlamaIndex trabajan con rutas de archivo, no con bytes.
    """
    suffix = Path(filename or "").suffix or ".pdf"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(raw)
    tmp.close()
    return tmp.name


def _docs_from_llama(documents: list[Any]) -> list[dict[str, Any]]:
    """Convierte objetos Document de LlamaIndex a dicts serializables."""
    out = []
    for d in documents:
        text = d.get_content() if hasattr(d, "get_content") else str(d)
        meta = dict(d.metadata) if getattr(d, "metadata", None) else {}
        out.append({"text": text, "metadata": meta})
    return out


# --------------------------------------------------------------------------- #
# Implementaciones de cada loader
# --------------------------------------------------------------------------- #
def load_pypdf(raw: bytes, filename: str) -> list[dict[str, Any]]:
    """1) PyPDF manual: recorre páginas y usa page.extract_text()."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    return [
        {"text": (page.extract_text() or ""), "metadata": {"page": i + 1}}
        for i, page in enumerate(reader.pages)
    ]


def load_pdfreader(raw: bytes, filename: str) -> list[dict[str, Any]]:
    """2) PDFReader de LlamaIndex (envuelve pypdf, un Document por página)."""
    from llama_index.readers.file import PDFReader

    tmp = _write_temp(raw, filename)
    try:
        documents = PDFReader().load_data(file=Path(tmp))
    finally:
        os.unlink(tmp)
    return _docs_from_llama(documents)


def load_pymupdf(raw: bytes, filename: str) -> list[dict[str, Any]]:
    """3) PyMuPDFReader de LlamaIndex (motor PyMuPDF/fitz, mejor calidad)."""
    from llama_index.readers.file import PyMuPDFReader

    tmp = _write_temp(raw, filename)
    try:
        reader = PyMuPDFReader()
        try:
            documents = reader.load_data(file_path=tmp)
        except TypeError:
            # Compatibilidad entre versiones (algunas usan `file` en vez de `file_path`)
            documents = reader.load_data(file=Path(tmp))
    finally:
        os.unlink(tmp)
    return _docs_from_llama(documents)


def extract_markdown_pages(
    raw: bytes,
    filename: str,
    pages: list[int] | None = None,
    use_ocr: bool = True,
) -> list[dict[str, Any]]:
    """PyMuPDF4LLM: extrae el PDF como MARKDOWN estructurado (títulos, listas,
    negritas, tablas, multi-columna). Motor local y determinístico (sin IA, sin
    nube). Un documento por página, en el orden de `pages`.

    pages:   índices 0-based a extraer (None = todas).
    use_ocr: False apaga su auto-OCR (que corre en INGLÉS). El pipeline lo apaga y
             solo le manda las páginas con texto nativo; las escaneadas van a
             pipeline/etapas/e03_ocr.py.
    """
    import pymupdf4llm

    tmp = _write_temp(raw, filename)
    try:
        # page_chunks=True -> lista de dicts por página con {text, metadata, ...}
        chunks = pymupdf4llm.to_markdown(tmp, page_chunks=True, pages=pages, use_ocr=use_ocr)
    finally:
        os.unlink(tmp)

    out: list[dict[str, Any]] = []
    for ch in chunks:
        if isinstance(ch, dict):
            text = ch.get("text", "")
            raw_meta = ch.get("metadata", {}) or {}
            # Nos quedamos solo con metadata JSON-serializable (page, title, etc.).
            meta = {k: v for k, v in raw_meta.items() if isinstance(v, (str, int, float, bool))}
        else:
            text, meta = str(ch), {}
        out.append({"text": text, "metadata": meta})
    return out


def load_pymupdf4llm(raw: bytes, filename: str) -> list[dict[str, Any]]:
    """Loader del catálogo: todas las páginas, con el auto-OCR (inglés) por defecto."""
    return extract_markdown_pages(raw, filename)


def load_unstructured(raw: bytes, filename: str) -> list[dict[str, Any]]:
    """UnstructuredReader: particiona el documento en elementos (títulos, párrafos,
    listas, tablas) usando la librería `unstructured`. Aquí forzamos la estrategia
    'fast' (motor pdfminer) para NO descargar modelos de visión/PyTorch."""
    from llama_index.readers.file import UnstructuredReader

    tmp = _write_temp(raw, filename)
    try:
        reader = UnstructuredReader()
        documents = reader.load_data(
            file=Path(tmp),
            unstructured_kwargs={"strategy": "fast"},
            split_documents=False,
        )
    finally:
        os.unlink(tmp)
    return _docs_from_llama(documents)


def load_pdf_table(raw: bytes, filename: str) -> list[dict[str, Any]]:
    """PDFTableReader: extrae SOLO las tablas del PDF (motor camelot, modo lattice)
    y devuelve un Document por tabla. Requiere Ghostscript instalado en el sistema."""
    _ensure_macos_ghostscript_lib()
    from llama_index.readers.pdf_table import PDFTableReader

    tmp = _write_temp(raw, filename)
    try:
        reader = PDFTableReader()
        try:
            documents = reader.load_data(file=Path(tmp), pages="all")
        except Exception as exc:  # noqa: BLE001
            if "ghostscript" in str(exc).lower():
                raise RuntimeError(
                    "PDFTableReader (camelot) necesita Ghostscript. Instálalo con: "
                    "brew install ghostscript"
                ) from exc
            raise
    finally:
        os.unlink(tmp)
    return _docs_from_llama(documents)


def load_smart_pdf(raw: bytes, filename: str) -> list[dict[str, Any]]:
    """SmartPDFLoader: usa llmsherpa para detectar el layout jerárquico (secciones,
    subsecciones, tablas) y devuelve chunks conscientes de la estructura. Necesita
    un servicio nlm-ingestor accesible vía LLMSHERPA_API_URL."""
    api_url = config.LLMSHERPA_API_URL
    if not api_url:
        raise RuntimeError(
            "SmartPDFLoader necesita un servicio nlm-ingestor. Levántalo con Docker:\n"
            "  docker run -p 5010:5010 ghcr.io/nlmatics/nlm-ingestor:latest\n"
            "y define en .env: "
            "LLMSHERPA_API_URL=http://localhost:5010/api/parseDocument?renderFormat=all"
        )

    from llama_index.readers.smart_pdf_loader import SmartPDFLoader

    tmp = _write_temp(raw, filename)
    try:
        loader = SmartPDFLoader(llmsherpa_api_url=api_url)
        documents = loader.load_data(tmp)
    finally:
        os.unlink(tmp)
    return _docs_from_llama(documents)
