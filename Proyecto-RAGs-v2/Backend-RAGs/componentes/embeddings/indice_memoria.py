"""
Índice vectorial EN MEMORIA (coseno) para la pestaña Embeddings del banco.

Indexa los chunks (task_type de documento) y consulta con una pregunta (task_type
de query): demuestra retrieval real sin levantar infraestructura. La ingesta NO lo
usa: indexa en Qdrant (pipeline/etapas/e09_indexado.py).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .proveedores import embed_vectors, resolve_embedder


class VectorIndex:
    """Índice coseno en memoria. Suficiente para el testbed; en producción esto
    sería Qdrant / pgvector, pero la interfaz (build/search) es la misma.

    El embedder se RESUELVE al construir y se guarda: así la query se embebe con
    el MISMO modelo y dimensión que los documentos (si no, el coseno no significa
    nada)."""

    def __init__(self, key: str | None, params: dict[str, Any]):
        self.key = resolve_embedder(key)
        self.params = params or {}
        self.vectors: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self.chunks: list[dict[str, Any]] = []

    def build(self, chunks: list[dict[str, Any]]) -> None:
        """chunks: [{text, metadata?}]. Los embebe como DOCUMENTOS y los guarda."""
        texts = [c["text"] for c in chunks]
        self.vectors = embed_vectors(self.key, texts, self.params, is_query=False)
        self.chunks = chunks

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Embebe la query (task_type de QUERY) y devuelve los top_k por coseno.

        Como todos los vectores están L2-normalizados, el coseno es el producto
        punto: una sola multiplicación matricial.
        """
        if not self.chunks:
            return []
        q = embed_vectors(self.key, [query], self.params, is_query=True)[0]
        scores = self.vectors @ q  # (N,) — coseno porque están normalizados
        top = np.argsort(-scores)[: max(1, top_k)]
        return [
            {
                "rank": rank + 1,
                "score": round(float(scores[i]), 4),
                "index": int(i),
                "text": self.chunks[int(i)]["text"],
                "metadata": self.chunks[int(i)].get("metadata", {}),
            }
            for rank, i in enumerate(top)
        ]


def build_index(key: str | None, chunks: list[dict[str, Any]], params: dict[str, Any] | None = None) -> VectorIndex:
    """Atajo: crea un VectorIndex y lo llena con los chunks dados."""
    index = VectorIndex(key, params or {})
    index.build(chunks)
    return index
