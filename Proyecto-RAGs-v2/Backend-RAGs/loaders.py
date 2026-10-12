"""
Catálogo de Document Loaders (Readers) para extraer texto de archivos.

Ordenados de PEOR a MEJOR (campo `quality`, 1 = básico … 8 = el mejor):

  1. PyPDF (manual)          -> extracción cruda, sin framework (baseline)
  2. PDFReader (LlamaIndex)  -> Reader básico del framework
  3. UnstructuredReader      -> particiona en elementos (títulos, párrafos, tablas)
  4. PyMuPDFReader (Llama.)  -> mejor extracción de texto y layout
  4. PDFTableReader          -> especializado: extrae SOLO tablas (camelot) [Ghostscript]
  5. PyMuPDF4LLM             -> Markdown estructurado, local (default del pipeline)
  5. SmartPDFLoader          -> layout jerárquico por secciones [servicio nlm-ingestor]
  5..8 LlamaParse v2         -> parsing con IA en la nube, 4 tiers [API KEY]:
       fast · cost_effective · agentic · agentic_plus

Cada entrada lleva `cost_usd_per_1k_pages` (0 = local/gratis) para comparar
calidad vs. precio.

Cada loader recibe (raw: bytes, filename: str) y devuelve una lista de
"documentos" -> [{"text": str, "metadata": dict}]. Un PDF suele producir un
documento por página.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


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
def _load_pypdf(raw: bytes, filename: str) -> list[dict[str, Any]]:
    """1) PyPDF manual: recorre páginas y usa page.extract_text()."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    return [
        {"text": (page.extract_text() or ""), "metadata": {"page": i + 1}}
        for i, page in enumerate(reader.pages)
    ]


def _load_pdfreader(raw: bytes, filename: str) -> list[dict[str, Any]]:
    """2) PDFReader de LlamaIndex (envuelve pypdf, un Document por página)."""
    from llama_index.readers.file import PDFReader

    tmp = _write_temp(raw, filename)
    try:
        documents = PDFReader().load_data(file=Path(tmp))
    finally:
        os.unlink(tmp)
    return _docs_from_llama(documents)


def _load_pymupdf(raw: bytes, filename: str) -> list[dict[str, Any]]:
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
             pipeline/stages/b_ocr.py.
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


def _load_pymupdf4llm(raw: bytes, filename: str) -> list[dict[str, Any]]:
    """Loader del catálogo: todas las páginas, con el auto-OCR (inglés) por defecto."""
    return extract_markdown_pages(raw, filename)


def _load_unstructured(raw: bytes, filename: str) -> list[dict[str, Any]]:
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


def _load_pdf_table(raw: bytes, filename: str) -> list[dict[str, Any]]:
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


def _load_smart_pdf(raw: bytes, filename: str) -> list[dict[str, Any]]:
    """SmartPDFLoader: usa llmsherpa para detectar el layout jerárquico (secciones,
    subsecciones, tablas) y devuelve chunks conscientes de la estructura. Necesita
    un servicio nlm-ingestor accesible vía LLMSHERPA_API_URL."""
    api_url = os.getenv("LLMSHERPA_API_URL")
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


