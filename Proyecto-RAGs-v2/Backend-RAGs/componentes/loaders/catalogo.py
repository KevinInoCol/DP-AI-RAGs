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

from typing import Any

from .llamaparse import LLAMAPARSE_TIERS, llamaparse_cost_per_1k_pages, make_llamaparse_loader
from .locales import (
    load_pdf_table,
    load_pdfreader,
    load_pymupdf,
    load_pymupdf4llm,
    load_pypdf,
    load_smart_pdf,
    load_unstructured,
)


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
        "loader": load_pypdf,
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
        "loader": load_pdfreader,
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
        "loader": load_unstructured,
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
        "loader": load_pymupdf,
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
        "loader": load_pymupdf4llm,
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
        "loader": load_pdf_table,
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
        "loader": load_smart_pdf,
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
            "loader": make_llamaparse_loader(tier),
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
