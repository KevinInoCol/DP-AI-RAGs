"""
Pipeline de ingesta RAG · ORQUESTADOR
Ruta: Backend-RAGs/pipeline/orquestador.py

El pegamento: encadena las etapas de pipeline/etapas/ en el MISMO orden y con los
MISMOS números que la pestaña "Pipeline de ingesta" (pipeline/flujo.py):

  01 fuente (api/routers/ingesta.py · fuentes/) → 02 validación
  → 03 loader | 03 OCR → 04 normalización → 05 limpieza → 06 chunking
  → 07 metadata → 08 embeddings → 09 indexado (Qdrant)

Aquí no hay lógica de negocio: solo el orden, el aislamiento de errores por
documento y los eventos de progreso (generator) para que el frontend muestre cada
paso y la ruta de indexación elegida.

Eventos que emite (dicts):
  {"event":"start", "collection", "num_docs", "loader", "ocr_engine", "splitter", "embedder", "model", "dimension"}
  {"event":"step", "doc", "filename", "step", "label", "status", ...extra}
     step ∈ validate|load|ocr|normalize|boilerplate|chunk|embed|index  (en ese orden)
     status ∈ running|done|skipped|error
     el step "embed" (done) trae: embedder ("gemini"|"openai"), model, vectors, dim
     el step "index" (done) trae lo que reporta Qdrant (etapas/e09_indexado.index_route):
       index_route ("brute_force"|"mixed"|"hnsw"), num_vectors, indexed_vectors, segments,
       optimizing, indexing_threshold (KB por segmento), vectors_threshold
  {"event":"doc_error", "doc", "filename", "error"}
  {"event":"done", "collection", ...los mismos campos de index_route}

El PROVEEDOR DE EMBEDDINGS se resuelve una sola vez por lote (Google u OpenAI,
según qué API key haya; ver etapas/e08_embeddings.py) y se reporta en el evento
"start": una colección debe tener todos sus vectores del MISMO modelo/dimensión.

El LOADER y el SPLITTER son opcionales: por defecto PyMuPDF4LLM (ver
etapas/e03_loader.py) y el chunking estructural (ver etapas/e06_chunking.py).
"""

from __future__ import annotations

from typing import Any, Iterator

from componentes.loaders import LOADERS
from componentes.vectorstores import qdrant_client

from . import naming
from .etapas import e09_indexado
from .etapas.e02_validacion import validate_extraction
from .etapas.e03_loader import INGEST_LOADER, extract_text_pages, is_valid_loader
from .etapas.e03_ocr import DEFAULT_OCR_ENGINE, list_ocr_engines, ocr_pages
from .etapas.e04_normalizacion import normalize_documents
from .etapas.e05_limpieza import remove_boilerplate
from .etapas.e06_chunking import INGEST_SPLITTER, chunk_document, is_valid_splitter
from .etapas.e07_metadata import build_payloads, document_checksum
from .etapas.e08_embeddings import embed_chunks, resolve_model


