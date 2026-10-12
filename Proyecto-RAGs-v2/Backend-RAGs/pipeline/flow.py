"""
Pipeline de ingesta RAG · DESCRIPCIÓN DEL FLUJO (para el frontend)
Ruta: Backend-RAGs/pipeline/flow.py

`describe_pipeline()` devuelve el pipeline como una secuencia vertical de nodos
(`step` · `decision` · `end`) con las opciones de cada etapa, leídas de los
catálogos reales (loaders, OCR, splitters, embedders, vector stores). Así el
diagrama del frontend no se desincroniza del código.

Estado de cada opción:
  active   · la usa hoy la ingesta (POST /ingest)
  testbed  · disponible para comparar en su pestaña, no conectada a /ingest
  planned  · evaluada pero aún no implementada
"""

from __future__ import annotations

from typing import Any

from embeddings import EMBEDDERS, default_embedder, embedding_dimension, list_embedders
from loaders import list_loaders
from splitters import list_splitters
from vectorstores import list_stores

from .orchestrator import INGEST_LOADER
from .sink.naming import COLLECTION_PREFIX
from .sink.qdrant import DEFAULT_INDEXING_THRESHOLD
from .stages.b_ocr import DEFAULT_OCR_ENGINE, list_ocr_engines
from .stages import c_normalize, d_boilerplate
from .stages.e_chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE


def _option(item: dict[str, Any], active_key: str | None) -> dict[str, Any]:
    """Normaliza una entrada de catálogo al formato de opción del diagrama."""
    return {
        "key": item["key"],
        "name": item["name"],
        "provider": item.get("provider"),
        "pricing": item.get("pricing"),
        "description": item.get("description", ""),
        "quality": item.get("quality"),
        "cost_usd_per_1k_pages": item.get("cost_usd_per_1k_pages"),
        "requires_api_key": item.get("requires_api_key", False),
        "status": "active" if item["key"] == active_key else "testbed",
        # Agrupa las opciones en la UI (hoy solo los splitters, por framework).
        "group": item.get("framework"),
    }


def _options(items: list[dict[str, Any]], active_key: str | None) -> list[dict[str, Any]]:
    return [_option(it, active_key) for it in items]


def _ocr_options() -> list[dict[str, Any]]:
    """Motores de OCR (todos elegibles en /ingest) + los evaluados sin implementar."""
    options = [
        {**_option(e, DEFAULT_OCR_ENGINE), "status": "active" if e["default"] else "selectable"}
        for e in list_ocr_engines()
    ]
    options.append({
        "key": "google_document_ai",
        "name": "Google Document AI · Enterprise OCR",
        "provider": "Google Cloud",
        "pricing": {"kind": "paid", "label": "$1.50 / 1k pág."},
        "description": (
            "OCR de Google Cloud. Fuerte con escaneos malos, sellos y manuscrito. "
            "Precio de lista, a confirmar en la tarifa vigente."
        ),
        "quality": None,
        "cost_usd_per_1k_pages": 1.5,
        "requires_api_key": True,
        "status": "planned",
    })
    return options


def _embedder_options() -> list[dict[str, Any]]:
    """Los dos proveedores son elegibles en /ingest (campo `embedder`); el que se
    usa si no se manda ninguno es el resuelto por API key disponible."""
    return [
        {**_option(e, None), "status": "active" if e["is_default"] else "selectable"}
        for e in list_embedders()
    ]


def _embed_detail() -> str:
    auto = default_embedder()
    if auto is None:
        return "Sin API key de embeddings: define GOOGLE_API_KEY u OPENAI_API_KEY en el .env."
    cfg = EMBEDDERS[auto]
    task = " · RETRIEVAL_DOCUMENT" if cfg["asymmetric"] else " · simétrico (doc = query)"
    return f"{cfg['model']} · {embedding_dimension(auto)} dimensiones{task}."


