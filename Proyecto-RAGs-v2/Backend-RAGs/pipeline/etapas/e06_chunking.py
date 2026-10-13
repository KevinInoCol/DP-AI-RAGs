"""
Pipeline de ingesta RAG · 06 · CHUNKING (estructural por defecto o un splitter del catálogo)
Ruta: Backend-RAGs/pipeline/etapas/e06_chunking.py

Divide el Markdown del documento en chunks. Por defecto (INGEST_SPLITTER) el corte
es CONSCIENTE DE LA ESTRUCTURA, no por tamaño a ciegas: aprovecha los headers
(#/##/...) que trae pymupdf4llm. Con otra clave (`splitter` de POST /ingest) se
usa cualquier técnica del catálogo de componentes/splitters con sus parámetros
por defecto, salvo las de SPLITTERS_NOT_FOR_INGEST.

Estrategia por defecto (2 fases, vía LlamaIndex):
  1. MarkdownNodeParser  -> corta por secciones/headers (mantiene la jerarquia de
     titulos en la metadata; no parte tablas dentro de una seccion).
  2. SentenceSplitter    -> sub-divide las secciones que exceden `chunk_size`
     (en tokens) respetando fronteras de oracion, con solape.

Asi los chunks quedan semanticamente coherentes -> mucho mejor recall.

Nota: se chunkea el Markdown del DOCUMENTO COMPLETO (no por pagina) para que las
secciones que cruzan saltos de pagina no se rompan. La atribucion de pagina exacta
por chunk se pierde a cambio de secciones intactas (trade-off consciente).
"""

from __future__ import annotations

from typing import Any

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter

from componentes.splitters import list_splitters, split_text

DEFAULT_CHUNK_SIZE = 512      # tokens
DEFAULT_CHUNK_OVERLAP = 64    # tokens

# Splitter por defecto de la ingesta: Markdown por secciones + SentenceSplitter.
INGEST_SPLITTER = "markdown_structural"

# Splitters del catálogo que NO sirven para la ingesta: esperan código, JSON o HTML
# y la ingesta les pasa el Markdown de un PDF. Siguen comparables en su pestaña.
SPLITTERS_NOT_FOR_INGEST = {"code", "lc_code", "lc_json", "lc_html_header"}


def is_valid_splitter(key: str) -> bool:
    """True si la clave es el chunking estructural o una técnica apta del catálogo."""
    if key in SPLITTERS_NOT_FOR_INGEST:
        return False
    return key == INGEST_SPLITTER or key in {s["key"] for s in list_splitters()}


def chunk_document(markdown: str, splitter: str, source: str) -> list[dict[str, Any]]:
    """Chunks del documento con el splitter elegido (validado con is_valid_splitter)."""
    if splitter == INGEST_SPLITTER:
        return chunk_markdown(markdown, metadata={"source": source})
    return split_text(splitter, markdown)


def chunk_markdown(
    markdown: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Divide un Markdown en chunks estructurales. Devuelve [{index, text, char_count,
    metadata}], donde metadata incluye la jerarquia de headers de la seccion."""
    if not markdown or not markdown.strip():
        return []

    doc = Document(text=markdown, metadata=metadata or {})

    # 1) por secciones (headers)
    section_nodes = MarkdownNodeParser().get_nodes_from_documents([doc])
    # 2) sub-dividir las secciones grandes por tamaño (tokens) con solape
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    nodes = splitter.get_nodes_from_documents(section_nodes)

    chunks: list[dict[str, Any]] = []
    for i, node in enumerate(nodes):
        content = node.get_content()
        # La metadata del nodo trae la jerarquia de headers (p.ej. "Header 1"...)
        # + la metadata base que le pasamos al Document.
        node_meta = {
            k: v
            for k, v in (node.metadata or {}).items()
            if isinstance(v, (str, int, float, bool))
        }
        chunks.append(
            {
                "index": i,
                "text": content,
                "char_count": len(content),
                "metadata": node_meta,
            }
        )
    return chunks
