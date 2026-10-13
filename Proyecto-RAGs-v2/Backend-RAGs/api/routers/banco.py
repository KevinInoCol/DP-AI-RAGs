"""
Banco de pruebas: las pestañas que COMPARAN técnicas de cada componente de un RAG
(Document Loaders, Text Splitters, Embeddings, Vector Store). No escriben en la
base de conocimiento: eso es la ingesta (ingesta.py).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.schemas import BenchmarkRequest, EmbedRequest, IndexRequest, SearchRequest, SplitRequest
from componentes.embeddings import VectorIndex, build_index, embed_texts, list_embedders
from componentes.loaders import list_loaders, load_document
from componentes.splitters import list_frameworks, list_splitters, split_text
from componentes.vectorstores import benchmark as vs_benchmark
from componentes.vectorstores import list_stores

router = APIRouter(tags=["banco de pruebas"])

# Índice vectorial "actual" en memoria (testbed de un solo usuario). Lo construye
# POST /index y lo consulta POST /search.
_INDEX: VectorIndex | None = None


# --------------------------------------------------------------------------- #
# Text Splitters
# --------------------------------------------------------------------------- #
@router.get("/splitters")
def get_splitters() -> dict[str, Any]:
    """Catálogo de splitters para construir el menú del frontend.

    Cada técnica trae `framework` ("llamaindex" | "langchain"); `frameworks` da
    el orden de los grupos en la UI.
    """
    return {"frameworks": list_frameworks(), "splitters": list_splitters()}


@router.post("/split")
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


# --------------------------------------------------------------------------- #
# Document Loaders
# --------------------------------------------------------------------------- #
@router.get("/loaders")
def get_loaders() -> dict[str, Any]:
    """Catálogo de Document Loaders (ordenado de peor a mejor)."""
    return {"loaders": list_loaders()}


@router.post("/load")
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


# --------------------------------------------------------------------------- #
# Embeddings (índice en memoria)
# --------------------------------------------------------------------------- #
@router.get("/embedders")
def get_embedders() -> dict[str, Any]:
    """Catálogo de modelos de embedding (etapa de indexación)."""
    return {"embedders": list_embedders()}


@router.post("/embed")
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


@router.post("/index")
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


@router.post("/search")
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


# --------------------------------------------------------------------------- #
# Vector Store (fuerza bruta vs. HNSW)
# --------------------------------------------------------------------------- #
@router.get("/vectorstores")
def get_vectorstores() -> dict[str, Any]:
    """Catálogo de motores de índice vectorial (fuerza bruta vs. ANN)."""
    return {"vectorstores": list_stores()}


@router.post("/vectorstores/benchmark")
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
