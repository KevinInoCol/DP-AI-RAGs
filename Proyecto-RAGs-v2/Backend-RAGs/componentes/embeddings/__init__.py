"""
Embeddings: convierten texto en vectores (Google u OpenAI, vía LlamaIndex).

  proveedores.py     · catálogo, resolución por API key y funciones de embedding
  indice_memoria.py  · índice coseno en memoria, solo para la pestaña Embeddings
"""

from .indice_memoria import VectorIndex, build_index
from .proveedores import (
    EMBEDDERS,
    PROVIDER_PRIORITY,
    available_embedders,
    default_embedder,
    embed_documents,
    embed_query,
    embed_texts,
    embedding_dimension,
    has_api_key,
    list_embedders,
    llama_embed_model,
    resolve_embedder,
)

__all__ = [
    "EMBEDDERS",
    "PROVIDER_PRIORITY",
    "VectorIndex",
    "available_embedders",
    "build_index",
    "default_embedder",
    "embed_documents",
    "embed_query",
    "embed_texts",
    "embedding_dimension",
    "has_api_key",
    "list_embedders",
    "llama_embed_model",
    "resolve_embedder",
]
