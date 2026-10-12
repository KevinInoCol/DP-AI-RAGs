"""
Pipeline de ingesta RAG · ORQUESTADOR
Ruta: Backend-RAGs/pipeline/orchestrator.py

El pegamento: encadena a validar → (texto nativo → loader | escaneada → b OCR)
→ c → d → e → f → embeddings → upsert a Qdrant, y va EMITIENDO eventos de progreso (generator) para que el
frontend muestre el spinner por paso y la ruta de indexación elegida.

Eventos que emite (dicts):
  {"event":"start", "collection", "num_docs", "ocr_engine", "embedder", "model", "dimension"}
  {"event":"step", "doc", "filename", "step", "label", "status", ...extra}
     step ∈ validate|load|ocr|normalize|boilerplate|chunk|embed|index  (en ese orden)
     status ∈ running|done|skipped|error
     el step "embed" (done) trae: embedder ("gemini"|"openai"), model, vectors, dim
     el step "index" (done) trae: index_route ("brute_force"|"hnsw"), num_vectors, indexing_threshold
  {"event":"doc_error", "doc", "filename", "error"}
  {"event":"done", "collection", "index_route", "num_vectors", "indexing_threshold"}

El PROVEEDOR DE EMBEDDINGS se resuelve una sola vez por lote (Google u OpenAI,
según qué API key haya; ver embeddings.resolve_embedder) y se reporta en el evento
"start": una colección debe tener todos sus vectores del MISMO modelo/dimensión.
"""

from __future__ import annotations

from typing import Any, Iterator

from embeddings import EMBEDDERS, embed_documents, embedding_dimension, resolve_embedder
from loaders import extract_markdown_pages
from vectorstores import _qdrant_client

from .sink import naming, qdrant
from .stages.a_extraction_validator import validate_extraction
from .stages.b_ocr import DEFAULT_OCR_ENGINE, list_ocr_engines, ocr_pages
from .stages.c_normalize import normalize_documents
from .stages.d_boilerplate import remove_boilerplate
from .stages.e_chunking import chunk_markdown
from .stages.f_metadata import build_payloads, document_checksum

# Loader fijo de la ingesta para páginas con texto nativo: Markdown estructurado,
# local (ver loaders.py · extract_markdown_pages).
INGEST_LOADER = "pymupdf4llm"


# --------------------------------------------------------------------------- #
# Ingesta de UN documento (generator de eventos)
# --------------------------------------------------------------------------- #
def _ingest_one(
    client, collection: str, doc_i: int, filename: str, raw: bytes, ocr_engine: str,
    embedder: str,
) -> Iterator[dict[str, Any]]:
    def ev(step: str, label: str, status: str, **extra: Any) -> dict[str, Any]:
        return {"event": "step", "doc": doc_i, "filename": filename,
                "step": step, "label": label, "status": status, **extra}

    checksum = document_checksum(raw)

    # 1 · VALIDATE (capa nativa, sin extraer ni OCR) → decide la ruta de cada página
    yield ev("validate", "Validando páginas", "running")
    report = validate_extraction(raw)
    num_pages = report["num_pages"]
    ocr_idx = sorted(report["ocr_pages"])
    ocr_set = set(ocr_idx)
    text_idx = [i for i in range(num_pages) if i not in ocr_set]
    yield ev("validate", "Validando páginas", "done", doc_verdict=report["doc_verdict"],
             text_pages=len(text_idx), ocr_pages=len(ocr_idx))

    pages: list[dict[str, Any]] = [
        {"text": "", "metadata": {"page": i + 1}} for i in range(num_pages)
    ]

    # 2 · RAMA "NO" · texto nativo → PyMuPDF4LLM solo en esas páginas, SIN su
    #     auto-OCR (en inglés): las escaneadas no pasan por aquí.
    if text_idx:
        label = f"Extrayendo texto nativo (PyMuPDF4LLM · {len(text_idx)} pág.)"
        yield ev("load", label, "running")
        extracted = extract_markdown_pages(raw, filename, pages=text_idx, use_ocr=False)
        for idx, doc in zip(text_idx, extracted):
            pages[idx] = {"text": doc["text"], "metadata": {**doc["metadata"], "page": idx + 1}}
        yield ev("load", label, "done", pages=len(extracted))
    else:
        yield ev("load", "Extracción de texto (sin páginas con texto nativo)", "skipped")

    # 3 · RAMA "SÍ" · escaneadas / ilegibles → OCR con el motor elegido
    if ocr_idx:
        label = f"OCR · {ocr_engine} ({len(ocr_idx)} pág.)"
        yield ev("ocr", label, "running", ocr_engine=ocr_engine)
        ocr_text = ocr_pages(raw, ocr_idx, engine=ocr_engine)
        for idx, txt in ocr_text.items():
            pages[idx] = {"text": txt, "metadata": {"page": idx + 1, "ocr_engine": ocr_engine}}
        yield ev("ocr", label, "done", ocr_engine=ocr_engine, ocr_pages=len(ocr_text))
    else:
        yield ev("ocr", "OCR (no necesario)", "skipped")

    # 4 · NORMALIZE
    yield ev("normalize", "Normalizando texto", "running")
    pages = normalize_documents(pages)
    yield ev("normalize", "Normalizando texto", "done")

    # 5 · BOILERPLATE
    yield ev("boilerplate", "Quitando encabezados/pies", "running")
    bp = remove_boilerplate([p["text"] for p in pages])
    yield ev("boilerplate", "Quitando encabezados/pies", "done", removed=bp["removed_lines"])

    # 6 · CHUNK (estructural sobre el markdown del doc completo)
    yield ev("chunk", "Fragmentando (chunking)", "running")
    full_md = "\n\n".join(bp["pages"])
    chunks = chunk_markdown(full_md, metadata={"source": filename})
    yield ev("chunk", "Fragmentando (chunking)", "done", chunks=len(chunks))

    if not chunks:
        yield ev("index", "Indexando (sin chunks)", "skipped")
        return

    # 7 · EMBED (proveedor resuelto por API key · documentos)
    model_name = EMBEDDERS[embedder]["model"]
    label = f"Generando embeddings ({model_name})"
    yield ev("embed", label, "running")
    vectors = embed_documents(embedder, [c["text"] for c in chunks])
    yield ev("embed", label, "done", embedder=embedder, model=model_name,
             vectors=int(vectors.shape[0]), dim=int(vectors.shape[1]))

    # 8 · INDEX (Qdrant upsert + reporte de ruta)
    yield ev("index", "Indexando en Qdrant", "running")
    dim = int(vectors.shape[1]) if vectors.size else embedding_dimension(embedder)
    qdrant.ensure_collection(client, collection, dim)
    payloads = build_payloads(chunks, source=filename, doc_id=checksum,
                              tenant_id=collection, checksum=checksum)
    qdrant.upsert(client, collection, payloads, vectors)
    route, count, threshold = qdrant.index_route(client, collection)
    yield ev("index", "Indexando en Qdrant", "done",
             index_route=route, num_vectors=count, indexing_threshold=threshold)


