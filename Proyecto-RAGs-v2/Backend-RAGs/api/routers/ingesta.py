"""
Ingesta REAL a Qdrant (etapa 01 del pipeline: de dónde llegan los PDFs).

  POST /ingest               · PDFs subidos desde el navegador (multipart)
  GET  /gcs/pdfs             · lista los PDFs de un bucket de GCS antes de ingestar
  POST /ingest/gcs           · PDFs de un bucket de GCS (bucket + prefijo)
  GET  /collections          · colecciones de tenants que ya existen en Qdrant
  GET  /collections/preview  · nombre final de la colección para un tenant (etapa 09)

Las dos ingestas validan la entrada ANTES de abrir el stream (error 400 claro) y
luego transmiten por SSE los eventos del orquestador (pipeline/orquestador.py).
"""

from __future__ import annotations

import json
from typing import Any, Iterator

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from api.schemas import GcsIngestRequest
from componentes.embeddings import EMBEDDERS, embedding_dimension
from componentes.vectorstores import qdrant_client
from pipeline.etapas.e03_loader import is_valid_loader
from pipeline.etapas.e03_ocr import DEFAULT_OCR_ENGINE, list_ocr_engines
from pipeline.etapas.e06_chunking import is_valid_splitter
from pipeline.fuentes import gcs
from pipeline.etapas.e09_indexado import collection_dim
from pipeline.naming import COLLECTION_PREFIX, collection_name, is_valid_tenant_input
from pipeline.orquestador import ingest_documents

router = APIRouter(tags=["ingesta"])


def _validate_ocr_engine(engine: str) -> None:
    if engine not in {e["key"] for e in list_ocr_engines()}:
        raise HTTPException(status_code=400, detail=f"Motor de OCR desconocido: {engine}")


def _validate_splitter(splitter: str | None) -> None:
    if splitter and not is_valid_splitter(splitter):
        raise HTTPException(status_code=400, detail=f"Splitter desconocido o no apto para la ingesta: {splitter}")


def _validate_loader(loader: str | None) -> None:
    if loader and not is_valid_loader(loader):
        raise HTTPException(status_code=400, detail=f"Loader desconocido o no apto para la ingesta: {loader}")


def _validate_tenant(tenant: str) -> None:
    if not is_valid_tenant_input(tenant):
        raise HTTPException(
            status_code=400,
            detail="Nombre de tenant inválido (usa al menos 2 letras o números).",
        )


def _clean_bucket(bucket: str) -> str:
    """Nombre del bucket sin `gs://` ni barras; 400 si queda vacío."""
    bucket = bucket.strip().removeprefix("gs://").strip("/")
    if not bucket:
        raise HTTPException(status_code=400, detail="Falta el nombre del bucket.")
    return bucket


def _sse(evt: dict[str, Any]) -> str:
    return f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"


def _collection_stats(client, name: str) -> dict[str, Any]:
    info = client.get_collection(name)
    return {"num_vectors": int(info.points_count or 0), "dimension": collection_dim(client, name)}


@router.get("/collections")
def get_collections() -> dict[str, Any]:
    """Colecciones de tenants (prefijo tenant_id_) que ya existen en Qdrant, para
    poder reutilizarlas. Si Qdrant no está configurado, devuelve la lista vacía con
    el motivo, sin fallar: la UI sigue funcionando."""
    try:
        client = qdrant_client()
        names = sorted(c.name for c in client.get_collections().collections
                       if c.name.startswith(COLLECTION_PREFIX))
        items = [{"collection": n, "tenant": n[len(COLLECTION_PREFIX):], **_collection_stats(client, n)}
                 for n in names]
    except Exception as exc:  # noqa: BLE001 · sin QDRANT_URL, servidor caído…
        return {"prefix": COLLECTION_PREFIX, "collections": [], "error": str(exc)}
    return {"prefix": COLLECTION_PREFIX, "collections": items, "error": None}


@router.get("/collections/preview")
def get_collection_preview(tenant: str = "", embedder: str | None = None) -> dict[str, Any]:
    """Nombre FINAL de la colección para lo que escribe el usuario (mismas reglas que
    la ingesta, pipeline/naming.py) y si ya existe en Qdrant (los PDFs se AÑADEN).

    Con `embedder`, avisa ANTES de ingestar si la colección existente tiene otra
    dimensión: la ingesta fallaría (no se mezclan modelos en una colección)."""
    try:
        name = collection_name(tenant)
    except ValueError as exc:
        return {"valid": False, "collection": None, "error": str(exc), "exists": None}
    out: dict[str, Any] = {"valid": True, "collection": name, "error": None, "exists": None}
    try:
        client = qdrant_client()
        out["exists"] = client.collection_exists(name)
        if out["exists"]:
            out.update(_collection_stats(client, name))
            if embedder in EMBEDDERS and out["dimension"]:
                expected = embedding_dimension(embedder)
                if expected != out["dimension"]:
                    out["dimension_error"] = (
                        f"Esta colección tiene vectores de {out['dimension']} dims y "
                        f"{EMBEDDERS[embedder]['model']} produce {expected}: la ingesta "
                        f"fallaría. Usa otro nombre o el mismo modelo con que se creó."
                    )
    except Exception:  # noqa: BLE001 · sin Qdrant no sabemos si existe; el nombre vale igual
        pass
    return out


