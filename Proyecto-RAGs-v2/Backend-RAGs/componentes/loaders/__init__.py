"""
Document Loaders: extraen el texto de un archivo (PDF, DOCX…).

  catalogo.py    · las opciones que ve la UI, de peor a mejor, con su precio
  locales.py     · loaders que corren en el equipo (pypdf, PyMuPDF, PyMuPDF4LLM…)
  llamaparse.py  · LlamaParse v2 en la nube (también lo usa el OCR del pipeline)
"""

from .catalogo import LOADERS, list_loaders, load_document
from .llamaparse import LLAMAPARSE_TIERS, llamaparse_cost_per_1k_pages, parse_with_llamaparse
from .locales import extract_markdown_pages

__all__ = [
    "LLAMAPARSE_TIERS",
    "LOADERS",
    "extract_markdown_pages",
    "list_loaders",
    "llamaparse_cost_per_1k_pages",
    "load_document",
    "parse_with_llamaparse",
]