# --------------------------------------------------------------------------- #
# LlamaParse v2 (LlamaCloud) · 4 tiers
# --------------------------------------------------------------------------- #
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
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
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
    (pipeline/stages/b_ocr.py) cuando se elige LlamaParse como motor de OCR."""
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


def _make_llamaparse_loader(tier: str) -> Callable[[bytes, str], list[dict[str, Any]]]:
    """Loader (raw, filename) -> documentos, fijado a un tier de LlamaParse."""

    def _load(raw: bytes, filename: str) -> list[dict[str, Any]]:
        return parse_with_llamaparse(raw, filename, tier)

    return _load


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #
LOADERS: dict[str, dict[str, Any]] = {
    "pypdf": {
        "name": "PyPDF (manual)",
        "provider": "py-pdf (open source)",
        "group": "no_api",
        "quality": 1,
        "engine": "pypdf",
        "accepts": [".pdf"],
        "description": (
            "El clásico. Extracción cruda página por página con page.extract_text(). "
            "Sin framework. Funciona con PDFs de texto simple, pero pierde tablas, "
            "columnas y no hace OCR de escaneos."
        ),
        "loader": _load_pypdf,
    },
    "pdf_reader": {
        "name": "PDFReader (LlamaIndex)",
        "provider": "LlamaIndex (sobre pypdf)",
        "group": "no_api",
        "quality": 2,
        "engine": "llama-index-readers-file",
        "accepts": [".pdf"],
        "description": (
            "El Reader básico de LlamaIndex. Envuelve pypdf y devuelve un objeto "
            "Document por página con metadata (page_label). Ya usa la abstracción "
            "del framework, pero la calidad de extracción es similar a PyPDF."
        ),
        "loader": _load_pdfreader,
    },
    "unstructured": {
        "name": "UnstructuredReader (LlamaIndex)",
        "provider": "Unstructured.io (vía LlamaIndex)",
        "group": "no_api",
        "quality": 3,
        "engine": "unstructured (strategy=fast)",
        "accepts": [".pdf"],
        "description": (
            "Usa la librería 'unstructured' para particionar el documento en "
            "elementos semánticos (títulos, párrafos, listas, tablas). Aquí corre "
            "en modo 'fast' (motor pdfminer, sin modelos de IA). Buena para conservar "
            "la estructura del contenido."
        ),
        "loader": _load_unstructured,
    },
    "pymupdf": {
        "name": "PyMuPDFReader (LlamaIndex)",
        "provider": "Artifex Software (vía LlamaIndex)",
        "group": "no_api",
        "quality": 4,
        "engine": "pymupdf / fitz",
        "accepts": [".pdf"],
        "description": (
            "Usa el motor PyMuPDF (fitz). Extracción más rápida y precisa, respeta "
            "mejor el orden de lectura y el layout. La mejor opción SIN API key para "
            "PDFs de texto."
        ),
        "loader": _load_pymupdf,
    },
    "pymupdf4llm": {
        "name": "PyMuPDF4LLM (Markdown)",
        "provider": "Artifex Software",
        "group": "no_api",
        "quality": 5,
        "engine": "pymupdf4llm (MuPDF → Markdown)",
        "accepts": [".pdf"],
        "description": (
            "Capa sobre PyMuPDF que extrae el PDF como MARKDOWN estructurado: detecta "
            "títulos, listas, negritas y TABLAS, y respeta el multi-columna. Mismo motor "
            "local y determinístico (SIN IA, sin nube), pero conservar la estructura mejora "
            "el chunking y el retrieval. La mejor opción local para RAG. Si Tesseract está "
            "instalado, OCRea las páginas escaneadas pero en INGLÉS (pierde tildes/ñ); "
            "por eso el pipeline las vuelve a OCRear en español."
        ),
        "loader": _load_pymupdf4llm,
    },
    "pdf_table": {
        "name": "PDFTableReader (LlamaIndex)",
        "provider": "camelot (open source, vía LlamaIndex)",
        "group": "no_api",
        "quality": 4,
        "engine": "camelot (lattice)",
        "accepts": [".pdf"],
        "description": (
            "🔬 ESPECIALIZADO: extrae SOLO las tablas del PDF (no el texto corrido) "
            "usando camelot, y devuelve un documento por tabla. Ideal para PDFs con "
            "datos tabulares. Requiere Ghostscript en el sistema (brew install ghostscript)."
        ),
        "loader": _load_pdf_table,
    },
    "smart_pdf": {
        "name": "SmartPDFLoader (LlamaIndex)",
        "provider": "NLMatics (llmsherpa, vía LlamaIndex)",
        "group": "no_api",
        "quality": 5,
        "engine": "llmsherpa / nlm-ingestor",
        "self_hosted": True,  # necesita levantar su servicio (Docker)
        "accepts": [".pdf"],
        "description": (
            "Detecta el layout JERÁRQUICO del PDF (secciones, subsecciones, listas, "
            "tablas) y genera chunks conscientes de la estructura del documento. "
            "Requiere un servicio nlm-ingestor accesible (self-hosted vía Docker) "
            "definido en LLMSHERPA_API_URL."
        ),
        "loader": _load_smart_pdf,
    },
}

_LLAMAPARSE_DESCRIPTIONS = {
    "fast": (
        "Tier más barato de LlamaParse v2 (1 crédito/pág.). Extracción por reglas, "
        "sin LLM; devuelve texto plano (no Markdown), pero sí OCRea páginas escaneadas. "
        "Útil como línea base de la nube."
    ),
    "cost_effective": (
        "Tier equilibrado (3 créditos/pág.). Parsing con modelo de IA: entiende tablas "
        "y columnas y devuelve Markdown. Era el modo que usábamos por defecto."
    ),
    "agentic": (
        "Tier con agente de IA (10 créditos/pág.). Mejor en layouts complejos, tablas "
        "difíciles y escaneos de baja calidad. Devuelve Markdown."
    ),
    "agentic_plus": (
        "Tier premium (45 créditos/pág.). Los modelos más potentes y la máxima "
        "precisión en documentos difíciles. El más caro. Devuelve Markdown."
    ),
}



def _llamaparse_entries() -> dict[str, dict[str, Any]]:
    """Una entrada de catálogo por tier: llama_parse_fast … llama_parse_agentic_plus."""
    return {
        f"llama_parse_{tier}": {
            "name": f"LlamaParse · {cfg['label']}",
            "provider": "LlamaIndex (LlamaCloud)",
            "group": "api",
            "quality": 5 + i,  # fast=5 … agentic_plus=8
            "engine": f"LlamaCloud v2 · tier={tier}",
            "accepts": [".pdf", ".docx", ".pptx", ".xlsx", ".html"],
            "description": _LLAMAPARSE_DESCRIPTIONS[tier] + " Requiere LLAMA_CLOUD_API_KEY.",
            "cost_usd_per_1k_pages": llamaparse_cost_per_1k_pages(tier),
            "loader": _make_llamaparse_loader(tier),
        }
        for i, (tier, cfg) in enumerate(LLAMAPARSE_TIERS.items())
    }


LOADERS.update(_llamaparse_entries())



def _loader_pricing(cfg: dict[str, Any]) -> dict[str, str]:
    """Precio para la UI: gratis si corre local; si no, costo por 1,000 páginas."""
    cost = cfg.get("cost_usd_per_1k_pages", 0.0)
    if cost:
        return {"kind": "paid", "label": f"${cost:.2f} / 1k pág."}
    if cfg.get("self_hosted"):
        return {"kind": "free", "label": "Gratis (self-hosted)"}
    return {"kind": "free", "label": "Gratis (local)"}


def list_loaders() -> list[dict[str, Any]]:
    """Catálogo (sin funciones) para el frontend, ordenado de peor a mejor."""
    items = sorted(LOADERS.items(), key=lambda kv: kv[1]["quality"])
    return [
        {
            "key": key,
            "name": cfg["name"],
            "provider": cfg["provider"],
            "group": cfg["group"],
            "quality": cfg["quality"],
            "engine": cfg["engine"],
            "accepts": cfg["accepts"],
            "description": cfg["description"],
            "requires_api_key": cfg["group"] == "api",
            "cost_usd_per_1k_pages": cfg.get("cost_usd_per_1k_pages", 0.0),
            "pricing": _loader_pricing(cfg),
        }
        for key, cfg in items
    ]


def load_document(key: str, raw: bytes, filename: str) -> list[dict[str, Any]]:
    """Aplica el loader indicado y devuelve la lista de documentos extraídos."""
    if key not in LOADERS:
        raise KeyError(f"Loader desconocido: {key}")
    return LOADERS[key]["loader"](raw, filename)