def describe_pipeline() -> dict[str, Any]:
    """Pipeline de ingesta completo, de arriba hacia abajo."""
    return {
        "nodes": [
            {
                "id": "upload",
                "kind": "step",
                "title": "Carga de documentos",
                "detail": "El usuario sube sus PDFs a la base de conocimiento de su tenant.",
                "module": "main.py · POST /ingest · /ingest/gcs",
                "provider": "Propio (FastAPI)",
                "options": [
                    {"key": "upload", "name": "Subida directa (multipart)",
                     "provider": "Propio (FastAPI)", "status": "active",
                     "pricing": {"kind": "free", "label": "Gratis (propio)"}},
                    {"key": "gcs", "name": "Bucket de Google Cloud Storage",
                     "provider": "Google Cloud", "status": "active",
                     "pricing": {"kind": "paid", "label": "Por GB almacenado",
                                 "note": "Tarifa de almacenamiento de Google Cloud Storage."}, "module": "pipeline/sources/gcs.py"},
                    {"key": "onedrive", "name": "OneDrive / SharePoint (Microsoft Graph)",
                     "provider": "Microsoft", "status": "testbed",
                     "pricing": {"kind": "freemium", "label": "Incluido en Microsoft 365",
                                 "note": "Sin costo extra si el cliente ya tiene la licencia."}, "module": "pipeline/sources/onedrive.py"},
                ],
            },
            {
                "id": "validate",
                "kind": "step",
                "title": "Validación de páginas",
                "detail": (
                    "Antes de extraer nada, lee la capa de texto NATIVA de cada página "
                    "y la clasifica: ok · scanned · empty · garbage."
                ),
                "module": "pipeline/stages/a_extraction_validator.py",
                "provider": "Propio · sobre PyMuPDF (Artifex Software)",
                "options": [],
            },
            {
                "id": "needs_ocr",
                "kind": "decision",
                "question": "¿La página es imagen (necesita OCR)?",
                "detail": (
                    "Cada página va por UNA sola rama: scanned o garbage → OCR; "
                    "el resto → extracción de texto. Luego se vuelven a unir en orden."
                ),
                "branches": {
                    "no": {
                        "title": "Extracción de texto (Loader)",
                        "detail": (
                            "Convierte las páginas con texto nativo a Markdown "
                            "estructurado, con el auto-OCR del loader apagado."
                        ),
                        "module": "loaders.py · extract_markdown_pages",
                        "provider": "Artifex Software (PyMuPDF4LLM)",
                        "options": _options(list_loaders(), INGEST_LOADER),
                    },
                    "yes": {
                        "title": "OCR (español)",
                        "detail": (
                            "Solo las páginas escaneadas o ilegibles. El motor se "
                            "elige por ingesta (campo ocr_engine)."
                        ),
                        "module": "pipeline/stages/b_ocr.py",
                        "provider": "Tesseract (open source) o LlamaIndex (LlamaCloud)",
                        "options": _ocr_options(),
                    },
                },
            },
            {
                "id": "normalize",
                "kind": "step",
                "title": "Normalización",
                "detail": "Unicode NFKC, caracteres invisibles, des-hifenización, espacios.",
                "module": "pipeline/stages/c_normalize.py",
                "provider": "Propio (Python estándar)",
                "how_it_works": {
                    "steps": c_normalize.EXPLAINED_STEPS,
                    "note": c_normalize.NOT_DONE,
                },
                "options": [],
            },
            {
                "id": "boilerplate",
                "kind": "step",
                "title": "Limpieza de encabezados y pies",
                "detail": (
                    "Quita encabezados, pies y numeración que se repiten en el borde de "
                    "muchas páginas. Ante la duda, no borra."
                ),
                "module": "pipeline/stages/d_boilerplate.py",
                "provider": "Propio (Python estándar)",
                "how_it_works": {
                    "steps": d_boilerplate.EXPLAINED_STEPS,
                    "note": d_boilerplate.NOT_DONE,
                },
                "options": [],
            },
            {
                "id": "chunk",
                "kind": "step",
                "title": "Chunking estructural",
                "detail": (
                    "MarkdownNodeParser por secciones + SentenceSplitter "
                    f"({DEFAULT_CHUNK_SIZE} tokens, solape {DEFAULT_CHUNK_OVERLAP})."
                ),
                "module": "pipeline/stages/e_chunking.py",
                "provider": "LlamaIndex",
                # Las opciones se muestran en un grupo por framework (ver splitters/).
                "option_groups": [
                    {
                        "key": "llamaindex",
                        "label": "LlamaIndex",
                        "note": (
                            "El framework del pipeline: cualquiera de estos se puede "
                            "enchufar en e_chunking.py sin cambiar el resto de etapas."
                        ),
                    },
                    {
                        "key": "langchain",
                        "label": "LangChain",
                        "note": (
                            "Las técnicas equivalentes en LangChain. El pipeline no las "
                            "usa: devuelven Documents de LangChain, no nodes de LlamaIndex. "
                            "Compáralas en la pestaña Text Splitters."
                        ),
                    },
                ],
                "options": [
                    {"key": "markdown_structural", "name": "Markdown estructural (pipeline)",
                     "provider": "LlamaIndex", "status": "active", "group": "llamaindex",
                     "pricing": {"kind": "free", "label": "Gratis (local)"}},
                    *_options(list_splitters(), None),
                ],
            },
            {
                "id": "metadata",
                "kind": "step",
                "title": "Metadata e idempotencia",
                "detail": "Checksum sha256 del documento e IDs deterministas por chunk.",
                "module": "pipeline/stages/f_metadata.py",
                "provider": "Propio (Python estándar)",
                "options": [],
            },
            {
                "id": "embed",
                "kind": "step",
                "title": "Embeddings",
                "detail": _embed_detail(),
                "module": "embeddings.py",
                "provider": "Google u OpenAI (vía LlamaIndex)",
                "options": _embedder_options(),
            },
            {
                "id": "index_route",
                "kind": "decision",
                "question": f"¿La colección tiene ≥ {DEFAULT_INDEXING_THRESHOLD:,} vectores?",
                "detail": (
                    "Lo decide Qdrant con su indexing_threshold (el de tu servidor "
                    "puede ser distinto; la ingesta lee el real)."
                ),
                "branches": {
                    "no": {
                        "title": "Fuerza bruta",
                        "provider": "Qdrant",
                        "detail": "Full scan exacto. Recall 100%, suficiente con pocos vectores.",
                        "options": [],
                    },
                    "yes": {
                        "title": "HNSW (ANN)",
                        "provider": "Qdrant",
                        "detail": "Índice aproximado. Búsqueda rápida a gran escala.",
                        "options": [],
                    },
                },
            },
            {
                "id": "store",
                "kind": "end",
                "title": "Qdrant · colección del tenant",
                "detail": f"Colección {COLLECTION_PREFIX}<slug>, upsert idempotente.",
                "module": "pipeline/sink/qdrant.py · pipeline/sink/naming.py",
                "provider": "Qdrant",
                "options": _options(list_stores(), None),
            },
        ],
    }
