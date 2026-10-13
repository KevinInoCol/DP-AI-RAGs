"""
Pipeline de ingesta RAG · SINK Qdrant (escritura de la colección del tenant)
Ruta: Backend-RAGs/pipeline/sink/qdrant.py

Distinto del benchmark de vectorstores.py: aquí solo se CREA la colección, se
hace upsert idempotente y se LEE la ruta de indexación que eligió Qdrant.

La ruta la decide Qdrant por su `indexing_threshold` (default 20000): por debajo
→ full scan (fuerza bruta); por encima → HNSW. Aquí solo la leemos y reportamos.
"""

from __future__ import annotations

from typing import Any

DEFAULT_INDEXING_THRESHOLD = 20000  # default de Qdrant (por debajo = fuerza bruta)
UPSERT_BATCH_SIZE = 256


def collection_dim(client, name: str) -> int | None:
    """Dimensión de los vectores con que se creó la colección (None si no se puede leer)."""
    try:
        params = client.get_collection(name).config.params.vectors
        # Vectores sin nombre -> VectorParams. Con nombre -> {nombre: VectorParams}.
        if isinstance(params, dict):
            return int(next(iter(params.values())).size)
        return int(params.size)
    except Exception:  # noqa: BLE001
        return None


def ensure_collection(client, name: str, dim: int) -> None:
    """Crea la colección del tenant si no existe (size=dim del modelo, COSINE).

    Si YA existe, verifica que la dimensión coincida. Con dos proveedores de
    embeddings (Gemini 768 vs. OpenAI 1536) este choque es fácil de provocar
    cambiando de API key, y el error nativo de Qdrant no dice qué pasó.
    """
    from qdrant_client import models as qm

    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
        return

    existing = collection_dim(client, name)
    if existing is not None and existing != dim:
        raise RuntimeError(
            f"La colección '{name}' ya existe con vectores de {existing} dims, pero "
            f"el embedder actual produce {dim}. Los espacios vectoriales de distintos "
            f"modelos/dimensiones NO son compatibles: indexa con el mismo modelo con "
            f"que se creó la colección, o bórrala para re-indexar todo desde cero."
        )


def upsert(client, name: str, payloads: list[dict[str, Any]], vectors) -> None:
    """Upsert idempotente (IDs deterministas de f_metadata → mismo doc no duplica)."""
    from qdrant_client import models as qm

    points = [
        qm.PointStruct(id=p["id"], vector=vectors[i].tolist(), payload=p["payload"])
        for i, p in enumerate(payloads)
    ]
    for s in range(0, len(points), UPSERT_BATCH_SIZE):
        client.upsert(collection_name=name, points=points[s : s + UPSERT_BATCH_SIZE], wait=True)


def index_route(client, name: str) -> tuple[str, int, int]:
    """Lee de Qdrant cuántos vectores hay y el umbral, y deduce la ruta activa.
    Si la colección no existe todavía (p.ej. ningún doc produjo chunks), reporta
    fuerza bruta con 0 vectores en vez de fallar."""
    if not client.collection_exists(name):
        return "brute_force", 0, DEFAULT_INDEXING_THRESHOLD
    info = client.get_collection(name)
    count = int(getattr(info, "points_count", 0) or 0)
    threshold = DEFAULT_INDEXING_THRESHOLD
    try:
        t = info.config.optimizer_config.indexing_threshold
        if t:
            threshold = int(t)
    except Exception:  # noqa: BLE001
        pass
    route = "hnsw" if count >= threshold else "brute_force"
    return route, count, threshold