# --------------------------------------------------------------------------- #
# Ingesta de un LOTE (1..N documentos)
# --------------------------------------------------------------------------- #
def ingest_documents(
    files: list[tuple[str, bytes]],
    tenant_input: str,
    ocr_engine: str = DEFAULT_OCR_ENGINE,
    embedder: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Ingesta 1..N PDFs a la colección del tenant, emitiendo eventos de progreso.

    files:      [(filename, raw_bytes), ...]. Cada doc que falla NO tumba el lote.
    ocr_engine: motor para las páginas escaneadas (ver stages/b_ocr.py).
    embedder:   clave del catálogo de embeddings, o None para resolverlo por la API
                key disponible (Google u OpenAI). Se resuelve UNA vez para todo el
                lote: mezclar modelos dentro de una colección la haría inconsultable.
    """
    if ocr_engine not in {e["key"] for e in list_ocr_engines()}:
        raise ValueError(f"Motor de OCR desconocido: {ocr_engine}")
    collection = naming.collection_name(tenant_input)  # ValueError si el nombre es inválido
    resolved = resolve_embedder(embedder)               # falla temprano si no hay API key
    dimension = embedding_dimension(resolved)
    client = _qdrant_client()

    # Choque de dimensión ANTES de gastar en OCR/embeddings: si la colección ya
    # existe con otro modelo, ningún documento del lote podría indexarse.
    if client.collection_exists(collection):
        existing = qdrant.collection_dim(client, collection)
        if existing is not None and existing != dimension:
            raise RuntimeError(
                f"La colección '{collection}' ya existe con vectores de {existing} dims, "
                f"pero {EMBEDDERS[resolved]['model']} produce {dimension}. Indexa con el "
                f"mismo modelo con que se creó la colección, o bórrala para re-indexar."
            )

    yield {"event": "start", "collection": collection, "num_docs": len(files),
           "ocr_engine": ocr_engine, "embedder": resolved,
           "model": EMBEDDERS[resolved]["model"], "dimension": dimension}

    for i, (filename, raw) in enumerate(files):
        try:
            yield from _ingest_one(client, collection, i, filename, raw, ocr_engine, resolved)
        except Exception as exc:  # noqa: BLE001  · aislar fallo por documento
            yield {"event": "doc_error", "doc": i, "filename": filename,
                   "error": f"{type(exc).__name__}: {exc}"}

    route, count, threshold = qdrant.index_route(client, collection)
    yield {"event": "done", "collection": collection,
           "index_route": route, "num_vectors": count, "indexing_threshold": threshold}
