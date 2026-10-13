"""
Pipeline de ingesta RAG · 09 · INDEXADO en Qdrant (escritura de la colección del tenant)
Ruta: Backend-RAGs/pipeline/etapas/e09_indexado.py

Distinto del benchmark de componentes/vectorstores: aquí solo se CREA la colección, se
hace upsert idempotente y se LEE la ruta de indexación que eligió Qdrant.

La ruta NO la elige este código: la decide Qdrant solo, en segundo plano. Cuando un
SEGMENTO de la colección acumula más vectores sin indexar que su `indexing_threshold`,
el optimizador construye el índice HNSW de ese segmento; mientras tanto, ese
segmento se recorre por fuerza bruta.

Ojo con la unidad: el umbral está en KILOBYTES de vectores y es POR SEGMENTO, no un
número de vectores de la colección. Qdrant cuenta 1 KB = un vector de 256
dimensiones, así que un vector de 768 dims "pesa" 3 KB y uno de 1536, 6 KB.

Por eso la ruta se LEE de lo que Qdrant reporta (`indexed_vectors_count`) en vez de
deducirla del umbral:
  brute_force · ningún vector en HNSW todavía
  mixed       · algunos segmentos con HNSW y otros sin indexar
  hnsw        · todos los vectores en HNSW
Justo después de un upsert la indexación puede seguir en curso (`optimizing`).
"""

from __future__ import annotations

from typing import Any

# Umbral por defecto en KB por segmento: el del config.yaml de Qdrant y el que
# reporta el servidor del curso. Solo describe el diagrama: la ingesta lee el real.
DEFAULT_INDEXING_THRESHOLD_KB = 10000
KB_PER_256_DIMS = 1  # Qdrant: 1 KB = un vector de 256 dimensiones
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
    """Upsert idempotente (IDs deterministas de e07_metadata → mismo doc no duplica)."""
    from qdrant_client import models as qm

    points = [
        qm.PointStruct(id=p["id"], vector=vectors[i].tolist(), payload=p["payload"])
        for i, p in enumerate(payloads)
    ]
    for s in range(0, len(points), UPSERT_BATCH_SIZE):
        client.upsert(collection_name=name, points=points[s : s + UPSERT_BATCH_SIZE], wait=True)


def vectors_per_threshold(threshold_kb: int, dim: int) -> int:
    """Cuántos vectores de `dim` dimensiones caben en `threshold_kb` (por segmento)."""
    return int(threshold_kb * 256 / dim) if dim else 0


def index_route(client, name: str) -> dict[str, Any]:
    """Ruta de indexación REAL de la colección, según lo que reporta Qdrant.

    Devuelve {index_route, num_vectors, indexed_vectors, segments, optimizing,
    indexing_threshold (KB por segmento), vectors_threshold (≈ vectores por segmento
    para pasar a HNSW con la dimensión de la colección)}. Si la colección no existe
    todavía (ningún doc produjo chunks), reporta fuerza bruta con 0 vectores.
    """
    if not client.collection_exists(name):
        return {"index_route": "brute_force", "num_vectors": 0, "indexed_vectors": 0,
                "segments": 0, "optimizing": False,
                "indexing_threshold": DEFAULT_INDEXING_THRESHOLD_KB, "vectors_threshold": 0}
    info = client.get_collection(name)
    count = int(getattr(info, "points_count", 0) or 0)
    indexed = int(getattr(info, "indexed_vectors_count", 0) or 0)
    threshold = DEFAULT_INDEXING_THRESHOLD_KB
    try:
        t = info.config.optimizer_config.indexing_threshold
        if t:
            threshold = int(t)
    except Exception:  # noqa: BLE001
        pass

    if indexed == 0:
        route = "brute_force"
    elif indexed >= count:
        route = "hnsw"
    else:
        route = "mixed"
    status = str(getattr(info, "status", "") or "").lower()
    return {
        "index_route": route,
        "num_vectors": count,
        "indexed_vectors": min(indexed, count),
        "segments": int(getattr(info, "segments_count", 0) or 0),
        # yellow = el optimizador sigue trabajando (p. ej. construyendo HNSW)
        "optimizing": "yellow" in status,
        "indexing_threshold": threshold,
        "vectors_threshold": vectors_per_threshold(threshold, collection_dim(client, name) or 0),
    }


def check_dimension(client, name: str, dimension: int, model: str) -> None:
    """Falla si la colección ya existe con OTRA dimensión: sus vectores serían de otro
    modelo y la colección quedaría inconsultable. Se llama ANTES de gastar en OCR y
    embeddings."""
    if not client.collection_exists(name):
        return
    existing = collection_dim(client, name)
    if existing is not None and existing != dimension:
        raise RuntimeError(
            f"La colección '{name}' ya existe con vectores de {existing} dims, "
            f"pero {model} produce {dimension}. Indexa con el "
            f"mismo modelo con que se creó la colección, o bórrala para re-indexar."
        )
