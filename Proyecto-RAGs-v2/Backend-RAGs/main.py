"""
API FastAPI del banco de pruebas RAG (loaders, splitters, embeddings, vector
stores) y del pipeline de ingesta a Qdrant.

Endpoints principales:
  GET  /splitters        -> catálogo de técnicas, agrupadas por framework (LlamaIndex / LangChain)
  POST /split            -> divide un texto con el splitter elegido
  GET  /loaders          -> catálogo de Document Loaders (incluye los 4 tiers de LlamaParse)
  GET  /ocr-engines      -> motores de OCR elegibles para la ingesta
  GET  /pipeline         -> descripción del flujo de ingesta y sus opciones
  GET  /embedders        -> modelos de embedding (Google u OpenAI) y cuál está disponible
  POST /ingest           -> ingesta de PDFs (SSE), con `ocr_engine` y `embedder` opcionales
  POST /extract          -> extrae texto plano de un archivo subido (.txt/.md/.pdf/...)
  GET  /health           -> estado del servicio y API keys de embeddings cargadas

Ejecutar:
  uvicorn main:app --reload --port 8005
"""

from __future__ import annotations

import io
import json
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from embeddings import (
    VectorIndex,
    available_embedders,
    build_index,
    default_embedder,
    embed_texts,
    list_embedders,
)
from loaders import list_loaders, load_document
from pipeline.flow import describe_pipeline
from pipeline.orchestrator import ingest_documents
from pipeline.sink.naming import is_valid_tenant_input
from pipeline.stages.b_ocr import DEFAULT_OCR_ENGINE, list_ocr_engines
from splitters import list_frameworks, list_splitters, split_text
from vectorstores import benchmark as vs_benchmark
from vectorstores import list_stores

load_dotenv()

app = FastAPI(title="RAG Toolkit · Testbed e ingesta", version="1.1.0")

# CORS abierto para desarrollo (frontend en Vite: 5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SplitRequest(BaseModel):
    splitter: str
    text: str
    params: dict[str, Any] = {}


# En los requests, `embedder=None` significa "resuélvelo tú por la API key
# disponible" (Google u OpenAI). Ver embeddings.resolve_embedder.
class EmbedRequest(BaseModel):
    embedder: str | None = None
    texts: list[str]
    params: dict[str, Any] = {}


class IndexRequest(BaseModel):
    embedder: str | None = None
    chunks: list[str]
    params: dict[str, Any] = {}


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class GcsIngestRequest(BaseModel):
    tenant: str
    bucket: str
    prefix: str = ""
    ocr_engine: str = DEFAULT_OCR_ENGINE
    embedder: str | None = None


class BenchmarkRequest(BaseModel):
    embedder: str | None = None
    embed_params: dict[str, Any] = {}
    chunks: list[str]
    queries: list[str]
    top_k: int = 5
    synthetic_scale: int = 5000
    store_params: dict[str, Any] = {}


# Índice vectorial "actual" en memoria (testbed de un solo usuario). Lo construye
# POST /index y lo consulta POST /search.
_INDEX: VectorIndex | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    """Estado del servicio + qué proveedores de embeddings están usables ahora."""
    return {
        "status": "ok",
        "google_key_loaded": bool(os.getenv("GOOGLE_API_KEY")),
        "openai_key_loaded": bool(os.getenv("OPENAI_API_KEY")),
        "embedders_available": available_embedders(),
        "embedder_default": default_embedder(),
    }


@app.get("/splitters")
def get_splitters() -> dict[str, Any]:
    """Catálogo de splitters para construir el menú del frontend.

    Cada técnica trae `framework` ("llamaindex" | "langchain"); `frameworks` da
    el orden de los grupos en la UI.
    """
    return {"frameworks": list_frameworks(), "splitters": list_splitters()}


