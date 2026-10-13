"""
Pipeline de ingesta RAG · DESCRIPCIÓN DEL FLUJO (para el frontend)
Ruta: Backend-RAGs/pipeline/flujo.py

`describe_pipeline()` devuelve el pipeline como una secuencia vertical de nodos
(`step` · `decision` · `end`) con las opciones de cada etapa, leídas de los
catálogos reales (loaders, OCR, splitters, embedders, vector stores). Así el
diagrama del frontend no se desincroniza del código.

Cada etapa lleva `number`, el MISMO número que su archivo en pipeline/etapas/
(e02_validacion … e09_indexado): la UI lo muestra tal cual. En la decisión
`needs_ocr` el número es de sus dos ramas (03 loader | 03 OCR); la decisión
`index_route` va AL FINAL y sin número: la toma Qdrant solo, después de que la
etapa 09 guarda los vectores. El campo
`module` de cada nodo apunta al archivo real.

Estado de cada opción:
  active     · la usa hoy la ingesta (POST /ingest) por defecto
  selectable · se puede elegir por ingesta (campo `field` del nodo en POST /ingest)
  testbed    · disponible para comparar en su pestaña, no conectada a /ingest
  planned    · evaluada pero aún no implementada
"""

from __future__ import annotations

from typing import Any

from componentes.embeddings import EMBEDDERS, default_embedder, embedding_dimension, list_embedders
from componentes.loaders import list_loaders
from componentes.splitters import list_splitters

from .etapas import e04_normalizacion, e05_limpieza
from .etapas.e03_loader import INGEST_LOADER, is_valid_loader
from .etapas.e03_ocr import DEFAULT_OCR_ENGINE, list_ocr_engines
from .etapas.e06_chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    INGEST_SPLITTER,
    is_valid_splitter,
)
from .etapas.e09_indexado import DEFAULT_INDEXING_THRESHOLD_KB, vectors_per_threshold
from .naming import COLLECTION_PREFIX


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


def _index_route_detail() -> str:
    """Explica el umbral en vectores para la dimensión del embedder por defecto."""
    key = default_embedder() or next(iter(EMBEDDERS))
    dim = embedding_dimension(key)
    n = vectors_per_threshold(DEFAULT_INDEXING_THRESHOLD_KB, dim)
    return (
        f"Lo decide Qdrant solo, en segundo plano y POR SEGMENTO. El umbral está en KB: "
        f"{DEFAULT_INDEXING_THRESHOLD_KB:,} KB ≈ {n:,} vectores de {dim} dims por segmento "
        f"(1 KB = 256 dims). Tu servidor puede usar otro valor: la ingesta reporta la "
        f"ruta real."
    )