# --------------------------------------------------------------------------- #
# Ingesta de UN documento (generator de eventos)
# --------------------------------------------------------------------------- #
def _ingest_one(
    client, collection: str, doc_i: int, filename: str, raw: bytes, loader: str,
    ocr_engine: str, model: dict[str, Any], splitter: str,
) -> Iterator[dict[str, Any]]:
    def ev(step: str, label: str, status: str, **extra: Any) -> dict[str, Any]:
        return {"event": "step", "doc": doc_i, "filename": filename,
                "step": step, "label": label, "status": status, **extra}

    checksum = document_checksum(raw)

    # 02 · VALIDACIÓN (capa nativa, sin extraer ni OCR) → decide la ruta de cada página
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

    # 03 · RAMA "NO" · texto nativo → loader elegido solo en esas páginas
    if text_idx:
        label = f"Extrayendo texto nativo ({LOADERS[loader]['name']} · {len(text_idx)} pág.)"
        yield ev("load", label, "running", loader=loader)
        extracted = extract_text_pages(raw, filename, text_idx, loader)
        for idx, doc in zip(text_idx, extracted):
            pages[idx] = {"text": doc["text"], "metadata": {**doc["metadata"], "page": idx + 1}}
        yield ev("load", label, "done", pages=len(extracted))
    else:
        yield ev("load", "Extracción de texto (sin páginas con texto nativo)", "skipped")

    # 03 · RAMA "SÍ" · escaneadas / ilegibles → OCR con el motor elegido
    if ocr_idx:
        label = f"OCR · {ocr_engine} ({len(ocr_idx)} pág.)"
        yield ev("ocr", label, "running", ocr_engine=ocr_engine)
        ocr_text = ocr_pages(raw, ocr_idx, engine=ocr_engine)
        for idx, txt in ocr_text.items():
            pages[idx] = {"text": txt, "metadata": {"page": idx + 1, "ocr_engine": ocr_engine}}
        yield ev("ocr", label, "done", ocr_engine=ocr_engine, ocr_pages=len(ocr_text))
    else:
        yield ev("ocr", "OCR (no necesario)", "skipped")

    # 04 · NORMALIZACIÓN
    yield ev("normalize", "Normalizando texto", "running")
    pages = normalize_documents(pages)
    yield ev("normalize", "Normalizando texto", "done")

    # 05 · LIMPIEZA de encabezados y pies
    yield ev("boilerplate", "Quitando encabezados/pies", "running")
    bp = remove_boilerplate([p["text"] for p in pages])
    yield ev("boilerplate", "Quitando encabezados/pies", "done", removed=bp["removed_lines"])

    # 06 · CHUNKING (sobre el markdown del doc completo)
    yield ev("chunk", "Fragmentando (chunking)", "running", splitter=splitter)
    chunks = chunk_document("\n\n".join(bp["pages"]), splitter, filename)
    yield ev("chunk", "Fragmentando (chunking)", "done", splitter=splitter, chunks=len(chunks))

    if not chunks:
        yield ev("index", "Indexando (sin chunks)", "skipped")
        return

    # 07 · METADATA: payloads con IDs deterministas (idempotencia)
    payloads = build_payloads(chunks, source=filename, doc_id=checksum,
                              tenant_id=collection, checksum=checksum)

    # 08 · EMBEDDINGS (proveedor ya resuelto para todo el lote)
    label = f"Generando embeddings ({model['model']})"
    yield ev("embed", label, "running")
    vectors = embed_chunks(model["embedder"], chunks)
    yield ev("embed", label, "done", embedder=model["embedder"], model=model["model"],
             vectors=int(vectors.shape[0]), dim=int(vectors.shape[1]))

    # 09 · INDEXADO (Qdrant upsert + reporte de ruta)
    yield ev("index", "Indexando en Qdrant", "running")
    dim = int(vectors.shape[1]) if vectors.size else model["dimension"]
    e09_indexado.ensure_collection(client, collection, dim)
    e09_indexado.upsert(client, collection, payloads, vectors)
    yield ev("index", "Indexando en Qdrant", "done", **e09_indexado.index_route(client, collection))


# --------------------------------------------------------------------------- #
# Ingesta de un LOTE (1..N documentos)
# --------------------------------------------------------------------------- #
def ingest_documents(
    files: list[tuple[str, bytes]],
    tenant_input: str,
    ocr_engine: str = DEFAULT_OCR_ENGINE,
    embedder: str | None = None,
    splitter: str | None = None,
    loader: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Ingesta 1..N PDFs a la colección del tenant, emitiendo eventos de progreso.

    files:      [(filename, raw_bytes), ...]. Cada doc que falla NO tumba el lote.
    ocr_engine: motor para las páginas escaneadas (ver etapas/e03_ocr.py).
    embedder:   clave del catálogo de embeddings, o None para resolverlo por la API
                key disponible (Google u OpenAI). Se resuelve UNA vez para todo el
                lote: mezclar modelos dentro de una colección la haría inconsultable.
    splitter:   clave del catálogo de splitters, o None para el chunking estructural.
    loader:     clave del catálogo de loaders para el texto nativo, o None para
                PyMuPDF4LLM. Solo los de un documento por página (e03_loader.py).
    """
    if ocr_engine not in {e["key"] for e in list_ocr_engines()}:
        raise ValueError(f"Motor de OCR desconocido: {ocr_engine}")
    loader = loader or INGEST_LOADER
    if not is_valid_loader(loader):
        raise ValueError(f"Loader desconocido o no apto para la ingesta: {loader}")
    splitter = splitter or INGEST_SPLITTER
    if not is_valid_splitter(splitter):
        raise ValueError(f"Splitter desconocido o no apto para la ingesta: {splitter}")
    collection = naming.collection_name(tenant_input)  # ValueError si el nombre es inválido
    model = resolve_model(embedder)                     # falla temprano si no hay API key
    client = qdrant_client()

    # Choque de dimensión ANTES de gastar en OCR/embeddings: si la colección ya
    # existe con otro modelo, ningún documento del lote podría indexarse.
    e09_indexado.check_dimension(client, collection, model["dimension"], model["model"])

    yield {"event": "start", "collection": collection, "num_docs": len(files),
           "loader": loader, "ocr_engine": ocr_engine, "splitter": splitter, **model}

    for i, (filename, raw) in enumerate(files):
        try:
            yield from _ingest_one(
                client, collection, i, filename, raw, loader, ocr_engine, model, splitter
            )
        except Exception as exc:  # noqa: BLE001  · aislar fallo por documento
            yield {"event": "doc_error", "doc": i, "filename": filename,
                   "error": f"{type(exc).__name__}: {exc}"}

    yield {"event": "done", "collection": collection, **e09_indexado.index_route(client, collection)}