@app.post("/split")
def post_split(req: SplitRequest) -> dict[str, Any]:
    """Aplica un splitter a un texto y devuelve los chunks + estadísticas."""
    try:
        chunks = split_text(req.splitter, req.text, req.params)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:  # p.ej. falta la API key de embeddings
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error al dividir: {exc}") from exc

    total_tokens = sum(c["token_count"] for c in chunks)
    total_chars = sum(c["char_count"] for c in chunks)
    return {
        "splitter": req.splitter,
        "num_chunks": len(chunks),
        "stats": {
            "total_chunks": len(chunks),
            "total_tokens": total_tokens,
            "total_chars": total_chars,
            "avg_tokens": round(total_tokens / len(chunks), 1) if chunks else 0,
            "avg_chars": round(total_chars / len(chunks), 1) if chunks else 0,
        },
        "chunks": chunks,
    }


@app.get("/loaders")
def get_loaders() -> dict[str, Any]:
    """Catálogo de Document Loaders (ordenado de peor a mejor)."""
    return {"loaders": list_loaders()}


@app.post("/load")
async def post_load(
    loader: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Extrae el texto de un archivo con el Document Loader elegido."""
    raw = await file.read()
    try:
        documents = load_document(loader, raw, file.filename or "")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:  # p.ej. falta LLAMA_CLOUD_API_KEY
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error al cargar: {exc}") from exc

    total_chars = sum(len(d["text"]) for d in documents)
    return {
        "loader": loader,
        "filename": file.filename,
        "num_documents": len(documents),
        "stats": {
            "total_documents": len(documents),
            "total_chars": total_chars,
            "avg_chars": round(total_chars / len(documents), 1) if documents else 0,
        },
        "documents": documents,
    }


@app.get("/ocr-engines")
def get_ocr_engines() -> dict[str, Any]:
    """Motores de OCR para las páginas escaneadas (del más barato al más caro)."""
    return {"ocr_engines": list_ocr_engines()}


@app.get("/pipeline")
def get_pipeline() -> dict[str, Any]:
    """Flujo de ingesta de arriba hacia abajo, con las opciones de cada etapa."""
    return describe_pipeline()


def _validate_ocr_engine(engine: str) -> None:
    if engine not in {e["key"] for e in list_ocr_engines()}:
        raise HTTPException(status_code=400, detail=f"Motor de OCR desconocido: {engine}")


@app.get("/embedders")
def get_embedders() -> dict[str, Any]:
    """Catálogo de modelos de embedding (etapa de indexación)."""
    return {"embedders": list_embedders()}


@app.post("/embed")
def post_embed(req: EmbedRequest) -> dict[str, Any]:
    """Embebe una lista de textos y devuelve stats + preview de cada vector."""
    try:
        return embed_texts(req.embedder, req.texts, req.params)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:  # p.ej. falta GOOGLE_API_KEY / OPENAI_API_KEY
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error al embeber: {exc}") from exc


@app.post("/index")
def post_index(req: IndexRequest) -> dict[str, Any]:
    """Indexa una lista de chunks (los embebe como documentos) y guarda el índice."""
    global _INDEX
    chunks = [{"text": t, "metadata": {"chunk": i + 1}} for i, t in enumerate(req.chunks) if t.strip()]
    if not chunks:
        raise HTTPException(status_code=400, detail="No hay chunks con texto para indexar.")
    try:
        _INDEX = build_index(req.embedder, chunks, req.params)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error al indexar: {exc}") from exc

    dim = int(_INDEX.vectors.shape[1]) if _INDEX.vectors.size else 0
    # _INDEX.key es el embedder YA resuelto (puede diferir de req.embedder si vino None).
    return {"embedder": _INDEX.key, "num_chunks": len(chunks), "dimension": dim}


@app.post("/search")
def post_search(req: SearchRequest) -> dict[str, Any]:
    """Consulta el índice actual con una query y devuelve los top_k chunks."""
    if _INDEX is None:
        raise HTTPException(status_code=400, detail="No hay índice. Indexa un documento primero.")
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="La consulta está vacía.")
    try:
        results = _INDEX.search(req.query, top_k=req.top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error al buscar: {exc}") from exc
    return {"query": req.query, "num_results": len(results), "results": results}


@app.get("/vectorstores")
def get_vectorstores() -> dict[str, Any]:
    """Catálogo de motores de índice vectorial (fuerza bruta vs. ANN)."""
    return {"vectorstores": list_stores()}


@app.post("/vectorstores/benchmark")
def post_vectorstores_benchmark(req: BenchmarkRequest) -> dict[str, Any]:
    """Compara los motores: build_ms, avg_search_ms y recall@k vs. el exacto."""
    try:
        return vs_benchmark(
            embedder=req.embedder,
            embed_params=req.embed_params,
            chunks=req.chunks,
            queries=req.queries,
            top_k=req.top_k,
            synthetic_scale=req.synthetic_scale,
            store_params=req.store_params,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:  # entrada inválida o falta API key
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error en el benchmark: {exc}") from exc


@app.post("/ingest")
async def post_ingest(
    tenant: str = Form(...),
    files: list[UploadFile] = File(...),
    ocr_engine: str = Form(DEFAULT_OCR_ENGINE),
    embedder: str | None = Form(None),
):
    """Ingesta 1..N PDFs a la colección del tenant y TRANSMITE (SSE) el progreso
    paso a paso (loader → validar → OCR → normalizar → boilerplate → chunk →
    embeddings → indexar), incluida la ruta de indexación (fuerza bruta vs HNSW).
    `ocr_engine` elige el motor para las páginas escaneadas (ver GET /ocr-engines).
    `embedder` elige el modelo de embeddings (ver GET /embedders); si no se manda,
    se usa el que haya según la API key disponible (Google u OpenAI)."""
    _validate_ocr_engine(ocr_engine)
    if not is_valid_tenant_input(tenant):
        raise HTTPException(
            status_code=400,
            detail="Nombre de tenant inválido (usa al menos 2 letras o números).",
        )
    docs: list[tuple[str, bytes]] = []
    for f in files:
        docs.append((f.filename or "documento.pdf", await f.read()))
    if not docs:
        raise HTTPException(status_code=400, detail="No se subió ningún archivo.")

    def stream():
        try:
            for evt in ingest_documents(docs, tenant, ocr_engine=ocr_engine, embedder=embedder or None):
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            err = {"event": "error", "error": f"{type(exc).__name__}: {exc}"}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/ingest/gcs")
def post_ingest_gcs(req: GcsIngestRequest):
    """Ingesta los PDFs de un bucket de GCS (bucket + prefijo) y transmite (SSE) el
    mismo progreso que /ingest. Descarga desde GCS y reutiliza el orquestador."""
    _validate_ocr_engine(req.ocr_engine)
    if not is_valid_tenant_input(req.tenant):
        raise HTTPException(
            status_code=400,
            detail="Nombre de tenant inválido (usa al menos 2 letras o números).",
        )
    if not req.bucket.strip():
        raise HTTPException(status_code=400, detail="Falta el nombre del bucket.")

    def sse(evt: dict[str, Any]) -> str:
        return f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

    def stream():
        try:
            from pipeline.sources.gcs import download, list_pdfs

            blobs = list_pdfs(req.bucket.strip(), req.prefix.strip())
            if not blobs:
                yield sse({"event": "error", "error": "No se encontraron PDFs en ese bucket/prefijo."})
                return
            # nombre corto (sin el path del prefijo) para mostrar/metadata
            docs = [(b["name"].split("/")[-1], download(req.bucket.strip(), b["name"])) for b in blobs]
            for evt in ingest_documents(
                docs, req.tenant, ocr_engine=req.ocr_engine, embedder=req.embedder
            ):
                yield sse(evt)
        except Exception as exc:  # noqa: BLE001
            yield sse({"event": "error", "error": f"{type(exc).__name__}: {exc}"})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/extract")
async def post_extract(file: UploadFile = File(...)) -> dict[str, Any]:
    """Extrae texto plano de un archivo subido (.txt, .md, .pdf, código, etc.)."""
    raw = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"No se pudo leer el PDF: {exc}") from exc
    else:
        # Texto / markdown / código: decodificar como UTF-8 (con fallback).
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")

    return {"filename": file.filename, "chars": len(text), "text": text}