@router.post("/ingest")
async def post_ingest(
    tenant: str = Form(...),
    files: list[UploadFile] = File(...),
    ocr_engine: str = Form(DEFAULT_OCR_ENGINE),
    embedder: str | None = Form(None),
    splitter: str | None = Form(None),
    loader: str | None = Form(None),
):
    """Ingesta 1..N PDFs a la colección del tenant y TRANSMITE (SSE) el progreso
    paso a paso (loader → validar → OCR → normalizar → boilerplate → chunk →
    embeddings → indexar), incluida la ruta de indexación (fuerza bruta vs HNSW).
    `ocr_engine` elige el motor para las páginas escaneadas (ver GET /ocr-engines).
    `embedder` elige el modelo de embeddings (ver GET /embedders); si no se manda,
    se usa el que haya según la API key disponible (Google u OpenAI).
    `splitter` elige la técnica de chunking (ver GET /splitters); si no se manda,
    se usa el chunking estructural por secciones de Markdown.
    `loader` elige el loader del texto nativo (ver GET /loaders); si no se manda,
    se usa PyMuPDF4LLM. Solo valen los que devuelven un documento por página."""
    _validate_ocr_engine(ocr_engine)
    _validate_splitter(splitter)
    _validate_loader(loader)
    _validate_tenant(tenant)
    docs: list[tuple[str, bytes]] = []
    for f in files:
        docs.append((f.filename or "documento.pdf", await f.read()))
    if not docs:
        raise HTTPException(status_code=400, detail="No se subió ningún archivo.")

    def stream() -> Iterator[str]:
        try:
            for evt in ingest_documents(
                docs, tenant, ocr_engine=ocr_engine, embedder=embedder or None,
                splitter=splitter or None, loader=loader or None,
            ):
                yield _sse(evt)
        except Exception as exc:  # noqa: BLE001
            yield _sse({"event": "error", "error": f"{type(exc).__name__}: {exc}"})

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/gcs/pdfs")
def get_gcs_pdfs(bucket: str, prefix: str = "") -> dict[str, Any]:
    """Lista los PDFs de un bucket (para revisar qué se va a ingestar)."""
    bucket = _clean_bucket(bucket)
    try:
        pdfs = gcs.list_pdfs(bucket, prefix.strip())
    except RuntimeError as exc:  # falta la librería o las credenciales
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 · permiso, bucket inexistente…
        raise HTTPException(status_code=400, detail=gcs.explain_error(exc, bucket)) from exc
    return {"bucket": bucket, "prefix": prefix.strip(), "pdfs": pdfs}


@router.post("/ingest/gcs")
def post_ingest_gcs(req: GcsIngestRequest):
    """Ingesta los PDFs de un bucket de GCS (bucket + prefijo) y transmite (SSE) el
    mismo progreso que /ingest. Descarga desde GCS y reutiliza el orquestador."""
    _validate_ocr_engine(req.ocr_engine)
    _validate_splitter(req.splitter)
    _validate_loader(req.loader)
    _validate_tenant(req.tenant)
    bucket = _clean_bucket(req.bucket)

    def stream() -> Iterator[str]:
        try:
            try:
                blobs = gcs.list_pdfs(bucket, req.prefix.strip())
                if not blobs:
                    yield _sse({"event": "error", "error": "No se encontraron PDFs en ese bucket/prefijo."})
                    return
                # Aviso antes de descargar: con muchos PDFs la descarga tarda.
                yield _sse({"event": "source", "bucket": bucket, "num_files": len(blobs)})
                # nombre corto (sin el path del prefijo) para mostrar/metadata
                docs = [(b["name"].split("/")[-1], gcs.download(bucket, b["name"])) for b in blobs]
            except RuntimeError:
                raise
            except Exception as exc:  # noqa: BLE001
                yield _sse({"event": "error", "error": gcs.explain_error(exc, bucket)})
                return
            for evt in ingest_documents(
                docs, req.tenant, ocr_engine=req.ocr_engine, embedder=req.embedder,
                splitter=req.splitter, loader=req.loader,
            ):
                yield _sse(evt)
        except Exception as exc:  # noqa: BLE001
            yield _sse({"event": "error", "error": f"{type(exc).__name__}: {exc}"})

    return StreamingResponse(stream(), media_type="text/event-stream")
