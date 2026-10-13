"""
Pipeline de ingesta RAG · 08 · EMBEDDINGS de los chunks
Ruta: Backend-RAGs/pipeline/etapas/e08_embeddings.py

Convierte cada chunk en un vector con el proveedor elegido (Google u OpenAI). El
proveedor se resuelve UNA vez por lote, antes de procesar ningún documento: una
colección debe tener todos sus vectores del MISMO modelo y dimensión.

Los modelos, precios y la resolución por API key viven en componentes/embeddings.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from componentes.embeddings import EMBEDDERS, embed_documents, embedding_dimension, resolve_embedder


def resolve_model(embedder: str | None) -> dict[str, Any]:
    """Proveedor elegido (o el de la API key disponible si es None), con su modelo y
    dimensión. Falla temprano con un error claro si falta la API key."""
    key = resolve_embedder(embedder)
    return {"embedder": key, "model": EMBEDDERS[key]["model"], "dimension": embedding_dimension(key)}


def embed_chunks(embedder: str, chunks: list[dict[str, Any]]) -> np.ndarray:
    """Vectores (L2-normalizados) de los chunks, embebidos como DOCUMENTOS."""
    return embed_documents(embedder, [c["text"] for c in chunks])