def describe_pipeline() -> dict[str, Any]:
    """Pipeline de ingesta completo, de arriba hacia abajo."""
    return {
        "nodes": [
            {
                "id": "upload",
                "number": 1,
                "kind": "step",
                "title": "Carga de documentos",
                "detail": "El usuario sube sus PDFs a la base de conocimiento de su tenant.",
                "module": "api/routers/ingesta.py · POST /ingest · /ingest/gcs",
                "provider": "Propio (FastAPI)",
                "field": "source",
                "options": [
                    {"key": "upload", "name": "Subida directa (multipart)",
                     "provider": "Propio (FastAPI)", "status": "active",
                     "pricing": {"kind": "free", "label": "Gratis (propio)"}},
                    {"key": "gcs", "name": "Bucket de Google Cloud Storage",
                     "provider": "Google Cloud", "status": "selectable",
                     "pricing": {"kind": "paid", "label": "Por GB almacenado",
                                 "note": "Tarifa de almacenamiento de Google Cloud Storage."}, "module": "pipeline/fuentes/gcs.py"},
                    {"key": "onedrive", "name": "OneDrive / SharePoint (Microsoft Graph)",
                     "provider": "Microsoft", "status": "testbed",
                     "pricing": {"kind": "freemium", "label": "Incluido en Microsoft 365",
                                 "note": "Sin costo extra si el cliente ya tiene la licencia."}, "module": "pipeline/fuentes/onedrive.py"},
                ],
            },
            {
                "id": "validate",
                "number": 2,
                "kind": "step",
                "title": "Validación de páginas",
                "detail": (
                    "Antes de extraer nada, lee la capa de texto NATIVA de cada página "
                    "y la clasifica: ok · scanned · empty · garbage."
                ),
                "module": "pipeline/etapas/e02_validacion.py",
                "provider": "Propio · sobre PyMuPDF (Artifex Software)",
                "options": [],
            },
            {
                "id": "needs_ocr",
                "number": 3,
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
                            "Extrae las páginas con texto nativo. Por defecto PyMuPDF4LLM "
                            "(Markdown estructurado, auto-OCR apagado); se puede elegir "
                            "cualquier loader que devuelva un documento por página."
                        ),
                        "module": "pipeline/etapas/e03_loader.py",
                        "provider": "Artifex Software (PyMuPDF4LLM) u otro loader",
                        "field": "loader",
                        "options": [
                            {**o, "status": "selectable"}
                            if o["status"] == "testbed" and is_valid_loader(o["key"]) else o
                            for o in _options(list_loaders(), INGEST_LOADER)
                        ],
                    },
                    "yes": {
                        "title": "OCR (español)",
                        "detail": (
                            "Solo las páginas escaneadas o ilegibles. El motor se "
                            "elige por ingesta (campo ocr_engine)."
                        ),
                        "module": "pipeline/etapas/e03_ocr.py",
                        "provider": "Tesseract (open source) o LlamaIndex (LlamaCloud)",
                        "field": "ocr_engine",
                        "options": _ocr_options(),
                    },
                },
            },
            {
                "id": "normalize",
                "number": 4,
                "kind": "step",
                "title": "Normalización",
                "detail": "Unicode NFKC, caracteres invisibles, des-hifenización, espacios.",
                "module": "pipeline/etapas/e04_normalizacion.py",
                "provider": "Propio (Python estándar)",
                "how_it_works": {
                    "steps": e04_normalizacion.EXPLAINED_STEPS,
                    "note": e04_normalizacion.NOT_DONE,
                },
                "options": [],
            },
            {
                "id": "boilerplate",
                "number": 5,
                "kind": "step",
                "title": "Limpieza de encabezados y pies",
                "detail": (
                    "Quita encabezados, pies y numeración que se repiten en el borde de "
                    "muchas páginas. Ante la duda, no borra."
                ),
                "module": "pipeline/etapas/e05_limpieza.py",
                "provider": "Propio (Python estándar)",
                "how_it_works": {
                    "steps": e05_limpieza.EXPLAINED_STEPS,
                    "note": e05_limpieza.NOT_DONE,
                },
                "options": [],
            },
            {
                "id": "chunk",
                "number": 6,
                "kind": "step",
                "title": "Chunking",
                "detail": (
                    "MarkdownNodeParser por secciones + SentenceSplitter "
                    f"({DEFAULT_CHUNK_SIZE} tokens, solape {DEFAULT_CHUNK_OVERLAP})."
                ),
                "module": "pipeline/etapas/e06_chunking.py",
                "provider": "LlamaIndex",
                "field": "splitter",
                # Las opciones se muestran en un grupo por framework (ver splitters/).
                "option_groups": [
                    {
                        "key": "llamaindex",
                        "label": "LlamaIndex",
                        "note": (
                            "El framework del pipeline. Cualquiera se puede elegir para "
                            "la ingesta (salvo el de código), con sus parámetros por defecto."
                        ),
                    },
                    {
                        "key": "langchain",
                        "label": "LangChain",
                        "note": (
                            "Las técnicas equivalentes en LangChain. También se pueden "
                            "elegir, salvo los de código, JSON y HTML (la ingesta trae Markdown)."
                        ),
                    },
                ],
                "options": [
                    {"key": INGEST_SPLITTER, "name": "Markdown estructural (pipeline)",
                     "provider": "LlamaIndex", "status": "active", "group": "llamaindex",
                     "pricing": {"kind": "free", "label": "Gratis (local)"}},
                    *(
                        {**o, "status": "selectable"} if is_valid_splitter(o["key"]) else o
                        for o in _options(list_splitters(), None)
                    ),
                ],
            },
            {
                "id": "metadata",
                "number": 7,
                "kind": "step",
                "title": "Metadata e idempotencia",
                "detail": "Checksum sha256 del documento e IDs deterministas por chunk.",
                "module": "pipeline/etapas/e07_metadata.py",
                "provider": "Propio (Python estándar)",
                "options": [],
            },
            {
                "id": "embed",
                "number": 8,
                "kind": "step",
                "title": "Embeddings",
                "detail": _embed_detail(),
                "module": "pipeline/etapas/e08_embeddings.py · componentes/embeddings",
                "provider": "Google u OpenAI (vía LlamaIndex)",
                "field": "embedder",
                "options": _embedder_options(),
            },
            {
                "id": "store",
                "number": 9,
                "kind": "step",
                "title": "Qdrant · colección del tenant",
                "detail": (
                    f"Guarda los vectores en la colección {COLLECTION_PREFIX}<slug> del "
                    "tenant, con upsert idempotente (reingestar el mismo PDF no duplica)."
                ),
                "module": "pipeline/etapas/e09_indexado.py · pipeline/naming.py",
                "provider": "Qdrant",
                # La ingesta siempre escribe en Qdrant: no hay opciones que elegir aquí.
                "options": [],
            },
            {
                "id": "index_route",
                "kind": "decision",
                "question": "Después de guardar: ¿algún segmento supera el indexing_threshold?",
                "detail": _index_route_detail(),
                "branches": {
                    "no": {
                        "title": "Fuerza bruta",
                        "provider": "Qdrant",
                        "detail": (
                            "Full scan exacto del segmento. Recall 100%, suficiente con "
                            "pocos vectores."
                        ),
                        "options": [],
                    },
                    "yes": {
                        "title": "HNSW (ANN)",
                        "provider": "Qdrant",
                        "detail": (
                            "Índice aproximado del segmento. Búsqueda rápida a gran escala. "
                            "Se construye en segundo plano: una colección puede quedar "
                            "mixta (unos segmentos con HNSW y otros sin indexar)."
                        ),
                        "options": [],
                    },
                },
            },
        ],
    }
